import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


STAGE_NAMES = (
    "document_intelligence",
    "classification",
    "knowledge_extraction",
    "teaching_planner",
    "content_generation",
    "activity_generation",
    "assessment_generation",
    "gap_analysis",
    "validation",
    "publishing",
)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=JobStatus.PENDING,
        nullable=False,
    )
    current_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    teaching_context: Mapped[str | None] = mapped_column(
        String, nullable=True, doc="optional teacher-provided context: grade override, objectives, style, time constraints"
    )
    stage_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    stage_timings: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False, doc="stage name -> wall-clock seconds, for observability/debugging"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
