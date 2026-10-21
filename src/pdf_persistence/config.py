"""Configuración del microservicio mediante variables de entorno (12-Factor)."""

import os
from dataclasses import dataclass

DEFAULT_PORT = 8003


def _read_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} debe ser un entero, se recibió: {raw!r}") from None
    if value <= 0:
        raise ValueError(f"{name} debe ser un entero positivo, se recibió: {value}")
    return value


@dataclass(frozen=True)
class Settings:
    """Configuración inmutable de la aplicación.

    Toda la configuración proviene del entorno; los secretos nunca se
    escriben en el repositorio. Los valores predeterminados existen solo
    para el entorno de desarrollo local.
    """

    mongo_uri: str
    mongo_database: str
    mongo_collection: str
    mongo_timeout_ms: int
    log_level: str
    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        """Construye la configuración desde variables de entorno.

        Variables:
            MONGO_URI: URI de conexión a MongoDB (puede incluir credenciales).
            MONGO_DATABASE: nombre de la base de datos.
            MONGO_COLLECTION: nombre de la colección de documentos.
            MONGO_TIMEOUT_MS: timeout de conexión y selección de servidor.
            LOG_LEVEL: nivel de logging (INFO por defecto).
            PORT: puerto HTTP del servicio (8003 por defecto).

        Raises:
            ValueError: si alguna variable es inválida.
        """
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(
                f"LOG_LEVEL debe ser un nivel válido, se recibió: {log_level!r}"
            )
        return cls(
            mongo_uri=os.environ.get("MONGO_URI", "mongodb://localhost:27017").rstrip(
                "/"
            ),
            mongo_database=os.environ.get("MONGO_DATABASE", "pdf_persistence"),
            mongo_collection=os.environ.get("MONGO_COLLECTION", "documents"),
            mongo_timeout_ms=_read_int("MONGO_TIMEOUT_MS", 5000),
            log_level=log_level,
            port=_read_int("PORT", DEFAULT_PORT),
        )
