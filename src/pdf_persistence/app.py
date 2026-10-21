"""Fábrica de la aplicación FastAPI del microservicio de persistencia."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pdf_persistence.api.error_handlers import register_exception_handlers
from pdf_persistence.api.middleware import (
    ObservabilityMiddleware,
    RequestIdMiddleware,
)
from pdf_persistence.api.routes import router
from pdf_persistence.config import Settings
from pdf_persistence.container import Container
from pdf_persistence.domain.errors import PersistenceError

logger = logging.getLogger("pdf_persistence.app")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Crea y destruye las dependencias externas de la aplicación.

    Si MongoDB no está disponible durante el arranque, el servicio sigue
    iniciando (readiness reportará ``not_ready``) y los errores de
    negocio se responden de forma controlada.
    """
    container: Container = app.state.container
    logger.info("startup")
    try:
        await container.ensure_indexes()
    except PersistenceError as exc:
        logger.warning("index_initialization_failed code=%s", exc.code)
    yield
    await container.aclose()
    logger.info("shutdown")


def create_app(
    settings: Settings | None = None,
    container: Container | None = None,
) -> FastAPI:
    """Construye la aplicación FastAPI.

    Args:
        settings: configuración explícita; si se omite se lee del entorno.
        container: contenedor de dependencias explícito para pruebas;
            si se omite se construye uno real a partir de la configuración.
    """
    if settings is None:
        settings = Settings.from_env()
    if container is None:
        container = Container.build(settings)

    app = FastAPI(
        title="pdf-persistence",
        summary=(
            "Microservicio de persistencia de documentos procesados "
            "del ecosistema pdf-extractext."
        ),
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.container = container
    app.include_router(router)
    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    return app
