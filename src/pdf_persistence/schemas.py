"""Esquemas del contrato HTTP (capa de presentación).

Todas las respuestas, incluidos los errores, son JSON con un formato
uniforme y estable. No se aceptan campos arbitrarios sin validación.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: Checksum de negocio en hexadecimal minúscula: cubre MD5 (32) del
#: monolito original y SHA-256 (64) del contrato de Validation.
CHECKSUM_PATTERN = r"^[0-9a-f]{32,128}$"


class DocumentCreateRequest(BaseModel):
    """Solicitud de ``POST /documents``."""

    model_config = ConfigDict(extra="forbid")

    checksum: str = Field(
        description="Checksum del contenido binario, en hexadecimal minúscula. "
        "Identificador de negocio; no se recalcula ni se modifica.",
        pattern=CHECKSUM_PATTERN,
    )
    checksum_algorithm: str | None = Field(
        default=None, description="Algoritmo del checksum (p. ej. sha256)."
    )
    filename: str | None = Field(default=None, description="Nombre del archivo.")
    content_type: str | None = Field(
        default=None, description="Tipo de contenido del documento."
    )
    file_size_bytes: int | None = Field(
        default=None, ge=0, description="Tamaño del archivo, en bytes."
    )
    text: str | None = Field(
        default=None, description="Texto extraído del documento, si se proporciona."
    )
    summary: str | None = Field(
        default=None, description="Resumen generado, si se proporciona."
    )
    page_count: int | None = Field(
        default=None, ge=1, description="Cantidad de páginas del documento."
    )
    model: str | None = Field(
        default=None, description="Modelo de IA utilizado para el resumen."
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Metadatos adicionales aprobados por el contrato."
    )


class DocumentUpdateRequest(BaseModel):
    """Solicitud de ``PUT /documents/{checksum}``.

    Solo se aceptan campos modificables; el checksum no puede cambiarse.
    """

    model_config = ConfigDict(extra="forbid")

    checksum_algorithm: str | None = None
    filename: str | None = None
    content_type: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    text: str | None = None
    summary: str | None = None
    page_count: int | None = Field(default=None, ge=1)
    model: str | None = None
    metadata: dict[str, Any] | None = None


class DocumentResponse(BaseModel):
    """Representación JSON de un documento persistido."""

    checksum: str
    checksum_algorithm: str | None
    filename: str | None
    content_type: str | None
    file_size_bytes: int | None
    text: str | None
    summary: str | None
    page_count: int | None
    model: str | None
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str
    deleted: bool
    deleted_at: str | None


class DocumentListResponse(BaseModel):
    """Respuesta paginada de ``GET /documents``."""

    items: list[DocumentResponse]
    total: int = Field(description="Total de documentos activos.")
    limit: int
    offset: int


class DeleteResponse(BaseModel):
    """Confirmación de eliminación lógica."""

    status: str
    checksum: str


class HealthResponse(BaseModel):
    """Respuesta de los healthchecks."""

    status: str


class ReadinessResponse(BaseModel):
    """Respuesta del readiness probe, con el motivo cuando no está listo."""

    status: str
    reason: str | None = Field(default=None, description="Motivo si no está listo.")


class ErrorDetail(BaseModel):
    """Detalle estructurado de un error."""

    code: str = Field(description="Código identificable y estable del error.")
    message: str = Field(description="Mensaje legible y seguro para el consumidor.")
    request_id: str | None = Field(
        default=None, description="Identificador de la solicitud, si corresponde."
    )


class ErrorResponse(BaseModel):
    """Envoltura uniforme de errores."""

    error: ErrorDetail
