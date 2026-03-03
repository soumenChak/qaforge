"""Add Connection, TestAgent, and ExecutionRun tables for test execution.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- connections table --
    op.create_table(
        "connections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "connection_type",
            sa.String(30),
            nullable=False,
            server_default="rest_api",
        ),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "is_default",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("project_id", "name", name="uq_connection_project_name"),
    )

    # -- test_agents table --
    op.create_table(
        "test_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "name", sa.String(100), nullable=False, server_default="default"
        ),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -- execution_runs table --
    op.create_table(
        "execution_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "test_plan_id",
            UUID(as_uuid=True),
            sa.ForeignKey("test_plans.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "connection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "test_agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("test_agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("test_case_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("results", JSONB, nullable=True),
        sa.Column(
            "triggered_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Performance index
    op.create_index("ix_execution_runs_status", "execution_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_execution_runs_status", "execution_runs")
    op.drop_table("execution_runs")
    op.drop_table("test_agents")
    op.drop_table("connections")
