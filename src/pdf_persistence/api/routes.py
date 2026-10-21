"""Rutas de la API: documentos, salud y métricas."""

import logging

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from pdf_persistence.api.metrics import render_metrics
from pdf_persistence.domain.errors import PersistenceError
from pdf_persistence.schemas import (
    CHECKSUM_PATTERN,
    DeleteResponse,
    DocumentCreateRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdateRequest,
    HealthResponse,
    ReadinessResponse,
)

logger = logging.getLogger("pdf_persistence.routes")

router = APIRouter()


def _use_case(request: Request):
    return request.app.state.container.use_case


def _document_json(document) -> dict:
    return DocumentResponse(
        checksum=document.checksum,
        checksum_algorithm=document.checksum_algorithm,
        filename=document.filename,
        content_type=document.content_type,
        file_size_bytes=document.file_size_bytes,
        text=document.text,
        summary=document.summary,
        page_count=document.page_count,
        model=document.model,
        metadata=document.metadata,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
        deleted=document.deleted,
        deleted_at=document.deleted_at.isoformat() if document.deleted_at else None,
    ).model_dump()


@router.get("/health/live", response_model=HealthResponse, summary="Liveness probe")
async def health_live() -> HealthResponse:
    """Indica que el proceso está vivo; no consulta dependencias."""
    return HealthResponse(status="alive")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={503: {"model": ReadinessResponse, "description": "No está listo."}},
)
async def health_ready(request: Request) -> Response:
    """Comprueba la conectividad real con MongoDB mediante un ping."""
    try:
        await _use_case(request).ping()
    except PersistenceError as exc:
        logger.warning("readiness_failed code=%s", exc.code)
        return JSONResponse(
            status_code=503,
            content=ReadinessResponse(
                status="not_ready", reason="MongoDB no está disponible."
            ).model_dump(),
        )
    return JSONResponse(
        content=ReadinessResponse(status="ready").model_dump(exclude_none=True)
    )


@router.get("/metrics", summary="Métricas Prometheus")
async def metrics() -> PlainTextResponse:
    """Expone las métricas del proceso en formato Prometheus."""
    return PlainTextResponse(
        content=render_metrics().decode("utf-8"),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.post(
    "/documents",
    status_code=201,
    response_model=DocumentResponse,
    summary="Registra un documento procesado",
    responses={
        200: {"description": "Repetición idempotente: datos idénticos ya registrados."},
        409: {"description": "Checksum existente con datos distintos."},
        422: {"description": "Datos de entrada inválidos."},
        503: {"description": "MongoDB no disponible."},
        504: {"description": "Timeout de MongoDB."},
    },
)
async def create_document(body: DocumentCreateRequest, request: Request) -> Response:
    """Crea un documento. Idempotente por checksum con datos idénticos."""
    logger.info(
        "create_document checksum=%s request_id=%s",
        body.checksum,
        getattr(request.state, "request_id", "-"),
    )
    document, created = await _use_case(request).create(body.model_dump())
    response = JSONResponse(
        status_code=201 if created else 200,
        content=_document_json(document),
    )
    response.headers["Location"] = f"/documents/{document.checksum}"
    return response


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="Lista documentos activos",
)
async def list_documents(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DocumentListResponse:
    """Lista documentos activos con paginación; excluye eliminados."""
    items, total = await _use_case(request).list(limit=limit, offset=offset)
    return DocumentListResponse(
        items=[DocumentResponse(**_document_json(document)) for document in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/documents/{checksum}",
    response_model=DocumentResponse,
    summary="Recupera un documento activo por checksum",
    responses={404: {"description": "Documento no encontrado."}},
)
async def get_document(
    request: Request,
    checksum: str = Path(pattern=CHECKSUM_PATTERN),
) -> DocumentResponse:
    """Recupera un documento activo por su checksum de negocio."""
    document = await _use_case(request).get(checksum)
    return DocumentResponse(**_document_json(document))


@router.put(
    "/documents/{checksum}",
    response_model=DocumentResponse,
    summary="Actualiza campos permitidos de un documento activo",
    responses={404: {"description": "Documento no encontrado."}},
)
async def update_document(
    request: Request,
    body: DocumentUpdateRequest,
    checksum: str = Path(pattern=CHECKSUM_PATTERN),
) -> DocumentResponse:
    """Actualiza únicamente los campos modificables del contrato."""
    patch = body.model_dump(exclude_unset=True)
    document = await _use_case(request).update(checksum, patch)
    return DocumentResponse(**_document_json(document))


@router.delete(
    "/documents/{checksum}",
    response_model=DeleteResponse,
    summary="Eliminación lógica de un documento",
    responses={404: {"description": "Documento no encontrado."}},
)
async def delete_document(
    request: Request,
    checksum: str = Path(pattern=CHECKSUM_PATTERN),
) -> DeleteResponse:
    """Marca el documento como eliminado; no se borra físicamente."""
    await _use_case(request).delete(checksum)
    return DeleteResponse(status="deleted", checksum=checksum)
