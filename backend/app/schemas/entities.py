import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_type: str
    storage_path: str
    content_hash: str
    document_type_hint: str | None = None
    uploaded_at: datetime


class DocumentCreateResponse(BaseModel):
    document: DocumentRead
    job_id: uuid.UUID


class JobRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: JobStatus
    current_stage: str | None
    progress_pct: int
    error: str | None
    tkp_version_id: uuid.UUID | None = None
    stage_timings: dict = {}
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job) -> "JobRead":
        publishing = job.stage_results.get("publishing") if job.stage_results else None
        tkp_version_id = publishing.get("tkp_version_id") if publishing else None
        return cls(
            id=job.id,
            document_id=job.document_id,
            status=job.status,
            current_stage=job.current_stage,
            progress_pct=job.progress_pct,
            error=job.error,
            tkp_version_id=tkp_version_id,
            stage_timings=job.stage_timings or {},
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class TKPVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    version: int
    classification: dict | None
    extracted_knowledge: dict | None
    teaching_plan: dict | None
    period_content: dict | None
    activities: dict | None
    assessments: dict | None
    learning_gaps: dict | None
    validation_report: dict | None
    pdf_paths: dict | None
    published_at: datetime | None


class RegenerateSectionRequest(BaseModel):
    reason: str | None = None


class JobSummary(BaseModel):
    """One row of the Library/History view — deliberately thin, everything
    here is already stored (document filename, classification subject/topic
    once available, job status), no new agent call or heavy join needed."""

    id: uuid.UUID
    document_filename: str
    subject: str | None = None
    topic: str | None = None
    status: JobStatus
    tkp_version_id: uuid.UUID | None = None
    created_at: datetime
