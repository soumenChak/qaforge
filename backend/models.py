"""
QAForge -- Pydantic v2 request / response models.

All response models use ``model_config = ConfigDict(from_attributes=True)``
so they can be constructed directly from SQLAlchemy ORM instances.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ═══════════════════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════════════════
class LoginRequest(BaseModel):
    """Credentials for email/password login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT token returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


# ═══════════════════════════════════════════════════════════════════════════
# Users
# ═══════════════════════════════════════════════════════════════════════════
class UserCreate(BaseModel):
    """Payload to create a new user."""

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=6)
    roles: List[str] = Field(default_factory=lambda: ["tester"])

    @field_validator("roles", mode="before")
    @classmethod
    def validate_roles(cls, v: Any) -> List[str]:
        allowed = {"admin", "lead", "tester"}
        roles = v if isinstance(v, list) else [v]
        for r in roles:
            if r not in allowed:
                raise ValueError(f"Invalid role '{r}'. Allowed: {sorted(allowed)}")
        return roles


class UserUpdate(BaseModel):
    """Payload to update an existing user (partial)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator("roles", mode="before")
    @classmethod
    def validate_roles(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return v
        allowed = {"admin", "lead", "tester"}
        roles = v if isinstance(v, list) else [v]
        for r in roles:
            if r not in allowed:
                raise ValueError(f"Invalid role '{r}'. Allowed: {sorted(allowed)}")
        return roles


class UserResponse(BaseModel):
    """User data returned to clients (never includes password_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    roles: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Projects
# ═══════════════════════════════════════════════════════════════════════════
class ProjectCreate(BaseModel):
    """Payload to create a new project."""

    name: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., pattern=r"^(mdm|ai|data_eng|integration|digital)$")
    sub_domain: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    template_id: Optional[uuid.UUID] = None
    app_profile: Optional[Dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    """Payload to update an existing project (partial)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r"^(active|completed|archived)$")
    template_id: Optional[uuid.UUID] = None
    app_profile: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    """Single project returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    domain: str
    sub_domain: str
    description: Optional[str] = None
    status: str
    template_id: Optional[uuid.UUID] = None
    app_profile: Optional[Dict[str, Any]] = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """Project with aggregated stats for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    domain: str
    sub_domain: str
    description: Optional[str] = None
    status: str
    app_profile: Optional[Dict[str, Any]] = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Computed stats (populated by the route, not ORM)
    test_case_count: int = 0
    requirement_count: int = 0
    passed_count: int = 0
    failed_count: int = 0


# ═══════════════════════════════════════════════════════════════════════════
# Requirements
# ═══════════════════════════════════════════════════════════════════════════
class RequirementCreate(BaseModel):
    """Payload to create a requirement within a project."""

    req_id: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: str = Field(default="medium", pattern=r"^(high|medium|low)$")
    category: Optional[str] = None
    source: str = Field(default="manual", pattern=r"^(brd|prd|manual)$")


class RequirementResponse(BaseModel):
    """Single requirement returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    req_id: str
    title: str
    description: Optional[str] = None
    priority: str
    category: Optional[str] = None
    source: str
    status: str
    created_at: datetime


class RequirementExtractRequest(BaseModel):
    """Request to extract requirements from a document using AI."""

    document_text: str = Field(..., min_length=10)
    document_type: str = Field(
        default="brd",
        pattern=r"^(brd|prd|srs|fsd|user_story|manual|jira|confluence)$",
    )
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    focus_areas: Optional[str] = Field(
        None,
        description="Optional guidance for extraction focus (e.g., 'focus on data quality rules and API integrations')",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Test Cases
# ═══════════════════════════════════════════════════════════════════════════
class TestStepSchema(BaseModel):
    """A single test step within a test case."""

    step_number: int
    action: str
    expected_result: str


class TestCaseCreate(BaseModel):
    """Payload to create a test case manually."""

    test_case_id: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    requirement_id: Optional[uuid.UUID] = None
    preconditions: Optional[str] = None
    test_steps: Optional[List[TestStepSchema]] = None
    expected_result: Optional[str] = None
    test_data: Optional[Dict[str, Any]] = None
    priority: str = Field(default="P2", pattern=r"^(P1|P2|P3|P4)$")
    category: str = Field(
        default="functional",
        pattern=r"^(functional|integration|regression|smoke|e2e)$",
    )
    domain_tags: Optional[List[str]] = None
    execution_type: str = Field(default="api", pattern=r"^(api|ui|sql|manual)$")
    source: str = Field(default="manual", pattern=r"^(ai_generated|manual|hybrid)$")


class TestCaseUpdate(BaseModel):
    """Payload to update an existing test case (partial)."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    preconditions: Optional[str] = None
    test_steps: Optional[List[TestStepSchema]] = None
    expected_result: Optional[str] = None
    test_data: Optional[Dict[str, Any]] = None
    priority: Optional[str] = Field(None, pattern=r"^(P1|P2|P3|P4)$")
    category: Optional[str] = Field(
        None,
        pattern=r"^(functional|integration|regression|smoke|e2e)$",
    )
    domain_tags: Optional[List[str]] = None
    execution_type: Optional[str] = Field(None, pattern=r"^(api|ui|sql|manual)$")
    status: Optional[str] = Field(
        None,
        pattern=r"^(draft|active|passed|failed|blocked|deprecated)$",
    )


class TestCaseResponse(BaseModel):
    """Single test case returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: Optional[uuid.UUID] = None
    test_case_id: str
    title: str
    description: Optional[str] = None
    preconditions: Optional[str] = None
    test_steps: Optional[List[Dict[str, Any]]] = None
    expected_result: Optional[str] = None
    test_data: Optional[Dict[str, Any]] = None
    priority: str
    category: str
    domain_tags: Optional[List[str]] = None
    execution_type: str = "api"
    source: str
    status: str
    rating: Optional[int] = None
    rating_feedback: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    generated_by_model: Optional[str] = None
    generation_metadata: Optional[Dict[str, Any]] = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TestCaseGenerateRequest(BaseModel):
    """Request to generate test cases using AI."""

    description: str = Field(..., min_length=10)
    domain: str
    sub_domain: str
    requirement_ids: Optional[List[uuid.UUID]] = None
    template_id: Optional[uuid.UUID] = None
    additional_context: Optional[str] = None
    brd_prd_text: Optional[str] = Field(None, description="BRD/PRD document text for richer context")
    reference_test_case_ids: Optional[List[uuid.UUID]] = Field(
        None, description="Existing test case IDs to use as reference examples"
    )
    count: int = Field(default=10, ge=1, le=100)
    priority: Optional[str] = Field(None, pattern=r"^(P1|P2|P3|P4)$")
    category: Optional[str] = Field(
        None,
        pattern=r"^(functional|integration|regression|smoke|e2e)$",
    )
    execution_type: Optional[str] = Field(None, pattern=r"^(api|ui|sql|manual)$")


class TestCaseRateRequest(BaseModel):
    """Rate an AI-generated test case (feeds the learning loop)."""

    rating: int = Field(..., ge=1, le=5)
    feedback_text: Optional[str] = None


class TestCaseExportRequest(BaseModel):
    """Request to export test cases to a file."""

    test_case_ids: List[uuid.UUID] = Field(..., min_length=1)
    format: str = Field(default="excel", pattern=r"^(excel|word|json|csv)$")
    template_id: Optional[uuid.UUID] = None
    include_steps: bool = True
    include_test_data: bool = True


# ═══════════════════════════════════════════════════════════════════════════
# Templates
# ═══════════════════════════════════════════════════════════════════════════
class TemplateCreate(BaseModel):
    """Payload to create an export template."""

    name: str = Field(..., min_length=1, max_length=255)
    domain: str
    format: str = Field(default="excel", pattern=r"^(excel|word|json)$")
    template_file_path: Optional[str] = None
    column_mapping: Optional[Dict[str, Any]] = None
    branding_config: Optional[Dict[str, Any]] = None


class TemplateUpdate(BaseModel):
    """Payload to update an export template (partial)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = None
    format: Optional[str] = Field(None, pattern=r"^(excel|word|json)$")
    column_mapping: Optional[Dict[str, Any]] = None
    branding_config: Optional[Dict[str, Any]] = None


class TemplateResponse(BaseModel):
    """Single template returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    domain: str
    format: str
    template_file_path: Optional[str] = None
    column_mapping: Optional[Dict[str, Any]] = None
    branding_config: Optional[Dict[str, Any]] = None
    created_by: uuid.UUID
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Connections
# ═══════════════════════════════════════════════════════════════════════════
class ConnectionCreate(BaseModel):
    """Payload to create an external connection profile."""

    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(
        ...,
        pattern=r"^(browser|database|api|platform|integration)$",
    )
    driver: str = Field(
        ...,
        pattern=r"^(playwright|snowflake|databricks|reltio|semarchy|http|oracle|sqlserver|postgresql|talend|boomi)$",
    )
    config: Dict[str, Any] = Field(default_factory=dict)
    credentials_ref: Optional[str] = None


class ConnectionResponse(BaseModel):
    """Single connection returned to clients (credentials masked)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    driver: str
    config: Dict[str, Any]
    credentials_ref: Optional[str] = None
    status: str
    last_tested_at: Optional[datetime] = None
    created_by: uuid.UUID
    created_at: datetime


class ConnectionTestResponse(BaseModel):
    """Result of testing a connection."""

    success: bool
    message: str
    latency_ms: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════
# Test Agents
# ═══════════════════════════════════════════════════════════════════════════
class TestAgentCreate(BaseModel):
    """Payload to create a test agent."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    domain: str
    sub_domain: Optional[str] = None
    agent_type: str = Field(
        ...,
        pattern=r"^(matcher|validator|smoke_tester|dq_checker|ui_tester|api_tester)$",
    )
    system_prompt: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    connection_ids: Optional[List[uuid.UUID]] = None
    template_id: Optional[str] = None


class TestAgentResponse(BaseModel):
    """Single test agent returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    domain: str
    sub_domain: Optional[str] = None
    agent_type: str
    system_prompt: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    connection_ids: Optional[List[uuid.UUID]] = None
    template_id: Optional[str] = None
    status: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Execution Runs
# ═══════════════════════════════════════════════════════════════════════════
class ExecutionRunCreate(BaseModel):
    """Payload to create / queue an execution run."""

    project_id: uuid.UUID
    test_agent_id: Optional[uuid.UUID] = None
    test_case_ids: List[uuid.UUID] = Field(..., min_length=1)
    connection_id: Optional[uuid.UUID] = None


class ExecutionRunResponse(BaseModel):
    """Single execution run returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    test_agent_id: Optional[uuid.UUID] = None
    test_case_ids: List[uuid.UUID]
    connection_id: Optional[uuid.UUID] = None
    status: str
    results: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    executed_by: uuid.UUID


class ExecutionRunStatus(BaseModel):
    """Lightweight status for polling during execution."""

    id: uuid.UUID
    status: str
    progress: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    elapsed_seconds: Optional[float] = None


class ConnectionUpdate(BaseModel):
    """Partial update for a connection."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    config: Optional[Dict[str, Any]] = None
    credentials_ref: Optional[str] = None
    status: Optional[str] = None


class TestAgentUpdate(BaseModel):
    """Partial update for a test agent."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    connection_ids: Optional[List[uuid.UUID]] = None
    template_id: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r"^(draft|active|archived)$")


# ═══════════════════════════════════════════════════════════════════════════
# Knowledge Base
# ═══════════════════════════════════════════════════════════════════════════
class KnowledgeSearchRequest(BaseModel):
    """Request to search the knowledge base (semantic + keyword)."""

    query: str = Field(..., min_length=2)
    domain: Optional[str] = None
    sub_domain: Optional[str] = None
    entry_type: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)


