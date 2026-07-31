from sqlalchemy.orm import Session

from app.models.job import STAGE_NAMES, Job, JobStatus

MAX_RETRIES = 3


class StageFailedError(Exception):
    def __init__(self, stage: str, cause: Exception):
        self.stage = stage
        self.cause = cause
        super().__init__(f"Stage '{stage}' failed after {MAX_RETRIES} attempts: {cause}")


def next_stage(job: Job) -> str | None:
    """Resume point: first stage in STAGE_NAMES not yet present in job.stage_results."""
    for stage in STAGE_NAMES:
        if stage not in job.stage_results:
            return stage
    return None


def run_stage(db: Session, job: Job, stage: str) -> None:
    """Execute one stage with retry/backoff, checkpoint the result on success, and mark
    the job failed (explicitly, never silently) on exhaustion. Stage execution itself is
    wired to the agents/ modules in Milestone 2-3; this function owns only sequencing,
    retry, and checkpointing per Section 10's convention that agents stay pure functions."""
    raise NotImplementedError("Orchestrator stage execution lands in Milestone 4")


def run_pipeline(db: Session, job: Job) -> None:
    """Drive the job from its current checkpoint to completion, one stage at a time."""
    job.status = JobStatus.RUNNING
    db.commit()

    stage = next_stage(job)
    while stage is not None:
        job.current_stage = stage
        db.commit()
        run_stage(db, job, stage)
        stage = next_stage(job)

    job.status = JobStatus.COMPLETED
    job.progress_pct = 100
    db.commit()
