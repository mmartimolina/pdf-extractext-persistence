"""Fixtures compartidas de las pruebas."""

import pytest
from fastapi.testclient import TestClient
from tests.fakes import FakeRepository

from pdf_persistence.config import Settings
from pdf_persistence.container import Container
from pdf_persistence.service.document_use_case import DocumentUseCase


def make_settings(**overrides) -> Settings:
    """Construye ``Settings`` con valores por defecto y overrides."""
    defaults = dict(
        mongo_uri="mongodb://localhost:27017",
        mongo_database="pdf_persistence_test",
        mongo_collection="documents",
        mongo_timeout_ms=5000,
        log_level="INFO",
        port=8003,
    )
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def repository() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def container(repository) -> Container:
    return Container(
        repository=repository,
        use_case=DocumentUseCase(repository=repository),
    )


@pytest.fixture
def client(repository, container) -> TestClient:
    """Cliente HTTP con el ciclo de vida completo de la aplicación."""
    from pdf_persistence.app import create_app

    app = create_app(settings=make_settings(), container=container)
    with TestClient(app) as test_client:
        yield test_client
    assert repository.closed, "el repositorio debe cerrarse al apagar"
