"""Route-level proof that the path-traversal fix and signed-URL scheme
actually work end-to-end through GET /files/{path}, not just at the storage
layer in isolation."""

import io

import pytest
from fastapi.testclient import TestClient

from app.api import files as files_module
from app.config import get_settings
from app.main import app
from app.storage.local_storage import LocalStorageBackend

API_KEY = get_settings().api_key


@pytest.fixture
def client(tmp_path, monkeypatch):
    backend = LocalStorageBackend(str(tmp_path))
    backend.save("tkp/job1/lesson_plans.pdf", io.BytesIO(b"%PDF-fake-content"))
    monkeypatch.setattr(files_module, "get_storage", lambda: backend)
    yield TestClient(app), backend


def test_legitimate_download_with_api_key_succeeds(client):
    test_client, _ = client
    response = test_client.get("/files/tkp/job1/lesson_plans.pdf", headers={"x-api-key": API_KEY})
    assert response.status_code == 200
    assert response.content == b"%PDF-fake-content"


def test_legitimate_download_with_signed_url_succeeds(client):
    test_client, backend = client
    signed_path = backend.url("tkp/job1/lesson_plans.pdf")  # "/files/...?expires=...&sig=..."
    response = test_client.get(signed_path)
    assert response.status_code == 200
    assert response.content == b"%PDF-fake-content"


def test_download_without_any_credentials_is_rejected(client):
    test_client, _ = client
    response = test_client.get("/files/tkp/job1/lesson_plans.pdf")
    assert response.status_code == 401


def test_download_with_tampered_signature_is_rejected(client):
    test_client, backend = client
    signed_path = backend.url("tkp/job1/lesson_plans.pdf")
    tampered = signed_path[:-4] + "0000"  # corrupt the last few hex chars of sig
    response = test_client.get(tampered)
    assert response.status_code == 401


def test_traversal_attempt_via_the_route_is_rejected_not_500(client):
    test_client, _ = client
    response = test_client.get(
        "/files/..%2F..%2F..%2Fetc%2Fpasswd",
        headers={"x-api-key": API_KEY},
    )
    # Either Starlette/httpx normalizes the encoded traversal before it
    # reaches our handler, or our own PathTraversalError->400 catches it —
    # either way this must never be a 200 with file content, and must never
    # be an unhandled 500.
    assert response.status_code in (400, 404)
