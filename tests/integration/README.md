# Pruebas de integración con MongoDB real

Estas pruebas validan el comportamiento real del driver, los índices y
la unicidad del checksum contra un servidor MongoDB. Están marcadas con
el marcador `integration` y **se omiten automáticamente** cuando no está
configurada la variable `TEST_MONGO_URI`, de modo que `uv run pytest`
queda libre de dependencias externas.

## Prerrequisitos

- Docker (recomendado) o un servidor MongoDB accesible.
- No se necesitan credenciales para el entorno local de pruebas.

## Procedimiento con Docker

```powershell
# 1. Levantar un MongoDB aislado y efímero (solo para pruebas)
docker run --rm -d --name pdf-persistence-it -p 27017:27017 mongo:8

# 2. Ejecutar solo las pruebas de integración
$env:TEST_MONGO_URI = "mongodb://localhost:27017"
uv run pytest -m integration --no-cov

# 3. Detener y eliminar el contenedor efímero
docker stop pdf-persistence-it
```

Cada prueba crea una base de datos única (`pdf_persistence_it_<id>`) que
se elimina al terminar, por lo que las pruebas son reproducibles y no
contaminan otros entornos.

## Notas

- La suite unitaria (`uv run pytest` sin marcador) no necesita MongoDB
  ni conexión a Internet: usa dobles de prueba del puerto
  `DocumentRepository`.
- No ejecute las pruebas de integración contra una base de datos de
  producción.
