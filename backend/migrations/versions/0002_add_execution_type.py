"""Add execution_type column to test_cases.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column(
            "execution_type",
            sa.String(20),
            nullable=False,
            server_default="api",
            comment="api / ui / sql / manual",
        ),
    )


def downgrade() -> None:
    op.drop_column("test_cases", "execution_type")
