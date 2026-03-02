"""
QAForge -- Agent API routes.

Endpoints for AI agents (Claude Code, Codex, Gemini CLI) to submit
test cases, execution results, and proof artifacts.

Auth: X-Agent-Key header (project-scoped API key, no JWT needed).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db_models import (
    AgentSession,
    ExecutionResult,
    ProofArtifact,
    TestCase,
    TestPlan,
    Project,
)
from db_session import get_db
from dependencies import get_agent_project
from models import (
    AgentExecutionBatchSubmit,
    AgentSessionCreate,
    AgentSessionResponse,
    AgentSummaryResponse,
    AgentTestCaseBatchSubmit,
    ExecutionResultResponse,
    ProofArtifactResponse,
    ProofArtifactSubmit,
    TestCaseResponse,
    TestPlanCreate,
    TestPlanResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Project metadata (agent can populate app profile, description, BRD/PRD)
# ---------------------------------------------------------------------------
@router.put("/project", response_model=dict)
def update_project_metadata(
    body: dict,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """
    Update the authenticated project's metadata.
    Agents can set: app_profile, description, brd_prd_text.
    """
    allowed_fields = {"app_profile", "description", "brd_prd_text"}
    updated = []

    for field in allowed_fields:
        if field in body:
            setattr(project, field, body[field])
            updated.append(field)

    if updated:
        project.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Agent updated project %s fields: %s", project.name, updated)

    return {
        "project_id": str(project.id),
        "project_name": project.name,
        "updated_fields": updated,
    }


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
@router.post("/sessions", response_model=AgentSessionResponse)
def create_agent_session(
    body: AgentSessionCreate,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Start a new agent session for the authenticated project."""
    session = AgentSession(
        id=uuid.uuid4(),
        project_id=project.id,
        agent_name=body.agent_name,
        agent_version=body.agent_version,
        submission_mode=body.submission_mode,
        session_meta=body.session_meta,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(
        "Agent session started: %s (%s) for project %s [%s mode]",
        body.agent_name,
        session.id,
        project.name,
        body.submission_mode,
    )
    return session


# ---------------------------------------------------------------------------
# Test Plans (agent can create plans to group test cases + results)
# ---------------------------------------------------------------------------
@router.post("/test-plans", response_model=TestPlanResponse)
def create_test_plan(
    body: TestPlanCreate,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Create a test plan so agent can group test cases and execution results."""
    plan = TestPlan(
        id=uuid.uuid4(),
        project_id=project.id,
        name=body.name,
        description=body.description,
        plan_type=body.plan_type,
        status="active",
        created_by=project.created_by,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    logger.info(
        "Agent created test plan '%s' (%s) for project %s",
        body.name,
        plan.id,
        project.name,
    )
    return plan


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
@router.post("/test-cases", response_model=List[TestCaseResponse])
def submit_test_cases(
    body: AgentTestCaseBatchSubmit,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """
    Submit one or more test cases. They are stored with status=draft
    and source=ai_generated, pending human QA review.
    """
    created = []
    for tc in body.test_cases:
        plan_id = tc.test_plan_id or body.test_plan_id

        # Validate test_plan belongs to this project if specified
        if plan_id:
            plan = db.query(TestPlan).filter(
                TestPlan.id == plan_id,
                TestPlan.project_id == project.id,
            ).first()
            if not plan:
                raise HTTPException(400, f"Test plan {plan_id} not found in project")

        # Check for duplicate test_case_id within project
        existing = db.query(TestCase).filter(
            TestCase.project_id == project.id,
            TestCase.test_case_id == tc.test_case_id,
        ).first()
        if existing:
            raise HTTPException(
                409,
                f"Test case ID '{tc.test_case_id}' already exists in project",
            )

        test_case = TestCase(
            id=uuid.uuid4(),
            project_id=project.id,
            test_plan_id=plan_id,
            requirement_id=tc.requirement_id,
            test_case_id=tc.test_case_id,
            title=tc.title,
            description=tc.description,
            preconditions=tc.preconditions,
            test_steps=[s.model_dump() for s in tc.test_steps] if tc.test_steps else None,
            expected_result=tc.expected_result,
            test_data=tc.test_data,
            priority=tc.priority,
            category=tc.category,
            domain_tags=tc.domain_tags,
            execution_type=tc.execution_type,
            source="ai_generated",
            status="draft",
            created_by=project.created_by,  # attribute to project owner
        )
        db.add(test_case)
        created.append(test_case)

    db.commit()
    for tc in created:
        db.refresh(tc)

    logger.info(
        "Agent submitted %d test cases for project %s",
        len(created),
        project.name,
    )
    return created


@router.get("/test-cases", response_model=List[TestCaseResponse])
def get_test_cases(
    status: Optional[str] = Query(None, description="Filter by status"),
    test_plan_id: Optional[uuid.UUID] = Query(None),
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Get test cases for the authenticated project, optionally filtered."""
    q = db.query(TestCase).filter(TestCase.project_id == project.id)
    if status:
        q = q.filter(TestCase.status == status)
    if test_plan_id:
        q = q.filter(TestCase.test_plan_id == test_plan_id)
    return q.order_by(TestCase.created_at).all()


# ---------------------------------------------------------------------------
# Execution Results
# ---------------------------------------------------------------------------
@router.post("/executions", response_model=List[ExecutionResultResponse])
def submit_executions(
    body: AgentExecutionBatchSubmit,
    session_id: Optional[uuid.UUID] = Query(None, description="Agent session ID"),
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """
    Submit one or more execution results with proof artifacts.
    Each result is linked to a test case.
    """
    # Validate session if provided
    agent_session = None
    if session_id:
        agent_session = db.query(AgentSession).filter(
            AgentSession.id == session_id,
            AgentSession.project_id == project.id,
        ).first()
        if not agent_session:
            raise HTTPException(400, f"Agent session {session_id} not found")
        # Update last_active_at
        agent_session.last_active_at = datetime.now(timezone.utc)

    created = []
    for ex in body.executions:
        # Validate test case belongs to this project
        test_case = db.query(TestCase).filter(
            TestCase.id == ex.test_case_id,
            TestCase.project_id == project.id,
        ).first()
        if not test_case:
            raise HTTPException(
                400,
                f"Test case {ex.test_case_id} not found in project",
            )

        result = ExecutionResult(
            id=uuid.uuid4(),
            test_case_id=ex.test_case_id,
            test_plan_id=ex.test_plan_id or test_case.test_plan_id,
            status=ex.status,
            actual_result=ex.actual_result,
            duration_ms=ex.duration_ms,
            error_message=ex.error_message,
            environment=ex.environment,
            executed_by=agent_session.agent_name if agent_session else "agent",
            agent_session_id=session_id,
            review_status="pending",
        )
        db.add(result)
        db.flush()  # get result.id for proof artifacts

        # Add proof artifacts
        if ex.proof_artifacts:
            for pa in ex.proof_artifacts:
                artifact = ProofArtifact(
                    id=uuid.uuid4(),
                    execution_result_id=result.id,
                    proof_type=pa.proof_type,
                    title=pa.title,
                    content=pa.content,
                    file_path=pa.file_path,
                )
                db.add(artifact)

        # Update test case status to reflect execution
        test_case.status = "executed" if ex.status in ("passed", "failed") else ex.status
        if ex.status == "passed":
            test_case.status = "passed"
        elif ex.status == "failed":
            test_case.status = "failed"

        created.append(result)

    db.commit()
    for r in created:
        db.refresh(r)

    logger.info(
        "Agent submitted %d execution results for project %s",
        len(created),
        project.name,
    )
    return created


@router.post("/executions/{execution_id}/proof", response_model=ProofArtifactResponse)
def add_proof_artifact(
    execution_id: uuid.UUID,
    body: ProofArtifactSubmit,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Add a proof artifact to an existing execution result."""
    result = db.query(ExecutionResult).join(TestCase).filter(
        ExecutionResult.id == execution_id,
        TestCase.project_id == project.id,
    ).first()
    if not result:
        raise HTTPException(404, "Execution result not found")

    artifact = ProofArtifact(
        id=uuid.uuid4(),
        execution_result_id=execution_id,
        proof_type=body.proof_type,
        title=body.title,
        content=body.content,
        file_path=body.file_path,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
@router.get("/summary", response_model=AgentSummaryResponse)
def get_summary(
    test_plan_id: Optional[uuid.UUID] = Query(None),
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Get progress summary for the project (or a specific test plan)."""
    tc_query = db.query(TestCase).filter(TestCase.project_id == project.id)
    ex_query = db.query(ExecutionResult).join(TestCase).filter(
        TestCase.project_id == project.id
    )

    if test_plan_id:
        tc_query = tc_query.filter(TestCase.test_plan_id == test_plan_id)
        ex_query = ex_query.filter(ExecutionResult.test_plan_id == test_plan_id)

    test_cases = tc_query.all()
    executions = ex_query.all()

    by_status = {}
    for tc in test_cases:
        by_status[tc.status] = by_status.get(tc.status, 0) + 1

    passed = sum(1 for e in executions if e.status == "passed")
    failed = sum(1 for e in executions if e.status == "failed")
    pending_review = sum(1 for e in executions if e.review_status == "pending")

    total_exec = len(executions)
    pass_rate = (passed / total_exec * 100) if total_exec > 0 else None

    return AgentSummaryResponse(
        project_name=project.name,
        test_plan_id=test_plan_id,
        total_test_cases=len(test_cases),
        by_status=by_status,
        total_executions=total_exec,
        passed=passed,
        failed=failed,
        pending_review=pending_review,
        pass_rate=round(pass_rate, 1) if pass_rate is not None else None,
    )
