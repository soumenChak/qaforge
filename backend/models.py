"""
QAForge -- Pydantic v2 request / response models.

All response models use ``model_config = ConfigDict(from_attributes=True)``
so they can be constructed directly from SQLAlchemy ORM instances.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

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
    roles: List[str] = Field(default_factory=lambda: ["engineer"])

    @field_validator("roles", mode="before")
    @classmethod
    def validate_roles(cls, v: Any) -> List[str]:
        allowed = {"admin", "engineer"}
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
        allowed = {"admin", "engineer"}
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
    brd_prd_text: Optional[str] = None
    assigned_users: Optional[List[uuid.UUID]] = None
    auto_generate_key: bool = False


class ProjectUpdate(BaseModel):
    """Payload to update an existing project (partial)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r"^(active|completed|archived)$")
    template_id: Optional[uuid.UUID] = None
    app_profile: Optional[Dict[str, Any]] = None
    brd_prd_text: Optional[str] = None


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
    brd_prd_text: Optional[str] = None
    has_agent_key: bool = False
    assigned_users: Optional[List[uuid.UUID]] = None
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
    assigned_users: Optional[List[uuid.UUID]] = None
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
    """A single test step within a test case.

    Contains both human-readable descriptions AND structured executable specs.
    The structured fields make tests re-runnable without LLM help.

    Supports execution types: mcp, api, sql, ui, manual.
    Extra fields are preserved via ``extra='allow'``.
    """

    model_config = ConfigDict(extra="allow")

    # -- Core (always required) --
    step_number: int
    action: str                     # Human-readable description of what to do
    expected_result: str            # Human-readable expected outcome

    # -- Execution routing --
    step_type: Optional[str] = None       # mcp | api | sql | ui | manual (overrides TC-level)
    connection_ref: Optional[str] = None  # Key into app_profile.connections, e.g. "reltio_mcp"

    # -- MCP tool spec --
    tool_name: Optional[str] = None           # e.g. "health_check_tool"
    tool_params: Optional[Dict[str, Any]] = None  # e.g. {"entity_type": "Individual"}

    # -- REST API spec --
    method: Optional[str] = None          # GET | POST | PUT | DELETE
    endpoint: Optional[str] = None        # /api/v1/entities (relative to connection base_url)
    headers: Optional[Dict[str, str]] = None
    request_body: Optional[Dict[str, Any]] = None

    # -- SQL spec --
    sql_script: Optional[str] = None      # SELECT ... (pre-existing field)
    system: Optional[str] = None          # Database system name (pre-existing field)

    # -- Assertions (universal) --
    assertions: Optional[List[Dict[str, Any]]] = None
    # Examples:
    #   {"type": "contains", "value": "healthy"}
    #   {"type": "json_path", "path": "$.status", "expected": "ok"}
    #   {"type": "status_code", "expected": 200}
    #   {"type": "not_empty"}
    #   {"type": "row_count", "operator": ">=", "value": 1}
    #   {"type": "response_time_ms", "operator": "<=", "value": 5000}


class TestCaseCreate(BaseModel):
    """Payload to create a test case manually."""

    test_case_id: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    requirement_id: Optional[uuid.UUID] = None
    test_plan_id: Optional[uuid.UUID] = None
    preconditions: Optional[str] = None
    test_steps: Optional[List[TestStepSchema]] = None
    expected_result: Optional[str] = None
    test_data: Optional[Dict[str, Any]] = None
    priority: str = Field(default="P2", pattern=r"^(P1|P2|P3|P4)$")
    category: str = Field(
        default="functional",
        pattern=r"^(functional|integration|regression|smoke|e2e|data_quality|match_rule|migration)$",
    )
    domain_tags: Optional[List[str]] = None
    execution_type: str = Field(default="api", pattern=r"^(api|ui|sql|manual|mdm|mcp)$")
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
        pattern=r"^(functional|integration|regression|smoke|e2e|data_quality|match_rule|migration)$",
    )
    domain_tags: Optional[List[str]] = None
    execution_type: Optional[str] = Field(None, pattern=r"^(api|ui|sql|manual|mdm|mcp)$")
    test_plan_id: Optional[uuid.UUID] = None
    status: Optional[str] = Field(
        None,
        pattern=r"^(draft|reviewed|approved|executed|passed|failed|blocked|deprecated)$",
    )


