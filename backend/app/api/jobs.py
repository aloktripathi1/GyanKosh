import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.db import SessionLocal, get_db
from app.models.job import Job
from app.schemas.entities import JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_job_or_404(db: Session, job_id: uuid.UUID) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/{job_id}", response_model=JobRead, dependencies=[Depends(require_api_key)])
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> JobRead:
    return JobRead.from_job(_get_job_or_404(db, job_id))


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
