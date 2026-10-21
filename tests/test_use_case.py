"""Pruebas del caso de uso de persistencia de documentos."""

import pytest
from tests.fakes import FakeRepository

from pdf_persistence.domain.errors import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    EmptyUpdateError,
)
from pdf_persistence.service.document_use_case import DocumentUseCase


@pytest.fixture
def repository():
    return FakeRepository()


@pytest.fixture
def use_case(repository):
    return DocumentUseCase(repository=repository)


PAYLOAD = {
    "checksum": "b" * 64,
    "checksum_algorithm": "sha256",
    "filename": "informe.pdf",
    "content_type": "application/pdf",
    "file_size_bytes": 2048,
    "text": "contenido textual",
    "summary": None,
    "page_count": 2,
    "model": None,
    "metadata": None,
}


class TestCreate:
    async def test_creates_document(self, use_case, repository):
        result, created = await use_case.create(PAYLOAD)
        assert created is True
        assert result.checksum == "b" * 64
        assert result.deleted is False
        assert result.deleted_at is None
        assert result.created_at is not None
        assert result.updated_at is not None
        assert repository.documents["b" * 64] == result

    async def test_create_is_idempotent_for_identical_payload(self, use_case):
        first, _ = await use_case.create(PAYLOAD)
        second, created = await use_case.create(PAYLOAD)
        assert created is False
        assert second == first

    async def test_create_conflict_for_different_payload(self, use_case):
        await use_case.create(PAYLOAD)
        different = {**PAYLOAD, "filename": "otro.pdf"}
        with pytest.raises(DocumentAlreadyExistsError):
            await use_case.create(different)

    async def test_create_conflict_when_existing_was_deleted(self, use_case):
        await use_case.create(PAYLOAD)
        await use_case.delete(PAYLOAD["checksum"])
        with pytest.raises(DocumentAlreadyExistsError):
            await use_case.create({**PAYLOAD, "summary": "nuevo"})


class TestGet:
    async def test_get_returns_active_document(self, use_case):
        created, _ = await use_case.create(PAYLOAD)
        assert await use_case.get(PAYLOAD["checksum"]) == created

    async def test_get_missing_raises_not_found(self, use_case):
        with pytest.raises(DocumentNotFoundError):
            await use_case.get("c" * 64)

    async def test_get_deleted_raises_not_found(self, use_case):
        await use_case.create(PAYLOAD)
        await use_case.delete(PAYLOAD["checksum"])
        with pytest.raises(DocumentNotFoundError):
            await use_case.get(PAYLOAD["checksum"])


class TestList:
    async def test_list_paginates_active_documents(self, use_case):
        for i in range(5):
            await use_case.create({**PAYLOAD, "checksum": f"{i:064x}"})
        items, total = await use_case.list(limit=2, offset=0)
        assert len(items) == 2
        assert total == 5
        _, total_2 = await use_case.list(limit=2, offset=4)
        assert total_2 == 5

    async def test_list_excludes_deleted(self, use_case):
        await use_case.create(PAYLOAD)
        await use_case.delete(PAYLOAD["checksum"])
        items, total = await use_case.list(limit=10, offset=0)
        assert items == []
        assert total == 0


class TestUpdate:
    async def test_update_changes_allowed_fields(self, use_case):
        await use_case.create(PAYLOAD)
        updated = await use_case.update(PAYLOAD["checksum"], {"summary": "resumen"})
        assert updated.summary == "resumen"
        assert updated.filename == "informe.pdf"

    async def test_update_missing_raises_not_found(self, use_case):
        with pytest.raises(DocumentNotFoundError):
            await use_case.update("d" * 64, {"summary": "x"})

    async def test_update_empty_patch_raises(self, use_case):
        await use_case.create(PAYLOAD)
        with pytest.raises(EmptyUpdateError):
            await use_case.update(PAYLOAD["checksum"], {})

    async def test_update_deleted_raises_not_found(self, use_case):
        await use_case.create(PAYLOAD)
        await use_case.delete(PAYLOAD["checksum"])
        with pytest.raises(DocumentNotFoundError):
            await use_case.update(PAYLOAD["checksum"], {"summary": "x"})


class TestDelete:
    async def test_delete_marks_document(self, use_case, repository):
        await use_case.create(PAYLOAD)
        await use_case.delete(PAYLOAD["checksum"])
        stored = repository.documents[PAYLOAD["checksum"]]
        assert stored.deleted is True
        assert stored.deleted_at is not None

    async def test_delete_twice_raises_not_found(self, use_case):
        await use_case.create(PAYLOAD)
        await use_case.delete(PAYLOAD["checksum"])
        with pytest.raises(DocumentNotFoundError):
            await use_case.delete(PAYLOAD["checksum"])

    async def test_delete_missing_raises_not_found(self, use_case):
        with pytest.raises(DocumentNotFoundError):
            await use_case.delete("e" * 64)


class TestHealth:
    async def test_ping_ok(self, use_case):
        assert await use_case.ping() is True

    async def test_ping_failure_raises_unavailable(self, use_case, repository):
        from pdf_persistence.domain.errors import MongoUnavailableError

        repository.fail_mode = MongoUnavailableError("conexion perdida")
        with pytest.raises(MongoUnavailableError):
            await use_case.ping()
