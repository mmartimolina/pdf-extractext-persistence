"""Pruebas de la configuración por variables de entorno."""

import pytest

from pdf_persistence.config import Settings


def _clear_env(monkeypatch):
    for name in (
        "MONGO_URI",
        "MONGO_DATABASE",
        "MONGO_COLLECTION",
        "MONGO_TIMEOUT_MS",
        "LOG_LEVEL",
        "PORT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_for_local_development(monkeypatch):
    _clear_env(monkeypatch)
    settings = Settings.from_env()
    assert settings.mongo_uri == "mongodb://localhost:27017"
    assert settings.mongo_database == "pdf_persistence"
    assert settings.mongo_collection == "documents"
    assert settings.mongo_timeout_ms == 5000
    assert settings.log_level == "INFO"
    assert settings.port == 8003


def test_reads_overrides(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://mongo:27017")
    monkeypatch.setenv("MONGO_DATABASE", "prod_db")
    monkeypatch.setenv("MONGO_COLLECTION", "docs")
    monkeypatch.setenv("MONGO_TIMEOUT_MS", "250")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("PORT", "9001")
    settings = Settings.from_env()
    assert settings.mongo_uri == "mongodb://mongo:27017"
    assert settings.mongo_database == "prod_db"
    assert settings.mongo_collection == "docs"
    assert settings.mongo_timeout_ms == 250
    assert settings.log_level == "DEBUG"
    assert settings.port == 9001


def test_strips_trailing_slash_from_uri(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MONGO_URI", "mongodb://mongo:27017/")
    assert Settings.from_env().mongo_uri == "mongodb://mongo:27017"


def test_invalid_timeout_rejected(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MONGO_TIMEOUT_MS", "not-a-number")
    with pytest.raises(ValueError, match="MONGO_TIMEOUT_MS"):
        Settings.from_env()


def test_non_positive_timeout_rejected(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MONGO_TIMEOUT_MS", "0")
    with pytest.raises(ValueError, match="MONGO_TIMEOUT_MS"):
        Settings.from_env()


def test_invalid_port_rejected(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("PORT", "-1")
    with pytest.raises(ValueError, match="PORT"):
        Settings.from_env()


def test_invalid_log_level_rejected(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "CHATTY")
    with pytest.raises(ValueError, match="LOG_LEVEL"):
        Settings.from_env()
