"""add activities and pdf_paths columns to tkp_versions

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-31

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tkp_versions", sa.Column("activities", postgresql.JSONB(), nullable=True))
    op.add_column("tkp_versions", sa.Column("pdf_paths", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("tkp_versions", "pdf_paths")
    op.drop_column("tkp_versions", "activities")
