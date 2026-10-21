"""Contenedor de dependencias de infraestructura.

Construye el cliente MongoDB real a partir de la configuración y lo
cierra de forma ordenada durante el apagado. Las pruebas sustituyen
este contenedor por dobles con la misma forma.
"""

from pdf_persistence.config import Settings
from pdf_persistence.domain.ports import DocumentRepository
from pdf_persistence.infrastructure.mongo_repository import MongoRepository
from pdf_persistence.service.document_use_case import DocumentUseCase


class Container:
    """Agrupa las dependencias externas del servicio."""

    def __init__(
        self, repository: DocumentRepository, use_case: DocumentUseCase
    ) -> None:
        self.repository = repository
        self.use_case = use_case

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        """Construye el repositorio MongoDB real a partir de la configuración."""
        repository = MongoRepository(
            uri=settings.mongo_uri,
            database_name=settings.mongo_database,
            collection_name=settings.mongo_collection,
            timeout_ms=settings.mongo_timeout_ms,
        )
        return cls(
            repository=repository,
            use_case=DocumentUseCase(repository=repository),
        )

    async def ensure_indexes(self) -> None:
        """Crea los índices necesarios de forma idempotente."""
        await self.repository.ensure_indexes()

    async def aclose(self) -> None:
        """Cierra los recursos de infraestructura de forma ordenada."""
        await self.repository.aclose()