class TestCaseResponse(BaseModel):
    """Single test case returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: Optional[uuid.UUID] = None
    test_plan_id: Optional[uuid.UUID] = None
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
    execution_type: Optional[str] = Field(None, pattern=r"^(api|ui|sql|manual|mdm|mcp)$")


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
    version: Optional[str] = None
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
        pattern=r"^(pattern|defect|best_practice|test_case|framework_pattern|anti_pattern|compliance_rule)$",
    )
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    tags: Optional[List[str]] = None
    source_project_id: Optional[uuid.UUID] = None
    version: Optional[str] = Field(None, max_length=20, description="Semantic version e.g. 1.0")


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


class ExtractionJobResponse(BaseModel):
    """Status of an async requirement extraction job."""

    job_id: str
    status: str  # processing | completed | failed
    progress: Optional[str] = None
    result_count: Optional[int] = None
    error: Optional[str] = None


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


class UIDiscoverRequest(BaseModel):
    """Request to AI-discover UI pages using Playwright + LLM vision."""

    routes: List[str] = Field(..., min_length=1, description="Routes to discover, e.g. ['/login', '/dashboard']")
    crawl: bool = Field(default=False, description="Follow discovered navigation links to find more pages")
    max_pages: int = Field(default=20, ge=1, le=50, description="Maximum pages to discover")


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
    execution_type: Optional[str] = Field(None, pattern=r"^(api|ui|sql|manual|mdm|mcp)$")


class ChatGenerateResponse(BaseModel):
    """Response from the chat-based generation agent."""

    message: ChatMessage
    action: str = Field(..., description="question | generate | confirm")
    test_cases: Optional[List[TestCaseResponse]] = None
    suggested_config: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════
# Test Plans
# ═══════════════════════════════════════════════════════════════════════════
class TestPlanCreate(BaseModel):
    """Payload to create a test plan."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    plan_type: str = Field(
        default="custom",
        pattern=r"^(sit|uat|regression|smoke|migration|custom)$",
    )
    execution_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Execution playbook: environment, prerequisites, connection refs, env vars",
    )
    test_case_ids: Optional[List[uuid.UUID]] = Field(
        None,
        description="Test case UUIDs to bind to this plan on creation",
    )


class TestPlanUpdate(BaseModel):
    """Payload to update a test plan (partial)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    plan_type: Optional[str] = Field(
        None, pattern=r"^(sit|uat|regression|smoke|migration|custom)$"
    )
    status: Optional[str] = Field(
        None, pattern=r"^(draft|active|in_review|completed|failed)$"
    )
    execution_config: Optional[Dict[str, Any]] = None


class TestPlanResponse(BaseModel):
    """Single test plan returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: Optional[str] = None
    plan_type: str
    status: str
    execution_config: Optional[Dict[str, Any]] = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Computed stats (populated by route, not ORM)
    test_case_count: int = 0
    executed_count: int = 0
    passed_count: int = 0
    failed_count: int = 0


# ═══════════════════════════════════════════════════════════════════════════
# Execution Results
# ═══════════════════════════════════════════════════════════════════════════
class ProofArtifactSubmit(BaseModel):
    """A proof artifact submitted with an execution result."""

    proof_type: str = Field(
        ...,
        pattern=r"^(api_response|screenshot|test_output|query_result|data_comparison|dq_scorecard|log|code_diff|manual_note)$",
    )
    title: str = Field(..., min_length=1, max_length=500)
    content: Optional[Union[str, Dict[str, Any]]] = None
    file_path: Optional[str] = None


class ProofArtifactResponse(BaseModel):
    """Single proof artifact returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    execution_result_id: uuid.UUID
    proof_type: str
    title: str
    content: Optional[Union[str, Dict[str, Any]]] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    created_at: datetime


class ExecutionResultSubmit(BaseModel):
    """Payload to submit an execution result (from agent or user)."""

    test_case_id: uuid.UUID
    test_plan_id: Optional[uuid.UUID] = None
    status: str = Field(..., pattern=r"^(passed|failed|error|skipped|blocked)$")
    actual_result: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    environment: Optional[Dict[str, Any]] = None
    proof_artifacts: Optional[List[ProofArtifactSubmit]] = None


class ExecutionResultResponse(BaseModel):
    """Single execution result returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_case_id: uuid.UUID
    test_plan_id: Optional[uuid.UUID] = None
    status: str
    actual_result: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    environment: Optional[Dict[str, Any]] = None
    executed_by: str
    executed_at: datetime
    review_status: Optional[str] = None
    review_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    proof_artifacts: List[ProofArtifactResponse] = Field(default_factory=list)


class ExecutionReviewRequest(BaseModel):
    """Payload to review (approve/reject) an execution result."""

    review_status: str = Field(..., pattern=r"^(approved|rejected)$")
    review_comment: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# Agent Sessions
# ═══════════════════════════════════════════════════════════════════════════
class AgentSessionCreate(BaseModel):
    """Payload to start an agent session."""

    agent_name: str = Field(..., min_length=1, max_length=100)
    agent_version: Optional[str] = Field(None, max_length=50)
    submission_mode: str = Field(
        default="realtime", pattern=r"^(realtime|batch)$"
    )
    session_meta: Optional[Dict[str, Any]] = None


