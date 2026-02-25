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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from db_models import (
    FeedbackEntry,
    GenerationRun,
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

    # Gather requirement context if IDs provided
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
        requirement_context = "\n".join(
            f"- {r.req_id}: {r.title} -- {r.description or ''}" for r in reqs
        )

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
) -> list[dict]:
    """
    Call the pipeline orchestrator to generate test cases.

    Falls back to mock generation if the pipeline is not importable.
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
) -> list[dict]:
    """Generate test cases by calling the LLM provider directly."""
    from core.llm_provider import get_llm_provider

    system_prompt = f"""You are a senior QA engineer specializing in {domain} / {sub_domain}.
You generate thorough, detailed test cases that a QA team can execute immediately.
Return ONLY a JSON array — no markdown fences, no explanation."""

    user_prompt = f"""Generate exactly {count} test cases for the following system description.

System Description:
{description[:4000]}

{f"Requirements Context:{chr(10)}{requirement_context[:3000]}" if requirement_context else ""}
{f"Additional Context:{chr(10)}{additional_context[:2000]}" if additional_context else ""}

For each test case, return a JSON array of objects with:
- "title": Concise test case title
- "description": What this test validates
- "preconditions": Setup required before execution
- "test_steps": Array of {{"step_number": N, "action": "...", "expected_result": "..."}}
- "expected_result": Overall expected outcome
- "priority": One of "P1", "P2", "P3", "P4"
- "category": One of "functional", "integration", "regression", "smoke", "e2e"
- "domain_tags": Array of relevant tags

Return ONLY the JSON array, no other text."""

    provider = get_llm_provider()
    messages = [{"role": "user", "content": user_prompt}]
    response = provider.complete(
        system=system_prompt,
        messages=messages,
        max_tokens=4096,
        temperature=0.4,
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
            "LLM generated %d test cases (%s/%s, %d tokens)",
            len(parsed), provider_name, model_name,
            response.tokens_in + response.tokens_out,
        )
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
