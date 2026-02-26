"""
QAForge -- SQLAlchemy ORM Models.

All tables use UUID primary keys and JSONB for flexible/schemaless fields.
This module is imported by Alembic's env.py for autogenerate support.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Base class for all QAForge ORM models."""
    pass


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    """Generate a new UUID4."""
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class User(Base):
    """Platform users (admin, lead, tester)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    roles: Mapped[Any] = mapped_column(JSONB, nullable=False, default=lambda: ["tester"])
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=_utcnow
    )

    # -- relationships (back-populated from child tables) --
    projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="creator", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
class Project(Base):
    """A QA project scoped to a domain/sub-domain."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="mdm / ai / data_eng / integration / digital"
    )
    sub_domain: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="reltio / semarchy / databricks / snowflake / talend / boomi / etc."
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    app_profile: Mapped[Any] = mapped_column(
        JSONB, nullable=True, default=None,
        comment="Application profile: URLs, auth config, endpoints, UI pages for test generation context"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="active / completed / archived"
    )
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_templates.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=_utcnow
    )

    # -- relationships --
    creator: Mapped["User"] = relationship("User", back_populates="projects", lazy="joined")
    template: Mapped[Optional["TestTemplate"]] = relationship(
        "TestTemplate", lazy="joined"
    )
    requirements: Mapped[List["Requirement"]] = relationship(
        "Requirement", back_populates="project", cascade="all, delete-orphan", lazy="select"
    )
    test_cases: Mapped[List["TestCase"]] = relationship(
        "TestCase", back_populates="project", cascade="all, delete-orphan", lazy="select"
    )
    execution_runs: Mapped[List["ExecutionRun"]] = relationship(
        "ExecutionRun", back_populates="project", lazy="select"
    )
    generation_runs: Mapped[List["GenerationRun"]] = relationship(
        "GenerationRun", back_populates="project", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name} [{self.domain}/{self.sub_domain}]>"


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------
class Requirement(Base):
    """A functional/business requirement linked to a project."""

    __tablename__ = "requirements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    req_id: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="Human-readable ID e.g. REQ-001"
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium", comment="high / medium / low"
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", comment="brd / prd / manual"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", comment="active / tested / deferred"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # -- relationships --
    project: Mapped["Project"] = relationship("Project", back_populates="requirements")
    test_cases: Mapped[List["TestCase"]] = relationship(
        "TestCase", back_populates="requirement", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "req_id", name="uq_requirement_project_req_id"),
    )

    def __repr__(self) -> str:
        return f"<Requirement {self.req_id}: {self.title[:40]}>"


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
class TestCase(Base):
    """An individual test case -- AI-generated, manual, or hybrid."""

    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True, index=True
    )
    test_case_id: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="Human-readable ID e.g. TC-001"
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preconditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    test_steps: Mapped[Any] = mapped_column(
        JSONB, nullable=True, comment="Array of {step_number, action, expected_result}"
    )
    expected_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    test_data: Mapped[Any] = mapped_column(JSONB, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(5), nullable=False, default="P2", comment="P1 / P2 / P3 / P4"
    )
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, default="functional",
        comment="functional / integration / regression / smoke / e2e"
    )
    domain_tags: Mapped[Any] = mapped_column(JSONB, nullable=True)
    execution_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="api",
        comment="api / ui / sql / manual"
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ai_generated",
        comment="ai_generated / manual / hybrid"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        comment="draft / reviewed / approved / executed / passed / failed"
    )
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="1-5 star rating")
    rating_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_result: Mapped[Any] = mapped_column(JSONB, nullable=True)
    generated_by_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    generation_metadata: Mapped[Any] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=_utcnow
    )

    # -- relationships --
    project: Mapped["Project"] = relationship("Project", back_populates="test_cases")
    requirement: Mapped[Optional["Requirement"]] = relationship(
        "Requirement", back_populates="test_cases"
    )
    creator: Mapped["User"] = relationship("User", lazy="joined")
    feedback_entries: Mapped[List["FeedbackEntry"]] = relationship(
        "FeedbackEntry", back_populates="test_case", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "test_case_id", name="uq_testcase_project_tc_id"),
    )

    def __repr__(self) -> str:
        return f"<TestCase {self.test_case_id}: {self.title[:40]}>"


# ---------------------------------------------------------------------------
# Test Templates
# ---------------------------------------------------------------------------
class TestTemplate(Base):
    """Export templates (Excel/Word/JSON) with branding and column mapping."""

    __tablename__ = "test_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    format: Mapped[str] = mapped_column(
        String(20), nullable=False, default="excel", comment="excel / word / json"
    )
    template_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    column_mapping: Mapped[Any] = mapped_column(JSONB, nullable=True)
    branding_config: Mapped[Any] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # -- relationships --
    creator: Mapped["User"] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<TestTemplate {self.name} [{self.domain}/{self.format}]>"


