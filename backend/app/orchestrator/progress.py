from sqlalchemy.orm import Session

from app.models.job import Job


def emit(db: Session, job: Job, stage: str, progress_pct: int) -> None:
    """Write progress onto the jobs row; the SSE endpoint polls this row for updates.
    Implemented fully (pub/sub or LISTEN/NOTIFY) in Milestone 4."""
    job.current_stage = stage
    job.progress_pct = progress_pct
    db.commit()


async def stream_job_progress(job_id: str, db_factory) -> None:
    """Async generator feeding the SSE endpoint. Implemented in Milestone 4."""
    raise NotImplementedError("SSE progress streaming lands in Milestone 4")
