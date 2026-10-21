"""Modelos de dominio compartidos entre capas."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoredDocument:
    """Registro persistido de un documento procesado.

    El ``checksum`` es el identificador de negocio acordado con el
    ecosistema: lo calcula Validation (SHA-256 del contenido binario) y
    Persistence nunca lo recalcula ni lo modifica.
    """

    checksum: str
    created_at: datetime
    updated_at: datetime
    deleted: bool
    deleted_at: datetime | None
    checksum_algorithm: str | None = None
    filename: str | None = None
    content_type: str | None = None
    file_size_bytes: int | None = None
    text: str | None = None
    summary: str | None = None
    page_count: int | None = None
    model: str | None = None
    metadata: dict | None = None
