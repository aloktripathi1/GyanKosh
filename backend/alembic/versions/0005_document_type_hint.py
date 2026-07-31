"""add document_type_hint to documents — user-declared nature for parser routing

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-31

"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("document_type_hint", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "document_type_hint")
