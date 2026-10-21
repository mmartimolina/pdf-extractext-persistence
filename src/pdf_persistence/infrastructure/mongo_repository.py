"""Repositorio concreto de documentos sobre MongoDB (PyMongo asíncrono).

Traduce los errores del driver a excepciones de dominio para que la capa
de negocio no dependa de MongoDB. Centraliza cliente, base de datos y
colección: no se crean conexiones por solicitud.
"""

import logging
from datetime import UTC, datetime

from pymongo import ASCENDING, AsyncMongoClient
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

logger = logging.getLogger("pdf_persistence.mongo")

DOCUMENT_FIELDS = (
    "checksum",
    "checksum_algorithm",
    "filename",
    "content_type",
    "file_size_bytes",
    "text",
    "summary",
    "page_count",
    "model",
    "metadata",
    "created_at",
    "updated_at",
    "deleted",
    "deleted_at",
)


class MongoRepository:
    """Implementación del puerto ``DocumentRepository`` sobre MongoDB."""

    def __init__(
        self,
        uri: str,
        database_name: str,
        collection_name: str,
        timeout_ms: int,
    ) -> None:
        self._client = AsyncMongoClient(
            host=uri,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms,
        )
        self._collection = self._client[database_name][collection_name]
        self._database_name = database_name
        self._collection_name = collection_name

    def _translate_error(
        self, exc: PyMongoError
    ) -> MongoUnavailableError | MongoTimeoutError:
        if isinstance(
            exc, (NetworkTimeout, ExecutionTimeout, ServerSelectionTimeoutError)
        ):
            return MongoTimeoutError()
        if isinstance(exc, (AutoReconnect, ConnectionError)):
            return MongoUnavailableError()
        return MongoUnavailableError("Error de comunicación con MongoDB.")

    @staticmethod
    def _to_document(record: dict) -> StoredDocument:
        return StoredDocument(**{field: record.get(field) for field in DOCUMENT_FIELDS})

    @staticmethod
    def _to_record(document: StoredDocument) -> dict:
        return {field: getattr(document, field) for field in DOCUMENT_FIELDS}

    async def insert(self, document: StoredDocument) -> None:
        try:
            await self._collection.insert_one(self._to_record(document))
        except DuplicateKeyError:
            raise DuplicateChecksumError(document.checksum) from None
        except PyMongoError as exc:
            raise self._translate_error(exc) from None

    async def find_by_checksum(
        self, checksum: str, include_deleted: bool = False
    ) -> StoredDocument | None:
        query: dict = {"checksum": checksum}
        if not include_deleted:
            query["deleted"] = {"$ne": True}
        try:
            record = await self._collection.find_one(query)
        except PyMongoError as exc:
            raise self._translate_error(exc) from None
        return self._to_document(record) if record is not None else None

    async def list_active(
        self, limit: int, offset: int
    ) -> tuple[list[StoredDocument], int]:
        query = {"deleted": {"$ne": True}}
        try:
            total = await self._collection.count_documents(query)
            cursor = (
                self._collection.find(query)
                .sort("created_at", ASCENDING)
                .skip(offset)
                .limit(limit)
            )
            records = [record async for record in cursor]
        except PyMongoError as exc:
            raise self._translate_error(exc) from None
        return [self._to_document(record) for record in records], total

    async def update_fields(self, checksum: str, fields: dict) -> StoredDocument | None:
        query = {"checksum": checksum, "deleted": {"$ne": True}}
        update = {"$set": {**fields, "updated_at": datetime.now(UTC)}}
        try:
            record = await self._collection.find_one_and_update(
                query, update, return_document=True
            )
        except PyMongoError as exc:
            raise self._translate_error(exc) from None
        return self._to_document(record) if record is not None else None

    async def soft_delete(self, checksum: str) -> bool:
        query = {"checksum": checksum, "deleted": {"$ne": True}}
        update = {"$set": {"deleted": True, "deleted_at": datetime.now(UTC)}}
        try:
            result = await self._collection.update_one(query, update)
        except PyMongoError as exc:
            raise self._translate_error(exc) from None
        return result.modified_count > 0

    async def ping(self) -> bool:
        """Comprueba la conectividad real con un ping administrativo."""
        try:
            await self._client.admin.command("ping")
        except PyMongoError as exc:
            raise self._translate_error(exc) from None
        return True

    async def ensure_indexes(self) -> None:
        """Crea el índice único por checksum y el índice de listado."""
        try:
            await self._collection.create_index(
                [("checksum", ASCENDING)], unique=True, name="unique_checksum"
            )
            await self._collection.create_index(
                [("deleted", ASCENDING), ("created_at", ASCENDING)],
                name="active_listing",
            )
        except PyMongoError as exc:
            raise self._translate_error(exc) from None
        logger.info(
            "indexes_ensured database=%s collection=%s",
            self._database_name,
            self._collection_name,
        )

    async def aclose(self) -> None:
        """Cierra el cliente MongoDB."""
        self._client.close()
