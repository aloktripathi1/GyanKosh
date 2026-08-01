"""Proves the regenerate-section row lock (api/tkp.py's with_for_update())
actually blocks a second transaction, not just that the code calls the right
method. Every other test in this suite deliberately avoids a live Postgres
connection (see test_orchestrator.py's docstring) — this is the one
exception, because blocking behavior is a property of the database, not of
our Python code, and can't be proven any other way.

Skipped unless GYANKOSH_TEST_DATABASE_URL points at a real, disposable
Postgres database (migrated to head). Not run as part of the default `pytest`
invocation in environments without one available."""

import os
import threading
import time
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.document import Document
from app.models.job import Job
from app.models.tkp_version import TKPVersion

PG_URL = os.environ.get("GYANKOSH_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="requires GYANKOSH_TEST_DATABASE_URL (a live, migrated Postgres) to prove real lock-blocking behavior"
)


@pytest.fixture
def tkp_id():
    engine = create_engine(PG_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    document_id, job_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    document = Document(id=document_id, filename="concurrency-test.pdf", file_type="pdf", storage_path="x", content_hash=str(uuid.uuid4()))
    job = Job(id=job_id, document_id=document_id)
    session.add(document)
    session.add(job)
    session.flush()
    tkp = TKPVersion(id=version_id, job_id=job_id, version=1)
    session.add(tkp)
    session.commit()
    session.close()

    yield version_id, Session

    cleanup = Session()
    cleanup.query(TKPVersion).filter(TKPVersion.id == version_id).delete()
    cleanup.query(Job).filter(Job.id == job_id).delete()
    cleanup.query(Document).filter(Document.id == document_id).delete()
    cleanup.commit()
    cleanup.close()


def test_with_for_update_blocks_a_second_concurrent_transaction(tkp_id):
    """Two real transactions, two real DB connections, two real OS threads.
    Transaction A locks the TKP row and holds it; transaction B attempts the
    same lock and must not acquire it until A commits (releasing the lock) —
    exactly the regenerate-section race the audit flagged."""
    version_id, Session = tkp_id

    events: list[tuple[str, str, float]] = []
    events_lock = threading.Lock()

    def record(name: str, event: str) -> None:
        with events_lock:
            events.append((name, event, time.monotonic()))

    a_holds_lock = threading.Event()
    errors: list[Exception] = []
    HOLD_SECONDS = 1.0
    results: dict[str, float] = {}

    def txn_a():
        try:
            session = Session()
            record("A", "start")
            session.query(TKPVersion).filter(TKPVersion.id == version_id).with_for_update().first()
            record("A", "acquired")
            a_holds_lock.set()
            # Hold the row lock open for a known duration — simulates a
            # regenerate call that's slow (an LLM call) while still holding
            # its transaction open.
            time.sleep(HOLD_SECONDS)
            session.commit()
            record("A", "released")
            session.close()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def txn_b():
        try:
            a_holds_lock.wait(timeout=10)  # only attempt once A definitely holds the lock
            session = Session()
            record("B", "start")
            wait_start = time.monotonic()
            # This call must BLOCK at the database level until A commits.
            session.query(TKPVersion).filter(TKPVersion.id == version_id).with_for_update().first()
            results["b_wait_seconds"] = time.monotonic() - wait_start
            record("B", "acquired")
            session.commit()
            session.close()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    thread_a = threading.Thread(target=txn_a)
    thread_b = threading.Thread(target=txn_b)
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)

    assert not errors, f"unexpected error(s) in worker threads: {errors}"
    # Measured entirely on B's own thread clock (no cross-thread timestamp
    # comparison, which is racy under OS scheduling jitter even when the
    # underlying DB-level ordering is correct) — if with_for_update() were a
    # no-op, B's query would return in milliseconds instead of waiting out
    # most of A's hold.
    assert results["b_wait_seconds"] >= HOLD_SECONDS * 0.8, (
        f"B acquired the lock after only {results['b_wait_seconds']:.3f}s, "
        f"expected to wait close to {HOLD_SECONDS}s for A to release it — with_for_update() is not actually blocking"
    )
