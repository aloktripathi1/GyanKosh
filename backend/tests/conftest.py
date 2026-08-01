"""Shared fixtures for tests that exercise app.orchestrator.pipeline directly
(test_orchestrator.py, test_golden_fixtures.py) without a live Postgres
connection — see test_orchestrator.py's module docstring for why."""

import io

import pytest

from app.orchestrator import pipeline
from app.storage.local_storage import LocalStorageBackend


@pytest.fixture
def storage(tmp_path):
    backend = LocalStorageBackend(str(tmp_path))
    backend.save("doc.txt", io.BytesIO(b"Newton's second law: F=ma."))
    return backend


@pytest.fixture(autouse=True)
def patch_storage(monkeypatch, storage):
    monkeypatch.setattr(pipeline, "get_storage", lambda: storage)
    monkeypatch.setattr(pipeline, "BACKOFF_BASE_SECONDS", 0)
