"""Add app_profile JSONB column to projects.

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "app_profile",
            postgresql.JSONB,
            nullable=True,
            comment="Application profile: URLs, auth config, endpoints, UI pages for generation context",
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "app_profile")
