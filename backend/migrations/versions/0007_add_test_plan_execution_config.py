"""Add execution_config JSONB column to test_plans table.

Stores execution playbook metadata: environment, prerequisites,
connection refs, required env vars, and execution order.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_plans",
        sa.Column(
            "execution_config",
            JSONB,
            nullable=True,
            comment="Execution playbook: environment, prerequisites, connection refs, env vars",
        ),
    )


def downgrade() -> None:
    op.drop_column("test_plans", "execution_config")
