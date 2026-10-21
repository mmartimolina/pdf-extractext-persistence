"""Excepciones específicas del dominio con código estable y estado HTTP.

Cada excepción transporta un ``code`` identificable, un ``message`` apto
para el consumidor y el ``status_code`` HTTP asociado. Nunca incluyen
secretos, URIs con credenciales ni contenido de los documentos.
"""

from typing import Final


class PersistenceError(Exception):
    """Error base del microservicio.

    Args:
        message: mensaje legible y seguro para el consumidor.
        status_code: estado HTTP asociado.
    """

    code: Final[str] = "PERSISTENCE_ERROR"

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DocumentNotFoundError(PersistenceError):
    """No existe un documento activo con el checksum solicitado."""

    code = "DOCUMENT_NOT_FOUND"

    def __init__(self, checksum: str) -> None:
        super().__init__(
            f"No existe un documento activo con checksum {checksum}.",
            status_code=404,
        )
        self.checksum = checksum


class DuplicateChecksumError(PersistenceError):
    """Señal interna del repositorio: el índice único rechazó la inserción."""

    code = "DUPLICATE_CHECKSUM"

    def __init__(self, checksum: str) -> None:
        super().__init__(
            f"El checksum {checksum} ya está registrado.",
            status_code=409,
        )
        self.checksum = checksum


class DocumentAlreadyExistsError(PersistenceError):
    """Ya existe un documento con el checksum y datos distintos."""

    code = "DOCUMENT_ALREADY_EXISTS"

    def __init__(self, checksum: str) -> None:
        super().__init__(
            f"Ya existe un documento registrado con checksum {checksum} "
            "y datos distintos. Use PUT /documents/{checksum} para "
            "actualizarlo.",
            status_code=409,
        )
        self.checksum = checksum


class EmptyUpdateError(PersistenceError):
    """La actualización no contiene ningún campo modificable."""

    code = "EMPTY_UPDATE"

    def __init__(self) -> None:
        super().__init__(
            "La actualización debe incluir al menos un campo.",
            status_code=422,
        )


class MongoUnavailableError(PersistenceError):
    """MongoDB no está accesible."""

    code = "MONGO_UNAVAILABLE"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message or "La base de datos MongoDB no está disponible.",
            status_code=503,
        )


class MongoTimeoutError(PersistenceError):
    """La operación con MongoDB superó el timeout configurado."""

    code = "MONGO_TIMEOUT"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message or "La operación con MongoDB superó el tiempo límite.",
            status_code=504,
        )


class InternalError(PersistenceError):
    """Error interno no anticipado."""

    code = "INTERNAL_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__("Error interno del servicio.", status_code=500)
