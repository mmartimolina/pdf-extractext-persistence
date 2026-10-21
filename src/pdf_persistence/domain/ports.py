"""Puertos (interfaces) que la capa de negocio requiere de la infraestructura.

Permiten sustituir MongoDB por un doble de prueba sin acoplar la lógica
de negocio al driver concreto.
"""

from typing import Protocol

from pdf_persistence.domain.models import StoredDocument

#: Campos del documento que pueden actualizarse mediante PUT.
UPDATABLE_FIELDS = (
    "checksum_algorithm",
    "filename",
    "content_type",
    "file_size_bytes",
    "text",
    "summary",
    "page_count",
    "model",
    "metadata",
)


class DocumentRepository(Protocol):
    """Puerto del repositorio de documentos."""

    async def insert(self, document: StoredDocument) -> None:
        """Inserta un documento nuevo.

        Raises:
            DuplicateChecksumError: si el checksum ya está registrado.
        """
        ...

    async def find_by_checksum(
        self, checksum: str, include_deleted: bool = False
    ) -> StoredDocument | None:
        """Devuelve el documento con ese checksum, si existe y está activo."""
        ...

    async def list_active(
        self, limit: int, offset: int
    ) -> tuple[list[StoredDocument], int]:
        """Devuelve una página de documentos activos y el total activo."""
        ...

    async def update_fields(self, checksum: str, fields: dict) -> StoredDocument | None:
        """Actualiza campos de un documento activo; None si no existe."""
        ...

    async def soft_delete(self, checksum: str) -> bool:
        """Marca eliminado un documento activo; False si no existe."""
        ...

    async def ping(self) -> bool:
        """Comprueba la conectividad real con la base de datos."""
        ...

    async def ensure_indexes(self) -> None:
        """Crea los índices necesarios de forma idempotente."""
        ...

    async def aclose(self) -> None:
        """Cierra los recursos del repositorio."""
        ...