class AgentSessionResponse(BaseModel):
    """Agent session returned after creation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    agent_name: str
    agent_version: Optional[str] = None
    submission_mode: str
    started_at: datetime
    last_active_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Validation Checkpoints
# ═══════════════════════════════════════════════════════════════════════════
class ValidationCheckpointCreate(BaseModel):
    """Payload to create a validation checkpoint."""

    checkpoint_type: str = Field(
        ..., pattern=r"^(test_case_review|execution_review|sign_off)$"
    )


class ValidationCheckpointUpdate(BaseModel):
    """Payload to review a validation checkpoint."""

    status: str = Field(
        ..., pattern=r"^(approved|rejected|needs_rework)$"
    )
    comments: Optional[str] = None


class ValidationCheckpointResponse(BaseModel):
    """Single validation checkpoint returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_plan_id: uuid.UUID
    checkpoint_type: str
    status: str
    reviewer_id: Optional[uuid.UUID] = None
    comments: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Agent API — Composite Schemas
# ═══════════════════════════════════════════════════════════════════════════
class AgentRequirementSubmit(BaseModel):
    """A single requirement submitted by an agent."""

    req_id: Optional[str] = None  # Auto-generated if not provided
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = None
    priority: str = "medium"  # high | medium | low
    category: Optional[str] = None
    source: str = "agent"


class AgentRequirementBatchSubmit(BaseModel):
    """Batch requirement submission from agent."""

    requirements: List[AgentRequirementSubmit]


class AgentTestCaseSubmit(BaseModel):
    """Test case submitted by an agent (simplified, no project_id needed)."""

    test_case_id: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    requirement_id: Optional[uuid.UUID] = None
    test_plan_id: Optional[uuid.UUID] = None
    preconditions: Optional[str] = None
    test_steps: Optional[List[TestStepSchema]] = None
    expected_result: Optional[str] = None
    test_data: Optional[Dict[str, Any]] = None
    priority: str = Field(default="P2", pattern=r"^(P1|P2|P3|P4)$")
    category: str = Field(
        default="functional",
        pattern=r"^(functional|integration|regression|smoke|e2e|data_quality|match_rule|migration)$",
    )
    domain_tags: Optional[List[str]] = None
    execution_type: str = Field(default="api", pattern=r"^(api|ui|sql|manual|mdm|mcp)$")


class AgentTestCaseBatchSubmit(BaseModel):
    """Batch or single test case submission from agent."""

    test_cases: List[AgentTestCaseSubmit] = Field(..., min_length=1)
    test_plan_id: Optional[uuid.UUID] = None


class AgentExecutionSubmit(BaseModel):
    """Execution result submitted by an agent."""

    test_case_id: uuid.UUID
    test_plan_id: Optional[uuid.UUID] = None
    status: str = Field(..., pattern=r"^(passed|failed|error|skipped|blocked)$")
    actual_result: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    environment: Optional[Dict[str, Any]] = None
    proof_artifacts: Optional[List[ProofArtifactSubmit]] = None


class AgentExecutionBatchSubmit(BaseModel):
    """Batch or single execution result submission from agent."""

    executions: List[AgentExecutionSubmit] = Field(..., min_length=1)


class AgentSummaryResponse(BaseModel):
    """Progress summary returned to agent."""

    project_name: str
    test_plan_id: Optional[uuid.UUID] = None
    total_test_cases: int = 0
    by_status: Dict[str, int] = Field(default_factory=dict)
    total_executions: int = 0
    passed: int = 0
    failed: int = 0
    pending_review: int = 0
    pass_rate: Optional[float] = None


class AgentKeyResponse(BaseModel):
    """Response when generating an agent API key."""

    api_key: str = Field(..., description="Show once — store securely")
    project_id: uuid.UUID
    project_name: str


# ===================================================================
# Execution Runs (Test Plan Execution)
# ===================================================================
class ExecuteTestPlanRequest(BaseModel):
    """Payload to trigger execution of a test plan."""

    connection_id: Optional[uuid.UUID] = Field(
        None, description="Connection to use; if None, auto-creates from app_profile"
    )
    test_case_ids: Optional[List[uuid.UUID]] = Field(
        None, description="Specific test case IDs to run; if None, runs all in plan"
    )


class ExecutionRunResponse(BaseModel):
    """Execution run status returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    test_plan_id: Optional[uuid.UUID] = None
    connection_id: Optional[uuid.UUID] = None
    status: str
    results: Optional[Dict[str, Any]] = None
    triggered_by: uuid.UUID
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ConnectionCreate(BaseModel):
    """Payload to create a connection."""

    name: str = Field(..., min_length=1, max_length=255)
    connection_type: str = Field(
        default="rest_api",
        pattern=r"^(rest_api|database|mcp|graphql)$",
    )
    config: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ConnectionResponse(BaseModel):
    """Connection returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    connection_type: str
    config: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool
    created_at: datetime