class KnowledgeEntryResponse(BaseModel):
    """Single knowledge entry returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    domain: str
    sub_domain: Optional[str] = None
    entry_type: str
    title: str
    content: str
    tags: Optional[List[str]] = None
    source_project_id: Optional[uuid.UUID] = None
    usage_count: int
    created_by: uuid.UUID
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Feedback / Metrics
# ═══════════════════════════════════════════════════════════════════════════
class FeedbackMetricsResponse(BaseModel):
    """Aggregated feedback metrics for a project or globally."""

    total_feedback: int = 0
    average_rating: Optional[float] = None
    rating_distribution: Dict[int, int] = Field(
        default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    )
    feedback_by_type: Dict[str, int] = Field(default_factory=dict)
    applied_to_knowledge_count: int = 0


# ═══════════════════════════════════════════════════════════════════════════
# Settings
# ═══════════════════════════════════════════════════════════════════════════
class SettingsResponse(BaseModel):
    """Platform-wide settings."""

    default_llm_provider: str
    default_llm_model: str
    available_providers: List[str]
    chromadb_status: str
    redis_status: str


class SettingsUpdate(BaseModel):
    """Payload to update platform settings (admin only)."""

    default_llm_provider: Optional[str] = None
    default_llm_model: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# Generation Runs
# ═══════════════════════════════════════════════════════════════════════════
class GenerationRunResponse(BaseModel):
    """Single generation run returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    agent_type: str
    input_context: Optional[Dict[str, Any]] = None
    test_cases_generated: int
    avg_rating: Optional[float] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    tokens_used: int
    duration_seconds: Optional[float] = None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Generic
