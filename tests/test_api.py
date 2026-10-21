"""Pruebas del contrato HTTP del microservicio."""

from tests.conftest import make_settings

from pdf_persistence.domain.errors import MongoTimeoutError, MongoUnavailableError

CHECKSUM = "ab" * 32
OTHER_CHECKSUM = "cd" * 32

CREATE_BODY = {
    "checksum": CHECKSUM,
    "checksum_algorithm": "sha256",
    "filename": "informe.pdf",
    "content_type": "application/pdf",
    "file_size_bytes": 2048,
    "text": "contenido textual del documento",
    "page_count": 2,
}


def _create(client, body=CREATE_BODY):
    return client.post("/documents", json=body)


class TestCreateDocument:
    def test_create_returns_201_with_document(self, client):
        response = _create(client)
        assert response.status_code == 201
        document = response.json()
        assert document["checksum"] == CHECKSUM
        assert document["checksum_algorithm"] == "sha256"
        assert document["filename"] == "informe.pdf"
        assert document["deleted"] is False
        assert document["deleted_at"] is None
        assert document["created_at"]
        assert document["updated_at"]
        assert response.headers["location"] == f"/documents/{CHECKSUM}"

    def test_create_idempotent_replay_returns_200(self, client):
        assert _create(client).status_code == 201
        replay = _create(client)
        assert replay.status_code == 200
        assert replay.json()["checksum"] == CHECKSUM

    def test_create_conflict_on_different_payload(self, client):
        _create(client)
        response = _create(client, {**CREATE_BODY, "filename": "otro.pdf"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DOCUMENT_ALREADY_EXISTS"

    def test_create_rejects_invalid_checksum(self, client):
        response = _create(client, {**CREATE_BODY, "checksum": "not-hex!"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REQUEST"

    def test_create_rejects_unknown_fields(self, client):
        response = _create(client, {**CREATE_BODY, "unexpected": "x"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REQUEST"

    def test_create_requires_checksum(self, client):
        response = _create(
            client, {k: v for k, v in CREATE_BODY.items() if k != "checksum"}
        )
        assert response.status_code == 422

    def test_create_mongo_unavailable_returns_503(self, client, repository):
        repository.fail_mode = MongoUnavailableError()
        response = _create(client)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "MONGO_UNAVAILABLE"

    def test_create_mongo_timeout_returns_504(self, client, repository):
        repository.fail_mode = MongoTimeoutError()
        response = _create(client)
        assert response.status_code == 504
        assert response.json()["error"]["code"] == "MONGO_TIMEOUT"


class TestGetDocument:
    def test_get_returns_document(self, client):
        _create(client)
        response = client.get(f"/documents/{CHECKSUM}")
        assert response.status_code == 200
        assert response.json()["checksum"] == CHECKSUM

    def test_get_missing_returns_404(self, client):
        response = client.get(f"/documents/{OTHER_CHECKSUM}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

    def test_get_deleted_returns_404(self, client):
        _create(client)
        client.delete(f"/documents/{CHECKSUM}")
        assert client.get(f"/documents/{CHECKSUM}").status_code == 404

    def test_get_invalid_checksum_returns_422(self, client):
        response = client.get("/documents/short")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


class TestListDocuments:
    def test_list_returns_items_and_total(self, client):
        _create(client)
        _create(client, {**CREATE_BODY, "checksum": OTHER_CHECKSUM})
        response = client.get("/documents")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["limit"] == 20
        assert body["offset"] == 0
        assert len(body["items"]) == 2

    def test_list_paginates(self, client):
        for i in range(3):
            _create(client, {**CREATE_BODY, "checksum": f"{i:064x}"})
        response = client.get("/documents", params={"limit": 2, "offset": 2})
        body = response.json()
        assert body["total"] == 3
        assert len(body["items"]) == 1
        assert body["limit"] == 2
        assert body["offset"] == 2

    def test_list_rejects_invalid_pagination(self, client):
        assert client.get("/documents", params={"limit": 0}).status_code == 422
        assert client.get("/documents", params={"limit": 101}).status_code == 422
        assert client.get("/documents", params={"offset": -1}).status_code == 422

    def test_list_excludes_deleted(self, client):
        _create(client)
        client.delete(f"/documents/{CHECKSUM}")
        body = client.get("/documents").json()
        assert body["total"] == 0
        assert body["items"] == []


class TestUpdateDocument:
    def test_update_changes_allowed_fields(self, client):
        _create(client)
        response = client.put(
            f"/documents/{CHECKSUM}", json={"summary": "resumen generado"}
        )
        assert response.status_code == 200
        document = response.json()
        assert document["summary"] == "resumen generado"
        assert document["filename"] == "informe.pdf"
        assert document["checksum"] == CHECKSUM

    def test_update_touches_updated_at(self, client, repository):
        _create(client)
        before = repository.documents[CHECKSUM].updated_at
        client.put(f"/documents/{CHECKSUM}", json={"summary": "s"})
        after = repository.documents[CHECKSUM].updated_at
        assert after >= before
        assert after != before or before == after

    def test_update_empty_body_rejected(self, client):
        _create(client)
        response = client.put(f"/documents/{CHECKSUM}", json={})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "EMPTY_UPDATE"

    def test_update_rejects_checksum_change(self, client):
        _create(client)
        response = client.put(
            f"/documents/{CHECKSUM}", json={"checksum": OTHER_CHECKSUM}
        )
        assert response.status_code == 422

    def test_update_missing_returns_404(self, client):
        response = client.put(f"/documents/{OTHER_CHECKSUM}", json={"summary": "s"})
        assert response.status_code == 404

    def test_update_deleted_returns_404(self, client):
        _create(client)
        client.delete(f"/documents/{CHECKSUM}")
        response = client.put(f"/documents/{CHECKSUM}", json={"summary": "s"})
        assert response.status_code == 404


class TestDeleteDocument:
    def test_delete_returns_confirmation(self, client):
        _create(client)
        response = client.delete(f"/documents/{CHECKSUM}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "deleted"
        assert body["checksum"] == CHECKSUM

    def test_delete_is_soft(self, client, repository):
        _create(client)
        client.delete(f"/documents/{CHECKSUM}")
        stored = repository.documents[CHECKSUM]
        assert stored.deleted is True
        assert stored.deleted_at is not None

    def test_delete_twice_returns_404(self, client):
        _create(client)
        assert client.delete(f"/documents/{CHECKSUM}").status_code == 200
        assert client.delete(f"/documents/{CHECKSUM}").status_code == 404


class TestHealth:
    def test_health_live(self, client):
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_health_ready_with_real_ping(self, client):
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    def test_health_ready_fails_when_mongo_down(self, client, repository):
        repository.fail_mode = MongoUnavailableError()
        response = client.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["reason"]


class TestObservability:
    def test_metrics_exposes_prometheus_format(self, client):
        _create(client)
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "pdf_persistence_requests_total" in response.text
        assert "/documents" in response.text

    def test_request_id_echoed_when_provided(self, client):
        response = client.get("/health/live", headers={"X-Request-ID": "abc-123"})
        assert response.headers["X-Request-ID"] == "abc-123"

    def test_request_id_generated_when_missing(self, client):
        response = client.get("/health/live")
        assert response.headers["X-Request-ID"]

    def test_error_response_includes_request_id(self, client):
        response = client.get(f"/documents/{OTHER_CHECKSUM}")
        request_id = response.headers["X-Request-ID"]
        assert response.json()["error"]["request_id"] == request_id

    async def test_unexpected_error_returns_internal_error_json(
        self, repository, container
    ):
        import httpx

        from pdf_persistence.app import create_app

        app = create_app(settings=make_settings(), container=container)
        async with app.router.lifespan_context(app):
            repository.fail_mode = RuntimeError("boom-detalle-interno")
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as http_client:
                response = await http_client.post("/documents", json=CREATE_BODY)
        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert "boom-detalle-interno" not in response.text
        assert "Traceback" not in response.text


class TestLifecycle:
    def test_indexes_ensured_on_startup(self, client, repository):
        assert repository.indexes_ensured is True

    def test_app_starts_even_if_indexes_fail(self, repository, container):
        repository.fail_mode = MongoUnavailableError()
        from fastapi.testclient import TestClient

        from pdf_persistence.app import create_app

        app = create_app(settings=make_settings(), container=container)
        with TestClient(app) as test_client:
            assert test_client.get("/health/live").status_code == 200
        repository.fail_mode = None
