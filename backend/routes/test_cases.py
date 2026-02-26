"""
QAForge -- Test case management routes.

Prefix: /api/projects/{project_id}/test-cases
(Note: main.py maps "test_cases" -> "/api/test-cases", but these routes
include the project_id in their path definitions.)

Endpoints:
    POST   /generate        — trigger AI generation pipeline
    GET    /                 — list test cases (filter, paginate)
    POST   /                 — add manual test case
    GET    /{tc_id}          — single test case detail
    PUT    /{tc_id}          — update test case
    DELETE /{tc_id}          — delete test case
    POST   /{tc_id}/rate     — rate a test case (1-5 + feedback)
    POST   /export           — export test cases to Excel (file download)
"""

import io
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from db_models import (
    FeedbackEntry,
    GenerationRun,
    KnowledgeEntry,
    Project,
    Requirement,
    TestCase,
    TestTemplate,
    User,
)
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    sanitize_string,
    track_cost,
)
from models import (
    MessageResponse,
    TestCaseCreate,
    TestCaseExportRequest,
    TestCaseGenerateRequest,
    TestCaseRateRequest,
    TestCaseResponse,
    TestCaseUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_project_or_404(project_id: uuid.UUID, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_test_case_or_404(
    tc_id: uuid.UUID, project_id: uuid.UUID, db: Session
) -> TestCase:
    tc = db.query(TestCase).filter(
        TestCase.id == tc_id,
        TestCase.project_id == project_id,
    ).first()
    if tc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Test case not found")
    return tc


# ---------------------------------------------------------------------------
# POST /{project_id}/test-cases/generate
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/test-cases/generate",
    response_model=list[TestCaseResponse],
    summary="Generate test cases using AI",
    status_code=status.HTTP_201_CREATED,
)
def generate_test_cases(
    project_id: uuid.UUID,
    body: TestCaseGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger the AI test case generation pipeline.

    Accepts a description and optional requirement_ids. Calls the pipeline
    orchestrator to generate test cases. Falls back to mock generation if
    the pipeline is not yet available.
    """
    project = _get_project_or_404(project_id, db)
    start_time = time.time()

    # ── Gather requirement context ──
    # If specific IDs provided, use those; otherwise auto-fetch ALL project requirements
    requirement_context = ""
    if body.requirement_ids:
        reqs = (
            db.query(Requirement)
            .filter(
                Requirement.id.in_(body.requirement_ids),
                Requirement.project_id == project_id,
            )
            .all()
        )
    else:
        # Auto-fetch all active requirements for the project
        reqs = (
            db.query(Requirement)
            .filter(
                Requirement.project_id == project_id,
                Requirement.status != "deferred",
            )
            .order_by(Requirement.created_at.asc())
            .limit(50)
            .all()
        )

    if reqs:
        requirement_context = "\n".join(
            f"- [{r.priority.upper()}] {r.req_id}: {r.title} -- {r.description or ''}" for r in reqs
        )
        logger.info("Requirements context: %d entries for project %s", len(reqs), project.name)

    # ── Gather BRD/PRD document text ──
    brd_prd_context = ""
    if body.brd_prd_text and body.brd_prd_text.strip():
        brd_prd_context = body.brd_prd_text.strip()[:8000]
        logger.info("BRD/PRD context: %d chars", len(brd_prd_context))

    # ── Gather reference test cases ──
    reference_tc_context = ""
    if body.reference_test_case_ids:
        ref_tcs = (
            db.query(TestCase)
            .filter(
                TestCase.id.in_(body.reference_test_case_ids),
                TestCase.project_id == project_id,
            )
            .limit(10)
            .all()
        )
        if ref_tcs:
            ref_lines = []
            for tc in ref_tcs:
                steps_summary = ""
                if tc.test_steps:
                    steps_summary = " | ".join(
                        f"Step {s.get('step_number', '?')}: {s.get('action', '')}"
                        for s in tc.test_steps[:5]
                    )
                ref_lines.append(
                    f"- {tc.test_case_id} [{tc.execution_type}] {tc.title}\n"
                    f"  Description: {tc.description or 'N/A'}\n"
                    f"  Steps: {steps_summary or 'N/A'}\n"
                    f"  Expected: {tc.expected_result or 'N/A'}"
                )
            reference_tc_context = "\n".join(ref_lines)
            logger.info("Reference TCs: %d loaded", len(ref_tcs))

    # Try the real pipeline first
    generated = _generate_via_pipeline(
        description=body.description,
        domain=body.domain,
        sub_domain=body.sub_domain,
        requirement_context=requirement_context,
        count=body.count,
        additional_context=body.additional_context,
        project_id=project_id,
        user_id=current_user.id,
        db=db,
        brd_prd_context=brd_prd_context,
        reference_tc_context=reference_tc_context,
    )

    # Save generated test cases to DB
    base_count = db.query(TestCase).filter(
        TestCase.project_id == project_id
    ).count()

    created = []
    for i, item in enumerate(generated):
        tc_id_str = f"TC-{base_count + i + 1:03d}"

        # Avoid duplicate tc_id
        existing = db.query(TestCase).filter(
            TestCase.project_id == project_id,
            TestCase.test_case_id == tc_id_str,
        ).first()
        if existing:
            tc_id_str = f"TC-{base_count + i + 100:03d}"

        # Normalise fields that the LLM may return as list instead of str
        def _to_str(val):
            if val is None:
                return None
            if isinstance(val, list):
                return "; ".join(str(v) for v in val)
            return str(val)

        # Determine execution_type: from LLM output -> from request body -> default "api"
        exec_type = item.get("execution_type", body.execution_type or "api")
        if exec_type not in ("api", "ui", "sql", "manual"):
            exec_type = "api"

        tc = TestCase(
            project_id=project_id,
            test_case_id=tc_id_str,
            title=sanitize_string(_to_str(item.get("title"))) or "Generated Test Case",
            description=sanitize_string(_to_str(item.get("description"))),
            preconditions=sanitize_string(_to_str(item.get("preconditions"))),
            test_steps=item.get("test_steps"),
            expected_result=sanitize_string(_to_str(item.get("expected_result"))),
            test_data=item.get("test_data"),
            priority=item.get("priority", body.priority or "P2"),
            category=item.get("category", body.category or "functional"),
            execution_type=exec_type,
            domain_tags=item.get("domain_tags"),
            source="ai_generated",
            status="draft",
            generated_by_model=item.get("model", "mock"),
            generation_metadata=item.get("metadata"),
            created_by=current_user.id,
        )
        db.add(tc)
        db.flush()
        created.append(tc)

    duration = time.time() - start_time

    # Track generation run
    gen_run = GenerationRun(
        project_id=project_id,
        agent_type=body.domain,
        input_context={
            "description": body.description[:500],
            "domain": body.domain,
            "sub_domain": body.sub_domain,
            "count": body.count,
        },
        test_cases_generated=len(created),
        llm_provider=generated[0].get("provider", "mock") if generated else "mock",
        llm_model=generated[0].get("model", "mock") if generated else "mock",
        duration_seconds=round(duration, 2),
    )
    db.add(gen_run)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="generate_test_cases",
        entity_type="test_case",
        entity_id=str(project_id),
        details={
            "count_requested": body.count,
            "count_generated": len(created),
            "duration_seconds": round(duration, 2),
        },
        ip_address=get_client_ip(request),
    )

    logger.info(
        "Generated %d test cases for project %s in %.1fs",
        len(created),
        project.name,
        duration,
    )

    return [TestCaseResponse.model_validate(tc) for tc in created]


def _generate_via_pipeline(
    description: str,
    domain: str,
    sub_domain: str,
    requirement_context: str,
    count: int,
    additional_context: Optional[str],
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
    brd_prd_context: str = "",
    reference_tc_context: str = "",
) -> list[dict]:
    """
    Call the pipeline orchestrator to generate test cases.

    Falls back to direct LLM generation if the pipeline is not importable.
    Falls back to mock generation if LLM also fails.
    """
    # Try importing the real pipeline (async orchestrator)
    try:
        import asyncio
        from pipeline.orchestrator import GenerateRequest, Orchestrator

        req = GenerateRequest(
            description=description,
            domain=domain,
            sub_domain=sub_domain,
            requirements=[requirement_context] if requirement_context else None,
            count=count,
            additional_context=additional_context or "",
        )
        loop = asyncio.new_event_loop()
        try:
            gen_result = loop.run_until_complete(Orchestrator().run(req))
        finally:
            loop.close()

        if gen_result and gen_result.test_cases:
            return gen_result.test_cases
    except ImportError:
        logger.info("pipeline.orchestrator not available; using direct LLM generation")
    except Exception:
        logger.warning("Pipeline generation failed; trying direct LLM", exc_info=True)

    # Try LLM-based generation directly
    try:
        return _generate_via_llm(
            description=description,
            domain=domain,
            sub_domain=sub_domain,
            requirement_context=requirement_context,
            count=count,
            additional_context=additional_context,
            project_id=project_id,
            user_id=user_id,
            db=db,
            brd_prd_context=brd_prd_context,
            reference_tc_context=reference_tc_context,
        )
    except Exception:
        logger.warning("LLM generation failed; using mock fallback", exc_info=True)

    # Mock fallback
    return _mock_generate(description, domain, sub_domain, count)


def _generate_via_llm(
    description: str,
    domain: str,
    sub_domain: str,
    requirement_context: str,
    count: int,
    additional_context: Optional[str],
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
    brd_prd_context: str = "",
    reference_tc_context: str = "",
) -> list[dict]:
    """Generate test cases by calling the LLM provider directly (uses smart model)."""
    from core.llm_provider import get_llm_provider

    # ── Query Knowledge Base for domain-relevant context ──
    kb_entries = (
        db.query(KnowledgeEntry)
        .filter(
            or_(
                KnowledgeEntry.domain == domain,
                KnowledgeEntry.domain == "general",
            )
        )
        .order_by(KnowledgeEntry.usage_count.desc(), KnowledgeEntry.created_at.desc())
        .limit(8)
        .all()
    )

    kb_context = ""
    kb_count = 0
    if kb_entries:
        kb_lines = []
        for entry in kb_entries:
            kb_lines.append(
                f"[{entry.entry_type.upper()}] {entry.title}\n{entry.content[:500]}"
            )
            entry.usage_count += 1
        kb_context = "\n\n".join(kb_lines)
        kb_count = len(kb_entries)
        db.flush()
        logger.info("KB context: %d entries for domain=%s", kb_count, domain)

    system_prompt = f"""You are a senior QA automation engineer specializing in {domain} / {sub_domain}.
You generate EXECUTION-READY test cases — each test case must contain enough detail in its test_steps
that an automated execution engine can run it without human intervention.

You understand three execution modes:
1. **API Testing** — HTTP requests with specific endpoints, methods, status codes, expected response fields
2. **UI Testing (Playwright)** — Browser automation with CSS selectors, navigation URLs, form fills, assertions
3. **SQL Testing** — Database queries with specific SQL, expected row counts, column checks

Your test steps must be CONCRETE and SPECIFIC — never vague like "verify the page works".
Instead: "GET /api/users returns 200 with fields: id, name, email" or "Click button#submit, assert .success-toast is visible".

IMPORTANT: You have been provided with the system description, requirements from BRD/PRD documents,
and possibly reference test cases. Use ALL of this context to generate high-quality, domain-specific
test cases that thoroughly cover the described system's functionality, edge cases, and integration points.

Return ONLY a JSON array — no markdown fences, no explanation."""

    # ── Build rich user prompt with all available context ──
    user_prompt_parts = [f"Generate exactly {count} EXECUTION-READY test cases for the following system."]

    user_prompt_parts.append(f"\n=== SYSTEM DESCRIPTION ===\n{description[:4000]}")

    if brd_prd_context:
        user_prompt_parts.append(
            f"\n=== BRD/PRD DOCUMENT CONTEXT ===\n"
            f"The following is extracted from the project's BRD/PRD documents. "
            f"Use this to understand the business requirements, acceptance criteria, "
            f"and expected system behavior:\n{brd_prd_context[:6000]}"
        )

    if requirement_context:
        user_prompt_parts.append(
            f"\n=== REQUIREMENTS / USE CASES ===\n"
            f"Generate test cases that cover these specific requirements:\n{requirement_context[:4000]}"
        )

    if reference_tc_context:
        user_prompt_parts.append(
            f"\n=== REFERENCE TEST CASES (match this style and level of detail) ===\n"
            f"Use these existing test cases as examples of the expected format, "
            f"detail level, and naming conventions:\n{reference_tc_context[:3000]}"
        )

    if additional_context:
        user_prompt_parts.append(f"\n=== ADDITIONAL CONTEXT ===\n{additional_context[:2000]}")

    if kb_context:
        user_prompt_parts.append(
            f"\n=== KNOWLEDGE BASE REFERENCE (use these patterns to improve test quality) ===\n{kb_context}"
        )

    user_prompt_parts.append(f"""
For each test case, return a JSON object with ALL of these fields:

- "title": Concise test case title (e.g. "Verify user login API returns JWT token")
- "description": What this test validates and why it matters
- "preconditions": Setup required (e.g. "Valid user exists with email test@example.com")
- "test_steps": Array of step objects — MUST be execution-ready (see format below)
- "expected_result": Overall expected outcome
- "priority": One of "P1", "P2", "P3", "P4"
- "category": One of "functional", "integration", "regression", "smoke", "e2e"
- "execution_type": One of "api", "ui", "sql"
- "domain_tags": Array of relevant tags

=== CRITICAL: test_steps FORMAT by execution_type ===

For "api" test cases, each step MUST reference specific HTTP details:
  {{"step_number": 1, "action": "POST /api/auth/login with body {{\\"email\\":\\"test@example.com\\",\\"password\\":\\"pass123\\"}}", "expected_result": "Returns 200 with fields: access_token, user"}}
  {{"step_number": 2, "action": "GET /api/users with Authorization: Bearer <token>", "expected_result": "Returns 200 with array of user objects containing id, name, email"}}

For "ui" test cases, each step MUST use Playwright-compatible actions and CSS selectors:
  {{"step_number": 1, "action": "Navigate to /login", "expected_result": "Login page loads with email and password fields visible"}}
  {{"step_number": 2, "action": "Fill input#email with 'admin@example.com'", "expected_result": "Email field populated"}}
  {{"step_number": 3, "action": "Fill input[type=password] with 'password123'", "expected_result": "Password field populated"}}
  {{"step_number": 4, "action": "Click button[type=submit]", "expected_result": "Form submits, redirects to /dashboard"}}
  {{"step_number": 5, "action": "Assert h1 contains text 'Dashboard'", "expected_result": "Dashboard heading visible"}}
  {{"step_number": 6, "action": "Assert URL contains /dashboard", "expected_result": "URL confirms navigation"}}

For "sql" test cases, each step MUST include actual SQL queries:
  {{"step_number": 1, "action": "Execute: SELECT COUNT(*) FROM users WHERE status = 'active'", "expected_result": "Row count >= 1"}}
  {{"step_number": 2, "action": "Execute: SELECT email FROM users WHERE id = 1", "expected_result": "Returns non-null email value"}}

=== GUIDELINES ===
- Infer execution_type from the system description: REST APIs → "api", web UI/forms/pages → "ui", databases/ETL → "sql"
- For web applications, generate a MIX of API tests (backend endpoints) and UI tests (user flows through the browser)
- UI test selectors: prefer #id, then [data-testid=...], then tag.class, then generic CSS
- API tests: include the full endpoint path starting with /
- Make test data realistic but safe (use example.com emails, test passwords, etc.)
- Each test case should be independently executable (no dependencies between test cases)
- If requirements are provided, ensure EACH requirement has at least one corresponding test case
- If BRD/PRD context is provided, derive test scenarios from the business rules and acceptance criteria described

Return ONLY the JSON array, no other text.""")

    user_prompt = "\n".join(user_prompt_parts)

    provider = get_llm_provider()
    messages = [{"role": "user", "content": user_prompt}]

    # Use the smart model for generation (Sonnet instead of Haiku)
    response = provider.complete(
        system=system_prompt,
        messages=messages,
        max_tokens=4096,
        temperature=0.4,
        model=provider.smart_model,
    )

    # Parse response — strip markdown fences if present
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]  # remove first line
        if text.endswith("```"):
            text = text[:-3].strip()

    parsed = json.loads(text)

    if isinstance(parsed, list):
        provider_name = response.provider or "unknown"
        model_name = response.model or "unknown"
        for item in parsed:
            item["provider"] = provider_name
            item["model"] = model_name
        track_cost(
            db,
            user_id=user_id,
            project_id=project_id,
            operation_type="llm",
            provider=provider_name,
            model=model_name,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
        )
        logger.info(
            "LLM generated %d test cases (%s/%s, %d tokens, %d KB entries used)",
            len(parsed), provider_name, model_name,
            response.tokens_in + response.tokens_out, kb_count,
        )
        # Attach KB metadata so the generate endpoint can track it
        for item in parsed:
            item["_kb_entries_used"] = kb_count
        return parsed

    raise ValueError("LLM did not return a JSON array")


def _mock_generate(
    description: str, domain: str, sub_domain: str, count: int
) -> list[dict]:
    """Generate mock test cases as a fallback."""
    results = []
    for i in range(min(count, 20)):
        results.append({
            "title": f"Verify {sub_domain} {domain} functionality - scenario {i + 1}",
            "description": f"Test case generated from: {description[:100]}...",
            "preconditions": f"System is configured for {domain}/{sub_domain}. Test data is loaded.",
            "test_steps": [
                {
                    "step_number": 1,
                    "action": f"Navigate to the {sub_domain} module",
                    "expected_result": f"{sub_domain} module loads successfully",
                },
                {
                    "step_number": 2,
                    "action": "Execute the primary workflow",
                    "expected_result": "Workflow completes without errors",
                },
                {
                    "step_number": 3,
                    "action": "Validate the output data",
                    "expected_result": "Output matches expected results",
                },
            ],
            "expected_result": "All validations pass successfully",
            "priority": ["P1", "P2", "P2", "P3"][i % 4],
            "category": ["functional", "integration", "regression", "smoke", "e2e"][i % 5],
            "domain_tags": [domain, sub_domain],
            "provider": "mock",
            "model": "mock",
            "metadata": {"source": "mock_generator", "version": "1.0"},
        })
    return results


# ---------------------------------------------------------------------------
# GET /{project_id}/test-cases/
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/test-cases",
    response_model=list[TestCaseResponse],
    summary="List test cases for a project",
)
def list_test_cases(
    project_id: uuid.UUID,
    test_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority (P1/P2/P3/P4)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    source: Optional[str] = Query(None, description="Filter by source (ai_generated/manual/hybrid)"),
    execution_type: Optional[str] = Query(None, description="Filter by execution type (api/ui/sql/manual)"),
    limit: int = Query(50, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List test cases for a project with optional filters and pagination.
    """
    _get_project_or_404(project_id, db)

    query = db.query(TestCase).filter(TestCase.project_id == project_id)

    if test_status:
        query = query.filter(TestCase.status == test_status)
    if priority:
        query = query.filter(TestCase.priority == priority)
    if category:
        query = query.filter(TestCase.category == category)
    if source:
        query = query.filter(TestCase.source == source)
    if execution_type:
        query = query.filter(TestCase.execution_type == execution_type)

    test_cases = (
        query.order_by(TestCase.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [TestCaseResponse.model_validate(tc) for tc in test_cases]


# ---------------------------------------------------------------------------
# POST /{project_id}/test-cases/
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/test-cases",
    response_model=TestCaseResponse,
    summary="Add a manual test case",
    status_code=status.HTTP_201_CREATED,
)
def create_test_case(
    project_id: uuid.UUID,
    body: TestCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a test case manually within a project."""
    _get_project_or_404(project_id, db)

    # Check duplicate test_case_id
    existing = db.query(TestCase).filter(
        TestCase.project_id == project_id,
        TestCase.test_case_id == body.test_case_id,
    ).first()
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Test case '{body.test_case_id}' already exists in this project",
        )

    # Validate requirement_id if provided
    if body.requirement_id:
        req = db.query(Requirement).filter(
            Requirement.id == body.requirement_id,
            Requirement.project_id == project_id,
        ).first()
        if req is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Requirement not found in this project",
            )

    tc = TestCase(
        project_id=project_id,
        requirement_id=body.requirement_id,
        test_case_id=body.test_case_id,
        title=sanitize_string(body.title) or body.title,
        description=sanitize_string(body.description) if body.description else None,
        preconditions=sanitize_string(body.preconditions) if body.preconditions else None,
        test_steps=[s.model_dump() for s in body.test_steps] if body.test_steps else None,
        expected_result=sanitize_string(body.expected_result) if body.expected_result else None,
        test_data=body.test_data,
        priority=body.priority,
        category=body.category,
        domain_tags=body.domain_tags,
        execution_type=body.execution_type,
        source=body.source,
        status="draft",
        created_by=current_user.id,
    )
    db.add(tc)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="create_test_case",
        entity_type="test_case",
        entity_id=str(tc.id),
        details={"project_id": str(project_id), "test_case_id": tc.test_case_id},
        ip_address=get_client_ip(request),
    )

    return TestCaseResponse.model_validate(tc)


# ---------------------------------------------------------------------------
# GET /{project_id}/test-cases/upload-template
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/test-cases/upload-template",
    summary="Download blank Excel template for bulk upload",
)
def download_upload_template(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns a pre-formatted Excel template with headers, validation notes,
    and 2 example rows so users know what format to use for bulk upload.
    """
    _get_project_or_404(project_id, db)

    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test Cases"

    # Header style
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2E5090", end_color="2E5090", fill_type="solid")
    note_font = Font(italic=True, color="888888", size=9)

    headers = [
        "Test Case ID *",
        "Title *",
        "Description",
        "Preconditions",
        "Priority",
        "Category",
        "Execution Type",
        "Test Steps",
        "Expected Result",
    ]

    # Write headers
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    # Validation notes row
    notes = [
        "Unique ID, e.g. TC-001",
        "Short descriptive title",
        "What does this test validate?",
        "Setup steps needed before test",
        "P1 / P2 / P3 / P4",
        "functional / integration / regression / smoke / e2e",
        "api / ui / sql / manual",
        "Format: 1. Action -> Expected\n2. Action -> Expected",
        "Overall expected outcome",
    ]
    for col_idx, note in enumerate(notes, 1):
        cell = ws.cell(row=2, column=col_idx, value=note)
        cell.font = note_font
        cell.alignment = Alignment(wrap_text=True)

    # Example rows
    examples = [
        [
            "TC-001",
            "Verify user login returns JWT",
            "Test that valid credentials return a JWT access token",
            "Test user exists: test@example.com / pass123",
            "P1",
            "functional",
            "api",
            '1. POST /api/auth/login with {"email":"test@example.com","password":"pass123"} -> Returns 200 with access_token\n2. Decode JWT -> Contains user_id and exp fields',
            "User receives a valid JWT token on successful login",
        ],
        [
            "TC-002",
            "Verify dashboard loads after login",
            "Test that authenticated user can see the dashboard",
            "User is logged in with valid session",
            "P2",
            "ui",
            "ui",
            "1. Navigate to /dashboard -> Page loads with heading 'Dashboard'\n2. Assert sidebar menu has 'Projects' link -> Link is visible and clickable",
            "Dashboard page renders correctly with navigation",
        ],
    ]
    for row_idx, example in enumerate(examples, 3):
        for col_idx, value in enumerate(example, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = Alignment(wrap_text=True)

    # Column widths
    widths = [16, 35, 35, 30, 10, 15, 15, 60, 35]
    for col_idx, width in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

    # Freeze top 2 rows
    ws.freeze_panes = "A3"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=test_case_template_{project_id}.xlsx"
        },
    )


# ---------------------------------------------------------------------------
# POST /{project_id}/test-cases/bulk-upload — MUST be before {tc_id} routes
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/test-cases/bulk-upload",
    summary="Bulk upload test cases from Excel file",
    status_code=status.HTTP_201_CREATED,
)
async def bulk_upload_test_cases(
    project_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(..., description="Excel (.xlsx) file with test cases"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Parse an uploaded Excel file and create test cases in bulk.

    Expects columns matching the download template:
    Test Case ID, Title, Description, Preconditions, Priority, Category,
    Execution Type, Test Steps, Expected Result.

    Skips the notes row (row 2) and example rows if present.
    Returns a summary of created / skipped / errored rows.
    """
    _get_project_or_404(project_id, db)

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Only Excel files (.xlsx) are supported. Download the template first.",
        )

    import openpyxl

    try:
        content = await file.read()
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot read Excel file: {exc}",
        )

    # Parse rows (skip header row 1 and notes row 2)
    created = []
    skipped = []
    errors = []

    # Get the next TC number for auto-ID generation
    max_tc = (
        db.query(TestCase.test_case_id)
        .filter(TestCase.project_id == project_id)
        .all()
    )
    existing_ids = {row[0] for row in max_tc}

    VALID_PRIORITIES = {"P1", "P2", "P3", "P4"}
    VALID_CATEGORIES = {"functional", "integration", "regression", "smoke", "e2e"}
    VALID_EXEC_TYPES = {"api", "ui", "sql", "manual"}

    for row_idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        # Skip completely empty rows
        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
            continue

        # Pad row to 9 columns
        cells = list(row) + [None] * max(0, 9 - len(row))
        tc_id = str(cells[0] or "").strip()
        title = str(cells[1] or "").strip()

        # Skip notes/example hint rows
        if tc_id.lower().startswith("unique id") or title.lower().startswith("short descriptive"):
            continue

        # Validate required fields
        if not tc_id or not title:
            errors.append({"row": row_idx, "error": "Missing Test Case ID or Title"})
            continue

        if tc_id in existing_ids:
            skipped.append({"row": row_idx, "tc_id": tc_id, "reason": "Duplicate ID"})
            continue

        description = str(cells[2] or "").strip() or None
        preconditions = str(cells[3] or "").strip() or None
        priority = str(cells[4] or "P2").strip().upper()
        category = str(cells[5] or "functional").strip().lower()
        exec_type = str(cells[6] or "manual").strip().lower()
        steps_text = str(cells[7] or "").strip()
        expected_result = str(cells[8] or "").strip() or None

        # Validate enum values
        if priority not in VALID_PRIORITIES:
            priority = "P2"
        if category not in VALID_CATEGORIES:
            category = "functional"
        if exec_type not in VALID_EXEC_TYPES:
            exec_type = "manual"

        # Parse test steps from text format: "1. Action -> Expected\n2. ..."
        test_steps = None
        if steps_text:
            test_steps = []
            import re
            step_lines = re.split(r"\n+", steps_text)
            for snum, line in enumerate(step_lines, 1):
                line = line.strip()
                if not line:
                    continue
                # Remove leading step number like "1." or "1)"
                line = re.sub(r"^\d+[\.\)]\s*", "", line)
                if " -> " in line:
                    action, exp = line.split(" -> ", 1)
                else:
                    action, exp = line, ""
                test_steps.append({
                    "step_number": snum,
                    "action": action.strip(),
                    "expected_result": exp.strip(),
                })

        try:
            tc = TestCase(
                project_id=project_id,
                test_case_id=tc_id,
                title=sanitize_string(title) or title,
                description=sanitize_string(description) if description else None,
                preconditions=sanitize_string(preconditions) if preconditions else None,
                test_steps=test_steps,
                expected_result=sanitize_string(expected_result) if expected_result else None,
                priority=priority,
                category=category,
                execution_type=exec_type,
                source="manual",
                status="draft",
                created_by=current_user.id,
            )
            db.add(tc)
            db.flush()
            existing_ids.add(tc_id)
            created.append({"row": row_idx, "tc_id": tc_id, "title": title})
        except Exception as exc:
            db.rollback()
            errors.append({"row": row_idx, "tc_id": tc_id, "error": str(exc)})

    # Commit all successful creates
    if created:
        db.commit()

    audit_log(
        db,
        user_id=current_user.id,
        action="bulk_upload_test_cases",
        entity_type="test_case",
        entity_id=str(project_id),
        details={
            "created": len(created),
            "skipped": len(skipped),
            "errors": len(errors),
            "filename": file.filename,
        },
        ip_address=get_client_ip(request),
    )

    return {
        "created": len(created),
        "skipped": len(skipped),
        "errors": len(errors),
        "details": {
            "created": created,
            "skipped": skipped,
            "errors": errors,
        },
    }


# ---------------------------------------------------------------------------
# GET /{project_id}/test-cases/{tc_id}
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/test-cases/{tc_id}",
    response_model=TestCaseResponse,
    summary="Get a single test case",
)
def get_test_case(
    project_id: uuid.UUID,
    tc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single test case by ID."""
    _get_project_or_404(project_id, db)
    tc = _get_test_case_or_404(tc_id, project_id, db)
    return TestCaseResponse.model_validate(tc)


# ---------------------------------------------------------------------------
# PUT /{project_id}/test-cases/{tc_id}
# ---------------------------------------------------------------------------
@router.put(
    "/{project_id}/test-cases/{tc_id}",
    response_model=TestCaseResponse,
    summary="Update a test case",
)
def update_test_case(
    project_id: uuid.UUID,
    tc_id: uuid.UUID,
    body: TestCaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update fields of an existing test case."""
    _get_project_or_404(project_id, db)
    tc = _get_test_case_or_404(tc_id, project_id, db)

    if body.title is not None:
        tc.title = sanitize_string(body.title) or body.title
    if body.description is not None:
        tc.description = sanitize_string(body.description)
    if body.preconditions is not None:
        tc.preconditions = sanitize_string(body.preconditions)
    if body.test_steps is not None:
        tc.test_steps = [s.model_dump() for s in body.test_steps]
    if body.expected_result is not None:
        tc.expected_result = sanitize_string(body.expected_result)
    if body.test_data is not None:
        tc.test_data = body.test_data
    if body.priority is not None:
        tc.priority = body.priority
    if body.category is not None:
        tc.category = body.category
    if body.domain_tags is not None:
        tc.domain_tags = body.domain_tags
    if body.execution_type is not None:
        tc.execution_type = body.execution_type
    if body.status is not None:
        tc.status = body.status

    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="update_test_case",
        entity_type="test_case",
        entity_id=str(tc.id),
        details=body.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )

    return TestCaseResponse.model_validate(tc)


# ---------------------------------------------------------------------------
# DELETE /{project_id}/test-cases/{tc_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{project_id}/test-cases/{tc_id}",
    response_model=MessageResponse,
    summary="Delete a test case",
)
def delete_test_case(
    project_id: uuid.UUID,
    tc_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a test case from a project."""
    _get_project_or_404(project_id, db)
    tc = _get_test_case_or_404(tc_id, project_id, db)

    tc_display = tc.test_case_id
    db.delete(tc)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_test_case",
        entity_type="test_case",
        entity_id=str(tc_id),
        details={"project_id": str(project_id), "test_case_id": tc_display},
        ip_address=get_client_ip(request),
    )

    return MessageResponse(message=f"Test case '{tc_display}' deleted")


# ---------------------------------------------------------------------------
# POST /{project_id}/test-cases/{tc_id}/rate
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/test-cases/{tc_id}/rate",
    response_model=TestCaseResponse,
    summary="Rate a test case",
)
def rate_test_case(
    project_id: uuid.UUID,
    tc_id: uuid.UUID,
    body: TestCaseRateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rate a test case (1-5 stars) with optional feedback text.

    Creates a FeedbackEntry and updates the test case's rating.
    """
    _get_project_or_404(project_id, db)
    tc = _get_test_case_or_404(tc_id, project_id, db)

    # Create feedback entry
    feedback = FeedbackEntry(
        test_case_id=tc.id,
        rating=body.rating,
        original_content={
            "title": tc.title,
            "description": tc.description,
            "test_steps": tc.test_steps,
        },
        feedback_text=sanitize_string(body.feedback_text) if body.feedback_text else None,
        feedback_type="quality",
        created_by=current_user.id,
    )
    db.add(feedback)

    # Update test case rating (keep the latest rating)
    tc.rating = body.rating
    tc.rating_feedback = sanitize_string(body.feedback_text) if body.feedback_text else None

    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="rate_test_case",
        entity_type="test_case",
        entity_id=str(tc.id),
        details={"rating": body.rating, "test_case_id": tc.test_case_id},
        ip_address=get_client_ip(request),
    )

    return TestCaseResponse.model_validate(tc)


# ---------------------------------------------------------------------------
# POST /{project_id}/test-cases/export
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/test-cases/export",
    summary="Export test cases to Excel",
)
def export_test_cases(
    project_id: uuid.UUID,
    body: TestCaseExportRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export selected test cases to an Excel file.

    Returns the file as a downloadable attachment.
    """
    _get_project_or_404(project_id, db)

    # Fetch requested test cases
    test_cases = (
        db.query(TestCase)
        .filter(
            TestCase.id.in_(body.test_case_ids),
            TestCase.project_id == project_id,
        )
        .order_by(TestCase.test_case_id.asc())
        .all()
    )

    if not test_cases:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No test cases found for the given IDs",
        )

    # Try openpyxl for Excel generation
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Test Cases"

        # Header style
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2E5090", end_color="2E5090", fill_type="solid")

        # Define columns
        headers = [
            "Test Case ID",
            "Title",
            "Description",
            "Preconditions",
            "Priority",
            "Category",
            "Status",
            "Source",
        ]
        if body.include_steps:
            headers.append("Test Steps")
        headers.append("Expected Result")
        if body.include_test_data:
            headers.append("Test Data")

        # Write headers
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        # Write data rows
        for row_idx, tc in enumerate(test_cases, 2):
            col = 1
            ws.cell(row=row_idx, column=col, value=tc.test_case_id); col += 1
            ws.cell(row=row_idx, column=col, value=tc.title); col += 1
            ws.cell(row=row_idx, column=col, value=tc.description or ""); col += 1
            ws.cell(row=row_idx, column=col, value=tc.preconditions or ""); col += 1
            ws.cell(row=row_idx, column=col, value=tc.priority); col += 1
            ws.cell(row=row_idx, column=col, value=tc.category); col += 1
            ws.cell(row=row_idx, column=col, value=tc.status); col += 1
            ws.cell(row=row_idx, column=col, value=tc.source); col += 1

            if body.include_steps and tc.test_steps:
                steps_text = "\n".join(
                    f"{s.get('step_number', i+1)}. {s.get('action', '')} -> {s.get('expected_result', '')}"
                    for i, s in enumerate(tc.test_steps)
                )
                cell = ws.cell(row=row_idx, column=col, value=steps_text)
                cell.alignment = Alignment(wrap_text=True)
                col += 1
            elif body.include_steps:
                ws.cell(row=row_idx, column=col, value=""); col += 1

            ws.cell(row=row_idx, column=col, value=tc.expected_result or ""); col += 1

            if body.include_test_data:
                ws.cell(
                    row=row_idx,
                    column=col,
                    value=json.dumps(tc.test_data, indent=2) if tc.test_data else "",
                )
                col += 1

        # Auto-width columns
        for col_idx in range(1, len(headers) + 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 20

        # Save to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        audit_log(
            db,
            user_id=current_user.id,
            action="export_test_cases",
            entity_type="test_case",
            entity_id=str(project_id),
            details={"count": len(test_cases), "format": body.format},
            ip_address=get_client_ip(request),
        )

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=test_cases_{project_id}.xlsx"
            },
        )

    except ImportError:
        # Fallback to CSV if openpyxl not installed
        logger.warning("openpyxl not installed; falling back to CSV export")
        return _export_csv(test_cases, project_id, body, current_user, request, db)


def _export_csv(
    test_cases: list[TestCase],
    project_id: uuid.UUID,
    body: TestCaseExportRequest,
    current_user: User,
    request: Request,
    db: Session,
) -> StreamingResponse:
    """Fallback CSV export when openpyxl is not available."""
    import csv

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    headers = [
        "Test Case ID", "Title", "Description", "Preconditions",
        "Priority", "Category", "Status", "Source", "Expected Result",
    ]
    writer.writerow(headers)

    for tc in test_cases:
        writer.writerow([
            tc.test_case_id,
            tc.title,
            tc.description or "",
            tc.preconditions or "",
            tc.priority,
            tc.category,
            tc.status,
            tc.source,
            tc.expected_result or "",
        ])

    audit_log(
        db,
        user_id=current_user.id,
        action="export_test_cases",
        entity_type="test_case",
        entity_id=str(project_id),
        details={"count": len(test_cases), "format": "csv"},
        ip_address=get_client_ip(request),
    )

    content = buffer.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=test_cases_{project_id}.csv"
        },
    )
