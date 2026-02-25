"""Initial QAForge schema — all tables for Phase 1.

Revision ID: 0001
Revises:
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # 1. users  (no foreign keys)
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("roles", postgresql.JSONB, nullable=False, server_default='["tester"]'),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ------------------------------------------------------------------
    # 2. test_templates  (FK -> users)
    # ------------------------------------------------------------------
    op.create_table(
        "test_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "domain",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "format",
            sa.String(20),
            nullable=False,
            server_default="excel",
            comment="excel / word / json",
        ),
        sa.Column("template_file_path", sa.String(500), nullable=True),
        sa.Column("column_mapping", postgresql.JSONB, nullable=True),
        sa.Column("branding_config", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # 3. projects  (FK -> users, test_templates)
    # ------------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "domain",
            sa.String(50),
            nullable=False,
            comment="mdm / ai / data_eng / integration / digital",
        ),
        sa.Column(
            "sub_domain",
            sa.String(100),
            nullable=False,
            comment="reltio / semarchy / databricks / snowflake / talend / boomi / etc.",
        ),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active / completed / archived",
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_projects_domain", "projects", ["domain"])
    op.create_index("ix_projects_status", "projects", ["status"])

    # ------------------------------------------------------------------
    # 4. requirements  (FK -> projects)
    # ------------------------------------------------------------------
    op.create_table(
        "requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "req_id",
            sa.String(30),
            nullable=False,
            comment="Human-readable ID e.g. REQ-001",
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="medium",
            comment="high / medium / low",
        ),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="manual",
            comment="brd / prd / manual",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active / tested / deferred",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("project_id", "req_id", name="uq_requirement_project_req_id"),
    )
    op.create_index("ix_requirements_project_id", "requirements", ["project_id"])

    # ------------------------------------------------------------------
    # 5. connections  (FK -> users)
    # ------------------------------------------------------------------
    op.create_table(
        "connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "type",
            sa.String(30),
            nullable=False,
            comment="browser / database / api / platform / integration",
        ),
        sa.Column(
            "driver",
            sa.String(30),
            nullable=False,
            comment="playwright / snowflake / databricks / reltio / semarchy / http / oracle / sqlserver / postgresql / talend / boomi",
        ),
        sa.Column(
            "config",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
            comment="host / port / warehouse / schema / options",
        ),
        sa.Column(
            "credentials_ref",
            sa.String(255),
            nullable=True,
            comment="Encrypted vault key reference",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="disconnected",
            comment="connected / disconnected / error",
        ),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_connections_status", "connections", ["status"])

    # ------------------------------------------------------------------
    # 6. test_agents  (FK -> users)
    # ------------------------------------------------------------------
    op.create_table(
        "test_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("sub_domain", sa.String(100), nullable=True),
        sa.Column(
            "agent_type",
            sa.String(30),
            nullable=False,
            comment="matcher / validator / smoke_tester / dq_checker / ui_tester / api_tester",
        ),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column(
            "connection_ids",
            postgresql.JSONB,
            nullable=True,
            comment="Array of connection UUIDs",
        ),
        sa.Column("template_id", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
            comment="draft / active / archived",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_test_agents_domain", "test_agents", ["domain"])
    op.create_index("ix_test_agents_status", "test_agents", ["status"])

    # ------------------------------------------------------------------
    # 7. test_cases  (FK -> projects, requirements, users)
    # ------------------------------------------------------------------
    op.create_table(
        "test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requirement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("requirements.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "test_case_id",
            sa.String(30),
            nullable=False,
            comment="Human-readable ID e.g. TC-001",
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("preconditions", sa.Text, nullable=True),
        sa.Column(
            "test_steps",
            postgresql.JSONB,
            nullable=True,
            comment="Array of {step_number, action, expected_result}",
        ),
        sa.Column("expected_result", sa.Text, nullable=True),
        sa.Column("test_data", postgresql.JSONB, nullable=True),
        sa.Column(
            "priority",
            sa.String(5),
            nullable=False,
            server_default="P2",
            comment="P1 / P2 / P3 / P4",
        ),
        sa.Column(
            "category",
            sa.String(30),
            nullable=False,
            server_default="functional",
            comment="functional / integration / regression / smoke / e2e",
        ),
        sa.Column("domain_tags", postgresql.JSONB, nullable=True),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="ai_generated",
            comment="ai_generated / manual / hybrid",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
            comment="draft / reviewed / approved / executed / passed / failed",
        ),
        sa.Column("rating", sa.Integer, nullable=True, comment="1-5 star rating"),
        sa.Column("rating_feedback", sa.Text, nullable=True),
        sa.Column("execution_result", postgresql.JSONB, nullable=True),
        sa.Column("generated_by_model", sa.String(100), nullable=True),
        sa.Column("generation_metadata", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("project_id", "test_case_id", name="uq_testcase_project_tc_id"),
    )
    op.create_index("ix_test_cases_project_id", "test_cases", ["project_id"])
    op.create_index("ix_test_cases_requirement_id", "test_cases", ["requirement_id"])
    op.create_index("ix_test_cases_status", "test_cases", ["status"])

    # ------------------------------------------------------------------
    # 8. execution_runs  (FK -> projects, test_agents, connections, users)
    # ------------------------------------------------------------------
    op.create_table(
        "execution_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "test_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "test_case_ids",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
            comment="Array of test case UUIDs",
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="queued",
            comment="queued / running / completed / failed / cancelled",
        ),
        sa.Column(
            "results",
            postgresql.JSONB,
            nullable=True,
            comment="Per test-case pass/fail results",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "executed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
    )
    op.create_index("ix_execution_runs_project_id", "execution_runs", ["project_id"])
    op.create_index("ix_execution_runs_status", "execution_runs", ["status"])

    # ------------------------------------------------------------------
    # 9. knowledge_entries  (FK -> projects, users)
    # ------------------------------------------------------------------
    op.create_table(
        "knowledge_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("sub_domain", sa.String(100), nullable=True),
        sa.Column(
            "entry_type",
            sa.String(30),
            nullable=False,
            comment="pattern / defect / best_practice / test_case",
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "embedding_id",
            sa.String(255),
            nullable=True,
            comment="ChromaDB embedding reference",
        ),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        sa.Column(
            "source_project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_knowledge_entries_domain", "knowledge_entries", ["domain"])

    # ------------------------------------------------------------------
    # 10. feedback_entries  (FK -> test_cases, users)
    # ------------------------------------------------------------------
    op.create_table(
        "feedback_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "test_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer, nullable=False, comment="1-5 star rating"),
        sa.Column("original_content", postgresql.JSONB, nullable=True),
        sa.Column("corrected_content", postgresql.JSONB, nullable=True),
        sa.Column("feedback_text", sa.Text, nullable=True),
        sa.Column(
            "feedback_type",
            sa.String(30),
            nullable=False,
            server_default="quality",
            comment="quality / accuracy / completeness / relevance",
        ),
        sa.Column(
            "applied_to_knowledge",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_feedback_entries_test_case_id", "feedback_entries", ["test_case_id"])

    # ------------------------------------------------------------------
    # 11. generation_runs  (FK -> projects)
    # ------------------------------------------------------------------
    op.create_table(
        "generation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_type", sa.String(30), nullable=False),
        sa.Column("input_context", postgresql.JSONB, nullable=True),
        sa.Column(
            "test_cases_generated", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("avg_rating", sa.Float, nullable=True),
        sa.Column("llm_provider", sa.String(50), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_generation_runs_project_id", "generation_runs", ["project_id"])

    # ------------------------------------------------------------------
    # 12. audit_log  (FK -> users)
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # ------------------------------------------------------------------
    # 13. cost_tracking  (FK -> users, projects)
    # ------------------------------------------------------------------
    op.create_table(
        "cost_tracking",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "operation_type",
            sa.String(30),
            nullable=False,
            comment="llm / snowflake / databricks / api",
        ),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("compute_units", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "estimated_cost_usd", sa.Float, nullable=False, server_default="0.0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_cost_tracking_user_id", "cost_tracking", ["user_id"])
    op.create_index("ix_cost_tracking_project_id", "cost_tracking", ["project_id"])
    op.create_index("ix_cost_tracking_created_at", "cost_tracking", ["created_at"])


def downgrade():
    # Drop in reverse dependency order
    op.drop_table("cost_tracking")
    op.drop_table("audit_log")
    op.drop_table("generation_runs")
    op.drop_table("feedback_entries")
    op.drop_table("knowledge_entries")
    op.drop_table("execution_runs")
    op.drop_table("test_cases")
    op.drop_table("connections")
    op.drop_table("test_agents")
    op.drop_table("requirements")
    op.drop_table("projects")
    op.drop_table("test_templates")
    op.drop_table("users")
