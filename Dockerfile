# syntax=docker/dockerfile:1
# Imagen de producción del microservicio pdf-persistence.

FROM ghcr.io/astral-sh/uv:0.11.3 AS uv

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=uv /uv /usr/local/bin/uv

# Instalación reproducible de dependencias desde pyproject.toml y uv.lock.
# No requiere MongoDB ni servicios externos: la imagen se construye sola.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src

RUN groupadd --system app && useradd --system --gid app app \
    && chown -R app:app /app
USER app

# El puerto HTTP se controla con PORT (8003 por defecto).
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PORT=8003

EXPOSE 8003

# Healthcheck de liveness sobre el puerto configurado.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8003') + '/health/live', timeout=4)" || exit 1

# main.py lee PORT del entorno y arranca uvicorn con él (12-Factor).
CMD ["python", "-m", "pdf_persistence.main"]
