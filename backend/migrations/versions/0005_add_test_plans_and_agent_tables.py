"""Add test_plans, execution_results, proof_artifacts, agent_sessions,
validation_checkpoints tables. Add agent_api_key_hash to projects and
test_plan_id to test_cases.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- agent_sessions (must exist before execution_results FK) --
    op.create_table(
        "agent_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=True),
        sa.Column("submission_mode", sa.String(20), nullable=False, server_default="realtime"),
        sa.Column("session_meta", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- test_plans --
    op.create_table(
        "test_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("plan_type", sa.String(30), nullable=False, server_default="custom"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- execution_results --
    op.create_table(
        "execution_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("test_case_id", UUID(as_uuid=True), sa.ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("test_plan_id", UUID(as_uuid=True), sa.ForeignKey("test_plans.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("actual_result", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("environment", JSONB, nullable=True),
        sa.Column("executed_by", sa.String(100), nullable=False),
        sa.Column("agent_session_id", UUID(as_uuid=True), sa.ForeignKey("agent_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_status", sa.String(20), nullable=True),
        sa.Column("review_comment", sa.Text, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- proof_artifacts --
    op.create_table(
        "proof_artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("execution_result_id", UUID(as_uuid=True), sa.ForeignKey("execution_results.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("proof_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", JSONB, nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- validation_checkpoints --
    op.create_table(
        "validation_checkpoints",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("test_plan_id", UUID(as_uuid=True), sa.ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("checkpoint_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewer_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("comments", sa.Text, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- Add columns to existing tables --
    op.add_column(
        "projects",
        sa.Column("agent_api_key_hash", sa.String(128), nullable=True),
    )
    op.add_column(
        "test_cases",
        sa.Column("test_plan_id", UUID(as_uuid=True), sa.ForeignKey("test_plans.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_test_cases_test_plan_id", "test_cases", ["test_plan_id"])


def downgrade() -> None:
    op.drop_index("ix_test_cases_test_plan_id", table_name="test_cases")
    op.drop_column("test_cases", "test_plan_id")
    op.drop_column("projects", "agent_api_key_hash")
    op.drop_table("validation_checkpoints")
    op.drop_table("proof_artifacts")
    op.drop_table("execution_results")
    op.drop_table("test_plans")
    op.drop_table("agent_sessions")
