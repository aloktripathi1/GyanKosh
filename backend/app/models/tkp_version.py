import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TKPVersion(Base):
    __tablename__ = "tkp_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    classification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extracted_knowledge: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    teaching_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    period_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    activities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    assessments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    learning_gaps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pdf_paths: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
