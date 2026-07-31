"""add teaching_context to jobs — optional teacher-provided clarifying context

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-31

"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("teaching_context", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "teaching_context")
