"""Manejo centralizado de excepciones con formato JSON uniforme."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pdf_persistence.domain.errors import InternalError, PersistenceError
from pdf_persistence.schemas import ErrorDetail

logger = logging.getLogger("pdf_persistence.errors")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_response(status_code: int, detail: ErrorDetail) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": detail.model_dump()},
    )


def _validation_message(exc: RequestValidationError) -> str:
    """Construye un mensaje seguro a partir de los errores de validación.

    No se incluye el valor recibido: podría contener texto documental
    completo u otros datos sensibles.
    """
    errors = exc.errors()
    if not errors:
        return "Los datos de la solicitud no son válidos."
    first = errors[0]
    location = ".".join(str(part) for part in first.get("loc", []))
    return f"Datos inválidos en {location or 'la solicitud'} ({first.get('type')})."


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los manejadores de errores de la aplicación."""

    @app.exception_handler(PersistenceError)
    async def handle_domain_error(
        request: Request, exc: PersistenceError
    ) -> JSONResponse:
        logger.warning(
            "domain_error code=%s status=%d request_id=%s",
            exc.code,
            exc.status_code,
            _request_id(request),
        )
        return _error_response(
            exc.status_code,
            ErrorDetail(
                code=exc.code, message=exc.message, request_id=_request_id(request)
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            422,
            ErrorDetail(
                code="INVALID_REQUEST",
                message=_validation_message(exc),
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception request_id=%s", _request_id(request))
        internal = InternalError(str(exc))
        return _error_response(
            internal.status_code,
            ErrorDetail(
                code=internal.code,
                message=internal.message,
                request_id=_request_id(request),
            ),
        )
