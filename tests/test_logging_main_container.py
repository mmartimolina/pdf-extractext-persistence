"""Pruebas de logging JSON, punto de entrada y contenedor real."""

import json
import logging

from tests.conftest import make_settings

from pdf_persistence.container import Container
from pdf_persistence.infrastructure.mongo_repository import MongoRepository
from pdf_persistence.logging_config import (
    JsonFormatter,
    configure_logging,
    log_level_from_name,
)


class TestLogging:
    def test_validation_message_with_no_errors_falls_back(self):
        from fastapi.exceptions import RequestValidationError

        from pdf_persistence.api.error_handlers import _validation_message

        exc = RequestValidationError([])
        assert _validation_message(exc) == "Los datos de la solicitud no son válidos."

    def test_validation_message_includes_location_and_type(self):
        from fastapi.exceptions import RequestValidationError

        from pdf_persistence.api.error_handlers import _validation_message

        exc = RequestValidationError(
            [{"loc": ("body", "checksum"), "type": "string_pattern_mismatch"}]
        )
        message = _validation_message(exc)
        assert "body.checksum" in message
        assert "string_pattern_mismatch" in message

    def test_json_formatter_produces_single_line_json(self):
        record = logging.LogRecord(
            name="pdf_test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="mensaje %s",
            args=("con valor",),
            exc_info=None,
        )
        line = JsonFormatter().format(record)
        payload = json.loads(line)
        assert payload["level"] == "INFO"
        assert payload["logger"] == "pdf_test"
        assert payload["message"] == "mensaje con valor"
        assert payload["timestamp"]

    def test_json_formatter_includes_exception(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="pdf_test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="fallo",
                args=(),
                exc_info=sys.exc_info(),
            )
        payload = json.loads(JsonFormatter().format(record))
        assert "ValueError: boom" in payload["exception"]

    def test_configure_logging_sets_root_handler(self):
        configure_logging(logging.WARNING)
        root = logging.getLogger()
        assert root.level == logging.WARNING
        assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)

    def test_log_level_from_name(self):
        assert log_level_from_name("info") == logging.INFO
        assert log_level_from_name("BOGUS") == logging.INFO


class TestContainer:
    def test_build_creates_mongo_repository(self):
        container = Container.build(make_settings())
        assert isinstance(container.repository, MongoRepository)
        assert container.use_case is not None

    async def test_aclose_closes_repository(self):
        repository = MongoRepository(
            "mongodb://localhost:27017", "db", "col", timeout_ms=100
        )
        closed = []

        async def fake_aclose():
            closed.append(True)

        repository.aclose = fake_aclose
        container = Container(
            repository=repository,
            use_case=None,
        )
        await container.aclose()
        assert closed == [True]


class TestMain:
    def test_main_module_creates_app(self, monkeypatch):
        import importlib

        monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
        monkeypatch.setenv("MONGO_DATABASE", "main_test")
        monkeypatch.setenv("PORT", "8003")
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        import pdf_persistence.main as main_module

        main_module = importlib.reload(main_module)
        assert main_module.app is not None
        assert main_module.app.state.settings.mongo_database == "main_test"

    def test_create_app_without_args_reads_env(self, monkeypatch):
        from pdf_persistence.app import create_app

        monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
        monkeypatch.setenv("MONGO_DATABASE", "env_db")
        monkeypatch.setenv("PORT", "8003")
        app = create_app()
        assert app.state.settings.mongo_database == "env_db"
        assert isinstance(app.state.container.repository, MongoRepository)
