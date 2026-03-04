"""Add version column to knowledge_entries for framework versioning.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_entries",
        sa.Column("version", sa.String(20), nullable=True, comment="Semantic version e.g. 1.0, 2.1"),
    )


def downgrade() -> None:
    op.drop_column("knowledge_entries", "version")
