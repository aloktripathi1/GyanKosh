"""API-level tests per Section 14: auth rejection on missing/invalid key,
upload rejection on wrong type/oversized/malformed file, 202 + job_id on a
valid upload. Uses FastAPI's TestClient against the real app/routes, with the
DB and background-task dependencies faked out (same "mock the boundary"
philosophy as the rest of this suite — no live Postgres needed)."""

import io
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api import documents as documents_module
from app.config import get_settings
from app.db import get_db
from app.main import app

API_KEY = get_settings().api_key


class _FakeQuery:
    def join(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return None


class _FakeDBSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        # Simulate the SQLAlchemy `default=uuid.uuid4` id column, which only
        # actually fires on a real flush against an engine.
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        # Simulate the server_default timestamp columns a real commit+refresh
        # would populate (created_at/updated_at/uploaded_at).
        now = datetime.now(UTC)
        for field in ("uploaded_at", "created_at", "updated_at"):
            if hasattr(obj, field) and getattr(obj, field) is None:
                setattr(obj, field, now)

    def get(self, model, id_):
        return None

    def query(self, *a, **k):
        return _FakeQuery()


class _FakeStorage:
    def save(self, key, data):
        return key


@pytest.fixture
def client(monkeypatch):
    def fake_get_db():
        yield _FakeDBSession()

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(documents_module, "get_storage", lambda: _FakeStorage())
    monkeypatch.setattr(documents_module, "run_job_in_background", lambda job_id: None)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


PDF_BYTES = b"%PDF-1.4\n%fake minimal pdf content for tests\n"


def test_upload_rejects_missing_api_key(client):
    response = client.post("/documents", files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")})
    assert response.status_code == 422  # FastAPI's Header(...) is required -> missing header is a validation error


def test_upload_rejects_invalid_api_key(client):
    response = client.post(
        "/documents",
        headers={"x-api-key": "wrong-key"},
        files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 401


def test_get_job_rejects_invalid_api_key(client):
    import uuid

    response = client.get(f"/jobs/{uuid.uuid4()}", headers={"x-api-key": "wrong-key"})
    assert response.status_code == 401


def test_upload_rejects_unsupported_content_type(client):
    response = client.post(
        "/documents",
        headers={"x-api-key": API_KEY},
        files={"file": ("doc.exe", io.BytesIO(b"MZ\x90\x00"), "application/x-msdownload")},
    )
    assert response.status_code == 415


def test_upload_rejects_oversized_file(client, monkeypatch):
    # Exercise the boundary check without actually moving 25MB through the
    # in-process test client — the limit itself is just a comparison.
    monkeypatch.setattr(documents_module, "MAX_UPLOAD_BYTES", 10)
    response = client.post(
        "/documents",
        headers={"x-api-key": API_KEY},
        files={"file": ("doc.txt", io.BytesIO(b"a" * 11), "text/plain")},
    )
    assert response.status_code == 413


def test_upload_rejects_empty_file(client):
    response = client.post(
        "/documents",
        headers={"x-api-key": API_KEY},
        files={"file": ("doc.txt", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_content_type_bytes_mismatch(client):
    """A .pdf-labeled upload whose bytes aren't actually a PDF (Section 15:
    wrong file extension/type vs actual content)."""
    response = client.post(
        "/documents",
        headers={"x-api-key": API_KEY},
        files={"file": ("doc.pdf", io.BytesIO(b"this is actually just plain text"), "application/pdf")},
    )
    assert response.status_code == 400
    assert "doesn't match" in response.json()["detail"]


def test_upload_rejects_unknown_document_type_hint(client):
    response = client.post(
        "/documents",
        headers={"x-api-key": API_KEY},
        data={"document_type_hint": "not_a_real_hint"},
        files={"file": ("doc.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


def test_valid_upload_returns_202_with_job_id(client):
    response = client.post(
        "/documents",
        headers={"x-api-key": API_KEY},
        files={"file": ("doc.txt", io.BytesIO(b"Newton's second law: F=ma."), "text/plain")},
    )
    assert response.status_code == 202
    body = response.json()
    assert "job_id" in body
    assert body["document"]["filename"] == "doc.txt"


def test_valid_pdf_upload_passes_magic_byte_check(client):
    response = client.post(
        "/documents",
        headers={"x-api-key": API_KEY},
        files={"file": ("doc.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 202
