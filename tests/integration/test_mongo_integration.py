"""Pruebas de integración con un servidor MongoDB real.

Se omiten automáticamente salvo que se configure ``TEST_MONGO_URI``
(p. ej. ``mongodb://localhost:27017``). Prerrequisitos y procedimiento
completo en ``tests/integration/README.md``.

Ejecución::

    TEST_MONGO_URI=mongodb://localhost:27017 uv run pytest -m integration --no-cov
"""

import contextlib
import os
import uuid

import pytest

from pdf_persistence.config import Settings
from pdf_persistence.container import Container
from pdf_persistence.domain.errors import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
)
from pdf_persistence.service.document_use_case import DocumentUseCase

pytestmark = pytest.mark.integration

TEST_MONGO_URI = os.environ.get("TEST_MONGO_URI", "")


def _mongo_available() -> bool:
    return bool(TEST_MONGO_URI)


@pytest.fixture(scope="module")
def container():
    if not _mongo_available():
        pytest.skip("TEST_MONGO_URI no está configurado; se omite la integración.")
    unique = uuid.uuid4().hex[:8]
    settings = Settings(
        mongo_uri=TEST_MONGO_URI,
        mongo_database=f"pdf_persistence_it_{unique}",
        mongo_collection="documents",
        mongo_timeout_ms=3000,
        log_level="INFO",
        port=8003,
    )
    from pdf_persistence.infrastructure.mongo_repository import MongoRepository

    repository = MongoRepository(
        uri=settings.mongo_uri,
        database_name=settings.mongo_database,
        collection_name=settings.mongo_collection,
        timeout_ms=settings.mongo_timeout_ms,
    )
    built = Container(repository=repository, use_case=DocumentUseCase(repository))
    yield built
    repository._client.drop_database(settings.mongo_database)
    repository._client.close()


async def _cleanup(container, checksum):
    with contextlib.suppress(Exception):  # limpieza best-effort
        await container.repository._collection.delete_one({"checksum": checksum})


@pytest.mark.skipif(not _mongo_available(), reason="TEST_MONGO_URI no configurado")
class TestMongoIntegration:
    async def test_index_uniqueness_is_enforced(self, container):
        await container.ensure_indexes()
        checksum = (uuid.uuid4().hex * 2)[:64]
        await container.use_case.create({"checksum": checksum, "filename": "a.pdf"})
        with pytest.raises(DocumentAlreadyExistsError):
            await container.use_case.create(
                {"checksum": checksum, "filename": "otro.pdf"}
            )
        await _cleanup(container, checksum)

    async def test_full_document_lifecycle(self, container):
        await container.ensure_indexes()
        checksum = (uuid.uuid4().hex * 2)[:64]
        payload = {
            "checksum": checksum,
            "checksum_algorithm": "sha256",
            "filename": "doc.pdf",
            "file_size_bytes": 1234,
            "text": "texto",
            "page_count": 1,
        }
        _, created = await container.use_case.create(payload)
        assert created is True
        fetched = await container.use_case.get(checksum)
        assert fetched.checksum == checksum

        updated = await container.use_case.update(checksum, {"summary": "resumen"})
        assert updated.summary == "resumen"

        items, total = await container.use_case.list(limit=10, offset=0)
        assert any(d.checksum == checksum for d in items)
        assert total >= 1

        await container.use_case.delete(checksum)
        with pytest.raises(DocumentNotFoundError):
            await container.use_case.get(checksum)
        _, total_after_delete = await container.use_case.list(limit=10, offset=0)
        assert total_after_delete == total - 1
        await _cleanup(container, checksum)

    async def test_ping_is_real(self, container):
        assert await container.use_case.ping() is True
