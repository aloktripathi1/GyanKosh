import uuid

from app.db import SessionLocal
from app.models.job import Job
from app.orchestrator.pipeline import run_pipeline
from app.tasks.celery_app import celery_app


@celery_app.task(name="tasks.run_job", bind=True, max_retries=0)
def run_job(self, job_id: str) -> None:
    """Celery entrypoint: loads the job, hands it to the orchestrator. Retry/
    backoff/checkpointing happen inside run_pipeline, not at the Celery level —
    a worker restart just re-invokes this task, which resumes from the last
    checkpointed stage rather than starting over."""
    db = SessionLocal()
    try:
        job = db.get(Job, uuid.UUID(job_id))
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        run_pipeline(db, job)
    finally:
        db.close()
