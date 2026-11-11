# pdf-extractext-persistence

Microservicio de persistencia de documentos procesados del ecosistema `pdf-extractext`,
desarrollado con Python, FastAPI y MongoDB (PyMongo).

## Responsabilidad

Almacenar, consultar, actualizar y eliminar (lógicamente) los documentos validados,
extraídos y resumidos por el orquestador. Cada documento se identifica por el
**checksum SHA-256** del PDF original, lo que hace el alta **idempotente**.

No valida PDFs, no extrae texto ni resume: es el destino final de la cadena
Validation → Extract → Summarize.

## Arquitectura

Tres capas con dependencias hacia adentro:

```
src/pdf_persistence/
├── api/                          # Capa de presentación (FastAPI)
│   ├── routes.py                 #   CRUD /documents, health, metrics
│   ├── middleware.py             #   Request-ID
│   ├── metrics.py                #   Métricas Prometheus
│   └── error_handlers.py         #   Mapeo dominio → HTTP
├── service/
│   └── document_use_case.py      # Casos de uso (create idempotente, get, list, update, delete)
├── domain/
│   ├── models.py                 # Document
│   ├── ports.py                  # DocumentRepository (Protocol)
│   └── errors.py                 # ConflictError, NotFoundError, RepositoryUnavailable…
├── infrastructure/
│   └── mongo_repository.py       # Adaptador pymongo (índice único por checksum, soft-delete)
├── app.py                        # create_app(): composition root
├── container.py                  # Inyección de dependencias
├── config.py / schemas.py / logging_config.py / main.py
```

## API

| Método | Ruta                      | Descripción                                              |
|--------|---------------------------|----------------------------------------------------------|
| GET    | `/health/live`            | Liveness                                                 |
| GET    | `/health/ready`           | Readiness: hace ping real a MongoDB (503 si falla)        |
| GET    | `/metrics`                | Métricas Prometheus                                      |
| POST   | `/documents`              | Alta (201; 200 si ya existe con datos idénticos; 409 conflicto) |
| GET    | `/documents`              | Listado paginado (`limit` 1..100, `offset`)               |
| GET    | `/documents/{checksum}`   | Detalle (404 si no existe)                                |
| PUT    | `/documents/{checksum}`   | Actualización de campos permitidos                        |
| DELETE | `/documents/{checksum}`   | Eliminación lógica (soft-delete)                          |

Errores JSON uniformes con `request_id`.

## Configuración

| Variable           | Default                      | Descripción                    |
|--------------------|------------------------------|--------------------------------|
| `PORT`             | `8003`                       | Puerto HTTP                    |
| `MONGO_URI`        | `mongodb://localhost:27017`  | URI de MongoDB                 |
| `MONGO_DATABASE`   | `pdf_persistence`            | Base de datos                  |
| `MONGO_COLLECTION` | `documents`                  | Colección                      |
| `MONGO_TIMEOUT_MS` | `5000`                       | Timeout de conexión a Mongo    |
| `LOG_LEVEL`        | `INFO`                       | Nivel de logs JSON             |

## Uso

Requiere [UV](https://docs.astral.sh/uv/) y MongoDB accesible en `MONGO_URI`.

```bash
uv sync
uv run python -m pdf_persistence.main
# o con Docker (usa la red externa compartida pdf-ecosystem-net):
docker compose up -d --build
```

## Tests

```bash
uv run pytest                        # unitarios (con fakes, sin Mongo)
uv run pytest -m integration --no-cov  # integración con MongoDB real (ver tests/integration/README.md)
```

Unitarios: API, casos de uso, repositorio Mongo (con fakes), configuración, logging.
Integración: driver real contra Mongo efímero (base `pdf_persistence_it_<id>`),
verifica índice único de checksum e idempotencia.
