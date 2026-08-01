from sqlalchemy.orm import Session

from app.models.job import Job


def emit(db: Session, job: Job, stage: str, progress_pct: int) -> None:
    """Write progress onto the jobs row; GET /jobs/{id}/stream polls this row
    (app/api/jobs.py) and pushes changes to the client over SSE."""
    job.current_stage = stage
    job.progress_pct = progress_pct
    db.commit()
