import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.db import SessionLocal, get_db
from app.models.document import Document
from app.models.job import Job
from app.models.tkp_version import TKPVersion
from app.schemas.entities import JobRead, JobSummary
from app.storage import get_storage

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_job_or_404(db: Session, job_id: uuid.UUID) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("", response_model=list[JobSummary], dependencies=[Depends(require_api_key)])
def list_jobs(db: Session = Depends(get_db), limit: int = 50) -> list[JobSummary]:
    """Library/History view: every past run, newest first — reuses data
    already stored at upload/classification time, no new agent call."""
    rows = (
        db.query(Job, Document)
        .join(Document, Job.document_id == Document.id)
        .order_by(Job.created_at.desc())
        .limit(limit)
        .all()
    )
    summaries = []
    for job, document in rows:
        classification = job.stage_results.get("classification") or {}
        publishing = job.stage_results.get("publishing") or {}
        summaries.append(
            JobSummary(
                id=job.id,
                document_filename=document.filename,
                subject=classification.get("subject"),
                topic=classification.get("topic"),
                status=job.status,
                tkp_version_id=publishing.get("tkp_version_id"),
                created_at=job.created_at,
            )
        )
    return summaries


@router.get("/{job_id}", response_model=JobRead, dependencies=[Depends(require_api_key)])
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> JobRead:
    return JobRead.from_job(_get_job_or_404(db, job_id))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_api_key)])
def delete_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """Removes a job (and its document, TKP version if any, and stored files)
    from history — for stuck/hung/abandoned runs that would otherwise sit in
    the Library forever with no way to clear them. FK order matters: TKPVersion
    references job_id, Job references document_id, so delete in that order."""
    job = _get_job_or_404(db, job_id)
    document = db.get(Document, job.document_id)

    db.query(TKPVersion).filter(TKPVersion.job_id == job_id).delete()
    db.delete(job)
    db.flush()
    if document is not None:
        storage = get_storage()
        try:
            storage.delete(document.storage_path)
        except FileNotFoundError:
            pass
        db.delete(document)
    db.commit()


@router.get("/{job_id}/stream", dependencies=[Depends(require_api_key)])
async def stream_job(job_id: uuid.UUID) -> StreamingResponse:
    """SSE progress stream: polls the jobs row every 2s and pushes a new event
    only when status/current_stage/progress_pct actually changes."""

    async def event_generator():
        last_snapshot = None
        while True:
            db = SessionLocal()
            try:
                job = db.get(Job, job_id)
                if job is None:
                    yield "event: error\ndata: job not found\n\n"
                    return
                snapshot = (job.status.value, job.current_stage, job.progress_pct)
                if snapshot != last_snapshot:
                    last_snapshot = snapshot
                    yield f"data: {JobRead.from_job(job).model_dump_json()}\n\n"
                if job.status.value in ("completed", "failed"):
                    return
            finally:
                db.close()
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
