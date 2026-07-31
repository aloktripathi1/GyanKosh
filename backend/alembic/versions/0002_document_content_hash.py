"""add content_hash to documents, for cost-control caching by document hash

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-31

"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content_hash", sa.String(), nullable=False, server_default=""))
    op.alter_column("documents", "content_hash", server_default=None)
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_column("documents", "content_hash")