# ---------------------------------------------------------------------------
# Connections (external systems)
# ---------------------------------------------------------------------------
class Connection(Base):
    """Connection profiles for external systems (databases, APIs, platforms)."""

    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="browser / database / api / platform / integration"
    )
    driver: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="playwright / snowflake / databricks / reltio / semarchy / http / oracle / sqlserver / postgresql / talend / boomi"
    )
    config: Mapped[Any] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="host / port / warehouse / schema / options"
    )
    credentials_ref: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Encrypted vault key reference"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="disconnected",
        comment="connected / disconnected / error"
    )
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # -- relationships --
    creator: Mapped["User"] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<Connection {self.name} [{self.driver}]>"


# ---------------------------------------------------------------------------
# Test Agents
# ---------------------------------------------------------------------------
class TestAgent(Base):
    """AI test agents configured per domain/sub-domain."""

    __tablename__ = "test_agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="matcher / validator / smoke_tester / dq_checker / ui_tester / api_tester"
    )
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[Any] = mapped_column(JSONB, nullable=True)
    connection_ids: Mapped[Any] = mapped_column(
        JSONB, nullable=True, comment="Array of connection UUIDs"
    )
    template_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", comment="draft / active / archived"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=_utcnow
    )

    # -- relationships --
    creator: Mapped["User"] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<TestAgent {self.name} [{self.agent_type}]>"


# ---------------------------------------------------------------------------
# Execution Runs
# ---------------------------------------------------------------------------
class ExecutionRun(Base):
    """A batch execution of test cases against a connection."""

    __tablename__ = "execution_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_agents.id", ondelete="SET NULL"), nullable=True
    )
    test_case_ids: Mapped[Any] = mapped_column(
        JSONB, nullable=False, default=list, comment="Array of test case UUIDs"
    )
    connection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connections.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued",
        comment="queued / running / completed / failed / cancelled"
    )
    results: Mapped[Any] = mapped_column(
        JSONB, nullable=True, comment="Per test-case pass/fail results"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    executed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # -- relationships --
    project: Mapped["Project"] = relationship("Project", back_populates="execution_runs")
    test_agent: Mapped[Optional["TestAgent"]] = relationship("TestAgent", lazy="joined")
    connection: Mapped[Optional["Connection"]] = relationship("Connection", lazy="joined")
    executor: Mapped["User"] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<ExecutionRun {self.id} [{self.status}]>"


# ---------------------------------------------------------------------------
# Knowledge Entries (RAG knowledge base)
# ---------------------------------------------------------------------------
class KnowledgeEntry(Base):
    """Domain knowledge for RAG-enhanced test generation."""

    __tablename__ = "knowledge_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    domain: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sub_domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entry_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="pattern / defect / best_practice / test_case"
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="ChromaDB embedding reference"
    )
    tags: Mapped[Any] = mapped_column(JSONB, nullable=True)
    source_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # -- relationships --
    source_project: Mapped[Optional["Project"]] = relationship("Project", lazy="joined")
    creator: Mapped["User"] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<KnowledgeEntry {self.entry_type}: {self.title[:40]}>"


# ---------------------------------------------------------------------------
# Feedback Entries
# ---------------------------------------------------------------------------
class FeedbackEntry(Base):
    """User feedback on AI-generated test cases for the learning loop."""

    __tablename__ = "feedback_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False, comment="1-5 star rating")
    original_content: Mapped[Any] = mapped_column(JSONB, nullable=True)
    corrected_content: Mapped[Any] = mapped_column(JSONB, nullable=True)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feedback_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="quality",
        comment="quality / accuracy / completeness / relevance"
    )
    applied_to_knowledge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # -- relationships --
    test_case: Mapped["TestCase"] = relationship("TestCase", back_populates="feedback_entries")
    creator: Mapped["User"] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<FeedbackEntry tc={self.test_case_id} rating={self.rating}>"


# ---------------------------------------------------------------------------
# Generation Runs (LLM usage tracking)
# ---------------------------------------------------------------------------
class GenerationRun(Base):
    """Tracks each AI generation batch for analytics and cost tracking."""

    __tablename__ = "generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    input_context: Mapped[Any] = mapped_column(JSONB, nullable=True)
    test_cases_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # -- relationships --
    project: Mapped["Project"] = relationship("Project", back_populates="generation_runs")

    def __repr__(self) -> str:
        return f"<GenerationRun {self.id} [{self.agent_type}] cases={self.test_cases_generated}>"


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------
class AuditLog(Base):
    """Immutable audit trail for all significant actions."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Any] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # -- relationships --
    user: Mapped[Optional["User"]] = relationship("User", lazy="joined")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type}/{self.entity_id}>"


# ---------------------------------------------------------------------------
# Cost Tracking
# ---------------------------------------------------------------------------
class CostTracking(Base):
    """Per-operation cost tracking for LLM calls, compute, and API usage."""

    __tablename__ = "cost_tracking"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="llm / snowflake / databricks / api"
    )
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compute_units: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # -- relationships --
    user: Mapped[Optional["User"]] = relationship("User", lazy="joined")
    project: Mapped[Optional["Project"]] = relationship("Project", lazy="joined")

    def __repr__(self) -> str:
        return f"<CostTracking {self.operation_type} ${self.estimated_cost_usd:.4f}>"
