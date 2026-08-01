import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api import jobs as jobs_api
from app.models.document import Document
from app.models.job import Job, JobStatus
from app.models.tkp_version import TKPVersion


class _FakeMultiEntityQuery:
    def __init__(self, rows):
        self._rows = rows

    def join(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *entities):
        assert entities == (Job, Document)
        return _FakeMultiEntityQuery(self._rows)


def _job_and_doc(*, filename, subject=None, tkp_version_id=None, status=JobStatus.COMPLETED):
    document = Document(id=uuid.uuid4(), filename=filename, file_type="pdf", storage_path="x", content_hash="h")
    job = Job(id=uuid.uuid4(), document_id=document.id, status=status)
    job.created_at = datetime.now(UTC)
    job.stage_results = {}
    if subject:
        job.stage_results["classification"] = {"subject": subject, "topic": "Photosynthesis"}
    if tkp_version_id:
        job.stage_results["publishing"] = {"tkp_version_id": str(tkp_version_id)}
    return job, document


def test_list_jobs_returns_newest_first_with_classification_and_tkp_link():
    tkp_id = uuid.uuid4()
    job1, doc1 = _job_and_doc(filename="chapter1.pdf", subject="Biology", tkp_version_id=tkp_id)
    job2, doc2 = _job_and_doc(filename="chapter2.pdf", status=JobStatus.RUNNING)
    db = _FakeSession([(job1, doc1), (job2, doc2)])

    result = jobs_api.list_jobs(db)

    assert len(result) == 2
    assert result[0].document_filename == "chapter1.pdf"
    assert result[0].subject == "Biology"
    assert result[0].topic == "Photosynthesis"
    assert result[0].tkp_version_id == tkp_id
    assert result[1].document_filename == "chapter2.pdf"
    assert result[1].subject is None
    assert result[1].tkp_version_id is None


def test_list_jobs_handles_empty_history():
    db = _FakeSession([])
    assert jobs_api.list_jobs(db) == []


class _FakeTKPQuery:
    def __init__(self):
        self.deleted = False

    def filter(self, *a, **k):
        return self

    def delete(self):
        self.deleted = True


class _FakeDeleteSession:
    def __init__(self, job=None, document=None):
        self._job = job
        self._document = document
        self.deleted_objects = []
        self.tkp_query = _FakeTKPQuery()

    def get(self, model, id_):
        if model is Job:
            return self._job if self._job is not None and id_ == self._job.id else None
        if model is Document:
            return self._document
        return None

    def query(self, model):
        assert model is TKPVersion
        return self.tkp_query

    def delete(self, obj):
        self.deleted_objects.append(obj)

    def flush(self):
        pass

    def commit(self):
        pass


def test_delete_job_removes_job_document_tkp_versions_and_stored_file(monkeypatch):
    document = Document(id=uuid.uuid4(), filename="x.pdf", file_type="pdf", storage_path="documents/x/x.pdf", content_hash="h")
    job = Job(id=uuid.uuid4(), document_id=document.id, status=JobStatus.RUNNING)
    db = _FakeDeleteSession(job, document)

    deleted_paths = []

    class _FakeStorage:
        def delete(self, path):
            deleted_paths.append(path)

    monkeypatch.setattr(jobs_api, "get_storage", lambda: _FakeStorage())

    jobs_api.delete_job(job.id, db)

    assert db.tkp_query.deleted, "must delete any TKPVersion rows referencing this job (FK: job_id)"
    assert job in db.deleted_objects
    assert document in db.deleted_objects
    assert deleted_paths == ["documents/x/x.pdf"]


def test_delete_job_404s_for_unknown_job():
    db = _FakeDeleteSession()
    with pytest.raises(HTTPException) as exc_info:
        jobs_api.delete_job(uuid.uuid4(), db)
    assert exc_info.value.status_code == 404