# ═══════════════════════════════════════════════════════════════════════════
class ChangePasswordRequest(BaseModel):
    """Payload to change the current user's password."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


class RequirementUpdate(BaseModel):
    """Payload to update an existing requirement (partial)."""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, pattern=r"^(high|medium|low)$")
    category: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r"^(active|tested|deferred)$")


class UploadTextRequest(BaseModel):
    """Upload raw BRD/PRD text for later extraction."""

    document_text: str = Field(..., min_length=10)
    document_type: str = Field(default="brd", pattern=r"^(brd|prd|manual)$")


class KnowledgeEntryCreate(BaseModel):
    """Payload to create a knowledge entry manually."""

    domain: str = Field(..., min_length=1, max_length=50)
    sub_domain: Optional[str] = Field(None, max_length=100)
    entry_type: str = Field(
        ...,
        pattern=r"^(pattern|defect|best_practice|test_case)$",
    )
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    tags: Optional[List[str]] = None
    source_project_id: Optional[uuid.UUID] = None


class FeedbackCorrectionResponse(BaseModel):
    """A correction entry (low-rated feedback with corrected content)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_case_id: uuid.UUID
    rating: int
    original_content: Optional[Dict[str, Any]] = None
    corrected_content: Optional[Dict[str, Any]] = None
    feedback_text: Optional[str] = None
    feedback_type: str
    created_by: uuid.UUID
    created_at: datetime


