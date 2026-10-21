"""Caso de uso de administración de documentos persistidos.

Contiene las reglas de negocio de persistencia: idempotencia del
registro por checksum, exclusión de eliminados en consultas y
eliminación lógica. No conoce HTTP ni MongoDB.
"""

from datetime import UTC, datetime

from pdf_persistence.domain.errors import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    DuplicateChecksumError,
    EmptyUpdateError,
)
from pdf_persistence.domain.models import StoredDocument
from pdf_persistence.domain.ports import UPDATABLE_FIELDS, DocumentRepository


class DocumentUseCase:
    """Reglas de persistencia de documentos del ecosistema."""

    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def create(self, payload: dict) -> tuple[StoredDocument, bool]:
        """Registra un documento nuevo.

        Idempotencia: si el checksum ya existe con exactamente los mismos
        datos proporcionados, se devuelve el documento existente (created
        ``False``); si los datos difieren (o el documento fue eliminado
        lógicamente), se rechaza con ``DocumentAlreadyExistsError``. La
        unicidad real la garantiza el índice único del repositorio ante
        carreras de concurrencia.
        """
        now = datetime.now(UTC)
        document = StoredDocument(
            checksum=payload["checksum"],
            created_at=now,
            updated_at=now,
            deleted=False,
            deleted_at=None,
            **{field: payload.get(field) for field in UPDATABLE_FIELDS},
        )
        try:
            await self._repository.insert(document)
            return document, True
        except DuplicateChecksumError:
            existing = await self._repository.find_by_checksum(
                document.checksum, include_deleted=True
            )
            if (
                existing is None
                or existing.deleted
                or not self._same_payload(existing, payload)
            ):
                raise DocumentAlreadyExistsError(document.checksum) from None
            return existing, False

    @staticmethod
    def _same_payload(existing: StoredDocument, payload: dict) -> bool:
        return all(
            getattr(existing, field) == payload.get(field)
            for field in UPDATABLE_FIELDS
            if field in payload
        )

    async def get(self, checksum: str) -> StoredDocument:
        """Recupera un documento activo por checksum."""
        document = await self._repository.find_by_checksum(checksum)
        if document is None:
            raise DocumentNotFoundError(checksum)
        return document

    async def list(self, limit: int, offset: int) -> tuple[list[StoredDocument], int]:
        """Lista documentos activos con paginación."""
        return await self._repository.list_active(limit=limit, offset=offset)

    async def update(self, checksum: str, patch: dict) -> StoredDocument:
        """Actualiza únicamente los campos permitidos de un documento activo."""
        fields = {k: v for k, v in patch.items() if k in UPDATABLE_FIELDS}
        if not fields:
            raise EmptyUpdateError()
        document = await self._repository.update_fields(checksum, fields)
        if document is None:
            raise DocumentNotFoundError(checksum)
        return document

    async def delete(self, checksum: str) -> None:
        """Realiza la eliminación lógica del documento."""
        deleted = await self._repository.soft_delete(checksum)
        if not deleted:
            raise DocumentNotFoundError(checksum)

    async def ping(self) -> bool:
        """Comprueba la conectividad real con la base de datos."""
        return await self._repository.ping()
