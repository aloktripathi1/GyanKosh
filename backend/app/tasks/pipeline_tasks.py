import uuid

from app.db import SessionLocal
from app.models.job import Job
from app.orchestrator.pipeline import run_pipeline


def run_job_in_background(job_id: str) -> None:
    """Entrypoint for FastAPI's BackgroundTasks: loads the job in its own DB
    session (the request-scoped session from the upload endpoint is closed by
    the time this runs) and hands it to the orchestrator. Runs in Starlette's
    threadpool, not the event loop — see documents.py.

    Retry/backoff/checkpointing happen inside run_pipeline, not here — a
    process restart just re-invokes the pipeline for any job still pending or
    running, which resumes from the last checkpointed stage rather than
    starting over."""
    db = SessionLocal()
    try:
        job = db.get(Job, uuid.UUID(job_id))
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        run_pipeline(db, job)
    finally:
        db.close()
