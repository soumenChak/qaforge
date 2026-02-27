"""Add brd_prd_text column to projects.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "brd_prd_text",
            sa.Text(),
            nullable=True,
            comment="BRD/PRD document text for test generation context",
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "brd_prd_text")
