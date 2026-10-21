"""Punto de entrada del microservicio para ejecución con uvicorn."""

import uvicorn

from pdf_persistence.app import create_app
from pdf_persistence.config import Settings
from pdf_persistence.logging_config import configure_logging, log_level_from_name

settings = Settings.from_env()
configure_logging(log_level_from_name(settings.log_level))

app = create_app(settings)

if __name__ == "__main__":  # pragma: no cover
    # Punto de entrada de ejecución directa; en producción se usa
    # ``uvicorn pdf_persistence.main:app``.
    uvicorn.run(
        "pdf_persistence.main:app",
        host="0.0.0.0",
        port=settings.port,
        log_config=None,
    )
