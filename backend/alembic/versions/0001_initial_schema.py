"""initial schema: documents, jobs, tkp_versions

Revision ID: 0001
Revises:
Create Date: 2026-07-31

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

job_status = postgresql.ENUM("pending", "running", "completed", "failed", name="job_status", create_type=False)


def upgrade() -> None:
    job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="pending"),
        sa.Column("current_stage", sa.String(), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("stage_results", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tkp_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("classification", postgresql.JSONB(), nullable=True),
        sa.Column("extracted_knowledge", postgresql.JSONB(), nullable=True),
        sa.Column("teaching_plan", postgresql.JSONB(), nullable=True),
        sa.Column("period_content", postgresql.JSONB(), nullable=True),
        sa.Column("assessments", postgresql.JSONB(), nullable=True),
        sa.Column("learning_gaps", postgresql.JSONB(), nullable=True),
        sa.Column("validation_report", postgresql.JSONB(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("tkp_versions")
    op.drop_table("jobs")
    op.drop_table("documents")
    job_status.drop(op.get_bind(), checkfirst=True)
