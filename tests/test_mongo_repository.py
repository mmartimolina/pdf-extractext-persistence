"""Pruebas unitarias del repositorio MongoDB con un doble de colección.

No requieren un servidor MongoDB real: validan la lógica del
repositorio (filtros, actualizaciones, eliminación lógica) y la
traducción de errores del driver a excepciones de dominio.
"""

from datetime import UTC, datetime

import pytest
from pymongo.errors import (
    AutoReconnect,
    DuplicateKeyError,
    ExecutionTimeout,
    NetworkTimeout,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from pdf_persistence.domain.errors import (
    DuplicateChecksumError,
    MongoTimeoutError,
    MongoUnavailableError,
)
from pdf_persistence.domain.models import StoredDocument
from pdf_persistence.infrastructure.mongo_repository import MongoRepository


def make_record(checksum="a" * 64, **overrides) -> StoredDocument:
    now = datetime.now(UTC)
    defaults = dict(
        checksum=checksum,
        created_at=now,
        updated_at=now,
        deleted=False,
        deleted_at=None,
    )
    defaults.update(overrides)
    return StoredDocument(**defaults)


class FakeCursor:
    def __init__(self, records):
        self._records = records

    def sort(self, key, direction):
        self._records = sorted(self._records, key=lambda r: r[key])
        return self

    def skip(self, offset):
        self._records = self._records[offset:]
        return self

    def limit(self, limit):
        self._records = self._records[:limit]
        return self

    def __aiter__(self):
        return self._agen()

    async def _agen(self):
        for record in self._records:
            yield record


class FakeAdmin:
    def __init__(self, fail: Exception | None = None):
        self.fail = fail

    async def command(self, name):
        if self.fail:
            raise self.fail
        return {"ok": 1}


class FakeClient:
    def __init__(self, fail: Exception | None = None):
        self.admin = FakeAdmin(fail)

    def close(self):
        self.closed = True


class FakeCollection:
    """Doble de AsyncCollection con el subconjunto usado por el repositorio."""

    def __init__(self):
        self.records: dict[str, dict] = {}
        self.fail: Exception | None = None
        self.indexes: list = []

    def _check_fail(self):
        if self.fail:
            raise self.fail

    async def insert_one(self, record):
        self._check_fail()
        if record["checksum"] in self.records:
            raise DuplicateKeyError("duplicate")
        self.records[record["checksum"]] = record

    async def find_one(self, query):
        self._check_fail()
        record = self.records.get(query.get("checksum"))
        if record is None:
            return None
        deleted_filter = query.get("deleted")
        if (
            isinstance(deleted_filter, dict)
            and deleted_filter.get("$ne") is True
            and record.get("deleted")
        ):
            return None
        return record

    async def count_documents(self, query):
        self._check_fail()
        deleted_filter = query.get("deleted")
        if isinstance(deleted_filter, dict) and deleted_filter.get("$ne") is True:
            return sum(1 for r in self.records.values() if not r.get("deleted"))
        return len(self.records)

    def find(self, query):
        self._check_fail()
        deleted_filter = query.get("deleted")
        records = list(self.records.values())
        if isinstance(deleted_filter, dict) and deleted_filter.get("$ne") is True:
            records = [r for r in records if not r.get("deleted")]
        return FakeCursor(records)

    async def update_one(self, query, update):
        self._check_fail()
        record = self.records.get(query.get("checksum"))
        if record is None or record.get("deleted"):
            return type("R", (), {"modified_count": 0})()
        record.update(update["$set"])
        return type("R", (), {"modified_count": 1})()

    async def find_one_and_update(self, query, update, return_document=True):
        self._check_fail()
        record = self.records.get(query.get("checksum"))
        if record is None or record.get("deleted"):
            return None
        record.update(update["$set"])
        return record

    async def create_index(self, keys, unique=False, name=None):
        self._check_fail()
        self.indexes.append((keys, unique, name))


@pytest.fixture
def repository():
    repo = MongoRepository(
        uri="mongodb://localhost:27017",
        database_name="test_db",
        collection_name="documents",
        timeout_ms=1000,
    )
    repo._collection = FakeCollection()
    repo._client = FakeClient()
    return repo


class TestInsert:
    async def test_insert_stores_record(self, repository):
        document = make_record(filename="a.pdf")
        await repository.insert(document)
        stored = repository._collection.records[document.checksum]
        assert stored["checksum"] == document.checksum
        assert stored["filename"] == "a.pdf"
        assert stored["deleted"] is False

    async def test_insert_duplicate_raises_domain_error(self, repository):
        document = make_record()
        await repository.insert(document)
        with pytest.raises(DuplicateChecksumError):
            await repository.insert(document)


class TestFind:
    async def test_find_returns_active_document(self, repository):
        document = make_record()
        await repository.insert(document)
        found = await repository.find_by_checksum(document.checksum)
        assert found is not None
        assert found.checksum == document.checksum
        assert found.created_at == document.created_at

    async def test_find_excludes_deleted(self, repository):
        document = make_record()
        await repository.insert(document)
        await repository.soft_delete(document.checksum)
        assert await repository.find_by_checksum(document.checksum) is None

    async def test_find_missing_returns_none(self, repository):
        assert await repository.find_by_checksum("f" * 64) is None


class TestListActive:
    async def test_list_returns_page_and_total(self, repository):
        for i in range(3):
            await repository.insert(make_record(checksum=f"{i:064x}"))
        items, total = await repository.list_active(limit=2, offset=1)
        assert total == 3
        assert [i.checksum for i in items] == [f"{1:064x}", f"{2:064x}"]

    async def test_list_excludes_deleted(self, repository):
        await repository.insert(make_record())
        await repository.insert(make_record(checksum="b" * 64))
        await repository.soft_delete("b" * 64)
        items, total = await repository.list_active(limit=10, offset=0)
        assert total == 1
        assert len(items) == 1


class TestUpdate:
    async def test_update_sets_fields_and_updated_at(self, repository):
        document = make_record()
        await repository.insert(document)
        updated = await repository.update_fields(
            document.checksum, {"summary": "resumen"}
        )
        assert updated.summary == "resumen"
        assert updated.updated_at >= document.updated_at

    async def test_update_missing_returns_none(self, repository):
        assert await repository.update_fields("e" * 64, {"summary": "x"}) is None

    async def test_update_deleted_returns_none(self, repository):
        document = make_record()
        await repository.insert(document)
        await repository.soft_delete(document.checksum)
        assert (
            await repository.update_fields(document.checksum, {"summary": "x"}) is None
        )


class TestSoftDelete:
    async def test_soft_delete_marks_document(self, repository):
        document = make_record()
        await repository.insert(document)
        assert await repository.soft_delete(document.checksum) is True
        deleted = await repository.find_by_checksum(
            document.checksum, include_deleted=True
        )
        assert deleted.deleted is True
        assert deleted.deleted_at is not None

    async def test_soft_delete_twice_returns_false(self, repository):
        document = make_record()
        await repository.insert(document)
        await repository.soft_delete(document.checksum)
        assert await repository.soft_delete(document.checksum) is False


class TestPing:
    async def test_ping_ok(self, repository):
        assert await repository.ping() is True

    async def test_ping_connection_error_raises_unavailable(self, repository):
        repository._client = FakeClient(fail=AutoReconnect("down"))
        with pytest.raises(MongoUnavailableError):
            await repository.ping()

    async def test_ping_selection_timeout_raises_timeout(self, repository):
        repository._client = FakeClient(fail=ServerSelectionTimeoutError("slow"))
        with pytest.raises(MongoTimeoutError):
            await repository.ping()


class TestEnsureIndexes:
    async def test_creates_unique_checksum_index(self, repository):
        await repository.ensure_indexes()
        indexes = repository._collection.indexes
        assert any(unique and name == "unique_checksum" for _, unique, name in indexes)
        assert any(name == "active_listing" for _, _, name in indexes)


class TestErrorTranslation:
    @pytest.mark.parametrize(
        ("driver_error", "domain_error"),
        [
            (NetworkTimeout("t"), MongoTimeoutError),
            (ExecutionTimeout("t"), MongoTimeoutError),
            (ServerSelectionTimeoutError("t"), MongoTimeoutError),
            (AutoReconnect("x"), MongoUnavailableError),
            (PyMongoError("generic"), MongoUnavailableError),
        ],
    )
    async def test_find_translates_driver_errors(
        self, repository, driver_error, domain_error
    ):
        repository._collection.fail = driver_error
        with pytest.raises(domain_error):
            await repository.find_by_checksum("a" * 64)

    async def test_insert_translates_driver_errors(self, repository):
        repository._collection.fail = AutoReconnect("x")
        with pytest.raises(MongoUnavailableError):
            await repository.insert(make_record())

    async def test_list_translates_driver_errors(self, repository):
        repository._collection.fail = NetworkTimeout("t")
        with pytest.raises(MongoTimeoutError):
            await repository.list_active(limit=1, offset=0)

    async def test_update_translates_driver_errors(self, repository):
        repository._collection.fail = PyMongoError("x")
        with pytest.raises(MongoUnavailableError):
            await repository.update_fields("a" * 64, {"summary": "s"})

    async def test_soft_delete_translates_driver_errors(self, repository):
        repository._collection.fail = PyMongoError("x")
        with pytest.raises(MongoUnavailableError):
            await repository.soft_delete("a" * 64)

    async def test_ensure_indexes_translates_driver_errors(self, repository):
        repository._collection.fail = PyMongoError("x")
        with pytest.raises(MongoUnavailableError):
            await repository.ensure_indexes()


class TestClose:
    async def test_aclose_closes_client(self, repository):
        await repository.aclose()
        assert repository._client.closed is True
