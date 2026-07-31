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
    uploaded_at: datetime


class DocumentCreateResponse(BaseModel):
    document: DocumentRead
    job_id: uuid.UUID


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    status: JobStatus
    current_stage: str | None
    progress_pct: int
    error: str | None
    created_at: datetime
    updated_at: datetime


class TKPVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    version: int
    classification: dict | None
    extracted_knowledge: dict | None
    teaching_plan: dict | None
    period_content: dict | None
    assessments: dict | None
    learning_gaps: dict | None
    validation_report: dict | None
    published_at: datetime | None


class RegenerateSectionRequest(BaseModel):
    reason: str | None = None