class LLMSettingsResponse(BaseModel):
    """Current LLM configuration."""

    provider: str
    model: str
    available_providers: List[str]


class LLMSettingsUpdate(BaseModel):
    """Payload to update LLM settings."""

    provider: Optional[str] = None
    model: Optional[str] = None


class LLMProviderInfo(BaseModel):
    """Details about a single LLM provider."""

    name: str
    configured: bool
    models: List[str]


class MessageResponse(BaseModel):
    """Generic message response for actions without a dedicated schema."""

    message: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Wrapper for paginated list endpoints."""

    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 50
    pages: int = 1


# ═══════════════════════════════════════════════════════════════════════════
# Coverage Score (Feature 2)
# ═══════════════════════════════════════════════════════════════════════════
class CoverageResult(BaseModel):
    """Test coverage analysis for a project's requirements."""

    score: float = Field(..., ge=0, le=100, description="Priority-weighted coverage score (0-100)")
    grade: str = Field(..., description="Letter grade: A/B/C/D/F")
    total_requirements: int
    covered_requirements: int
    uncovered_requirements: int
    coverage_by_priority: Dict[str, Any] = Field(
        default_factory=dict,
        description="Breakdown by priority: {high: {total, covered, uncovered_ids}, medium: ..., low: ...}",
    )
    uncovered_details: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of uncovered requirements: [{req_id, title, priority}]",
    )
    orphan_test_count: int = Field(
        default=0,
        description="Test cases without a requirement_id (not contributing to coverage)",
    )
    scoring_explanation: str = Field(
        default="",
        description="Human-readable explanation of how the score was calculated",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Profile Validation (Feature 3)
# ═══════════════════════════════════════════════════════════════════════════
class ProfileValidationResult(BaseModel):
    """Results from validating an app_profile against the live application."""

    overall_status: str = Field(..., description="pass | partial | fail")
    checks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of validation checks: [{name, status, message, details}]",
    )


# ═══════════════════════════════════════════════════════════════════════════
# OpenAPI Discovery (Feature 4)
# ═══════════════════════════════════════════════════════════════════════════
class OpenAPIDiscoverRequest(BaseModel):
    """Request to auto-discover API endpoints from an OpenAPI/Swagger spec."""

    openapi_url: str = Field(..., min_length=5, description="URL to OpenAPI JSON or YAML spec")


# ═══════════════════════════════════════════════════════════════════════════
# Chat-Based Test Generation (Feature 6)
# ═══════════════════════════════════════════════════════════════════════════
class ChatMessage(BaseModel):
    """A single message in a chat-based generation conversation."""

    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatGenerateRequest(BaseModel):
    """Request for chat-based test generation (multi-turn conversation)."""

    messages: List[ChatMessage] = Field(..., min_length=1)
    requirement_ids: Optional[List[uuid.UUID]] = None
    execution_type: Optional[str] = Field(None, pattern=r"^(api|ui|sql|manual)$")


class ChatGenerateResponse(BaseModel):
    """Response from the chat-based generation agent."""

    message: ChatMessage
    action: str = Field(..., description="question | generate | confirm")
    test_cases: Optional[List[TestCaseResponse]] = None
    suggested_config: Optional[Dict[str, Any]] = None
