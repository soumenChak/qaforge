"""
QAForge -- Test Plan management routes.

Prefix: /api/projects (nested under project)

Endpoints:
    POST   /{pid}/test-plans              — create test plan
    GET    /{pid}/test-plans              — list test plans with stats
    GET    /{pid}/test-plans/{id}         — plan detail with stats
    PUT    /{pid}/test-plans/{id}         — update plan
    DELETE /{pid}/test-plans/{id}         — delete plan (cascades)

    GET    /{pid}/test-plans/{id}/checkpoints    — list checkpoints
    POST   /{pid}/test-plans/{id}/checkpoints    — create checkpoint
    PATCH  /{pid}/checkpoints/{id}               — review checkpoint

    GET    /{pid}/executions              — list execution results
    GET    /{pid}/executions/{id}         — execution detail with proof
    POST   /{pid}/executions/{id}/review  — approve/reject execution

    GET    /{pid}/test-plans/{id}/traceability   — RTM report
    GET    /{pid}/test-plans/{id}/summary        — executive summary
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from db_models import (
    ExecutionResult,
    Project,
    ProofArtifact,
    Requirement,
    TestCase,
    TestPlan,
    User,
    ValidationCheckpoint,
)
from db_session import get_db
from dependencies import audit_log, get_client_ip, get_current_user
from models import (
    ExecutionResultResponse,
    ExecutionReviewRequest,
    MessageResponse,
    TestPlanCreate,
    TestPlanResponse,
    TestPlanUpdate,
    ValidationCheckpointCreate,
    ValidationCheckpointResponse,
    ValidationCheckpointUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _plan_with_stats(db: Session, plan: TestPlan) -> Dict[str, Any]:
    """Convert a TestPlan ORM object to a response dict with computed stats."""
    tc_count = db.query(func.count(TestCase.id)).filter(
        TestCase.test_plan_id == plan.id
    ).scalar() or 0

    exec_stats = (
        db.query(ExecutionResult.status, func.count(ExecutionResult.id))
        .filter(ExecutionResult.test_plan_id == plan.id)
        .group_by(ExecutionResult.status)
        .all()
    )
    stats = dict(exec_stats)

    return TestPlanResponse(
        id=plan.id,
        project_id=plan.project_id,
        name=plan.name,
        description=plan.description,
        plan_type=plan.plan_type,
        status=plan.status,
        created_by=plan.created_by,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        test_case_count=tc_count,
        executed_count=sum(stats.values()),
        passed_count=stats.get("passed", 0),
        failed_count=stats.get("failed", 0),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Test Plans CRUD
# ═══════════════════════════════════════════════════════════════════════════
@router.post("/{project_id}/test-plans", response_model=TestPlanResponse)
def create_test_plan(
    project_id: uuid.UUID,
    body: TestPlanCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new test plan for the project."""
    project = _get_project_or_404(db, project_id)

    plan = TestPlan(
        id=uuid.uuid4(),
        project_id=project.id,
        name=body.name,
        description=body.description,
        plan_type=body.plan_type,
        created_by=current_user.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    audit_log(
        db, current_user.id,
        action="create_test_plan",
        entity_type="test_plan",
        entity_id=str(plan.id),
        ip_address=get_client_ip(request),
    )

    return _plan_with_stats(db, plan)


@router.get("/{project_id}/test-plans", response_model=List[TestPlanResponse])
def list_test_plans(
    project_id: uuid.UUID,
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List test plans for the project with stats."""
    _get_project_or_404(db, project_id)

    q = db.query(TestPlan).filter(TestPlan.project_id == project_id)
    if status:
        q = q.filter(TestPlan.status == status)
    plans = q.order_by(TestPlan.created_at.desc()).all()

    return [_plan_with_stats(db, p) for p in plans]


@router.get("/{project_id}/test-plans/{plan_id}", response_model=TestPlanResponse)
def get_test_plan(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get test plan detail with stats."""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id,
    ).first()
    if not plan:
        raise HTTPException(404, "Test plan not found")

    return _plan_with_stats(db, plan)


@router.put("/{project_id}/test-plans/{plan_id}", response_model=TestPlanResponse)
def update_test_plan(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: TestPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a test plan."""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id,
    ).first()
    if not plan:
        raise HTTPException(404, "Test plan not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    db.commit()
    db.refresh(plan)
    return _plan_with_stats(db, plan)


@router.delete("/{project_id}/test-plans/{plan_id}", response_model=MessageResponse)
def delete_test_plan(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a test plan (cascades to checkpoints, unlinks test cases)."""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id,
    ).first()
    if not plan:
        raise HTTPException(404, "Test plan not found")

    db.delete(plan)
    db.commit()

    audit_log(
        db, current_user.id,
        action="delete_test_plan",
        entity_type="test_plan",
        entity_id=str(plan_id),
        ip_address=get_client_ip(request),
    )

    return MessageResponse(message="Test plan deleted")


# ═══════════════════════════════════════════════════════════════════════════
# Validation Checkpoints
# ═══════════════════════════════════════════════════════════════════════════
@router.get(
    "/{project_id}/test-plans/{plan_id}/checkpoints",
    response_model=List[ValidationCheckpointResponse],
)
def list_checkpoints(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List validation checkpoints for a test plan."""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id,
    ).first()
    if not plan:
        raise HTTPException(404, "Test plan not found")

    return (
        db.query(ValidationCheckpoint)
        .filter(ValidationCheckpoint.test_plan_id == plan_id)
        .order_by(ValidationCheckpoint.created_at)
        .all()
    )


@router.post(
    "/{project_id}/test-plans/{plan_id}/checkpoints",
    response_model=ValidationCheckpointResponse,
)
def create_checkpoint(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: ValidationCheckpointCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a validation checkpoint for a test plan."""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id,
    ).first()
    if not plan:
        raise HTTPException(404, "Test plan not found")

    cp = ValidationCheckpoint(
        id=uuid.uuid4(),
        test_plan_id=plan_id,
        checkpoint_type=body.checkpoint_type,
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


@router.patch(
    "/{project_id}/checkpoints/{checkpoint_id}",
    response_model=ValidationCheckpointResponse,
)
def review_checkpoint(
    project_id: uuid.UUID,
    checkpoint_id: uuid.UUID,
    body: ValidationCheckpointUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Review a checkpoint (approve/reject/needs_rework)."""
    cp = (
        db.query(ValidationCheckpoint)
        .join(TestPlan)
        .filter(
            ValidationCheckpoint.id == checkpoint_id,
            TestPlan.project_id == project_id,
        )
        .first()
    )
    if not cp:
        raise HTTPException(404, "Checkpoint not found")

    cp.status = body.status
    cp.comments = body.comments
    cp.reviewer_id = current_user.id
    cp.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(cp)
    return cp


# ═══════════════════════════════════════════════════════════════════════════
# Execution Results (user-facing)
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/{project_id}/executions", response_model=List[ExecutionResultResponse])
def list_executions(
    project_id: uuid.UUID,
    test_plan_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List execution results for the project."""
    q = (
        db.query(ExecutionResult)
        .join(TestCase)
        .filter(TestCase.project_id == project_id)
    )
    if test_plan_id:
        q = q.filter(ExecutionResult.test_plan_id == test_plan_id)
    if status:
        q = q.filter(ExecutionResult.status == status)
    if review_status:
        q = q.filter(ExecutionResult.review_status == review_status)

    return q.order_by(ExecutionResult.executed_at.desc()).limit(200).all()


@router.get("/{project_id}/executions/{execution_id}", response_model=ExecutionResultResponse)
def get_execution(
    project_id: uuid.UUID,
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get execution result with proof artifacts."""
    result = (
        db.query(ExecutionResult)
        .join(TestCase)
        .filter(
            ExecutionResult.id == execution_id,
            TestCase.project_id == project_id,
        )
        .first()
    )
    if not result:
        raise HTTPException(404, "Execution result not found")
    return result


@router.post("/{project_id}/executions/{execution_id}/review", response_model=ExecutionResultResponse)
def review_execution(
    project_id: uuid.UUID,
    execution_id: uuid.UUID,
    body: ExecutionReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve or reject an execution result."""
    result = (
        db.query(ExecutionResult)
        .join(TestCase)
        .filter(
            ExecutionResult.id == execution_id,
            TestCase.project_id == project_id,
        )
        .first()
    )
    if not result:
        raise HTTPException(404, "Execution result not found")

    result.review_status = body.review_status
    result.review_comment = body.review_comment
    result.reviewed_by = current_user.id
    result.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(result)
    return result


@router.delete(
    "/{project_id}/test-plans/executions/{exec_id}",
    summary="Delete an execution result",
)
def delete_execution(
    project_id: uuid.UUID,
    exec_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an execution result. Cascades to proof artifacts."""
    execution = db.query(ExecutionResult).filter(ExecutionResult.id == exec_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution result not found")

    # Verify project ownership
    tc = db.query(TestCase).filter(TestCase.id == execution.test_case_id).first()
    if not tc or tc.project_id != project_id:
        raise HTTPException(status_code=404, detail="Execution result not found in this project")

    db.delete(execution)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_execution",
        entity_type="execution_result",
        entity_id=str(exec_id),
        ip_address=get_client_ip(request),
    )

    return {"message": "Execution result deleted"}


# ═══════════════════════════════════════════════════════════════════════════
# Traceability Matrix
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/{project_id}/test-plans/{plan_id}/traceability")
def get_traceability_matrix(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a Requirements Traceability Matrix (RTM).
    Maps: Requirement → Test Cases → Execution Status.
    """
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id,
    ).first()
    if not plan:
        raise HTTPException(404, "Test plan not found")

    # Get all requirements for the project
    requirements = (
        db.query(Requirement)
        .filter(Requirement.project_id == project_id)
        .order_by(Requirement.req_id)
        .all()
    )

    # Get test cases for this plan
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.test_plan_id == plan_id)
        .all()
    )

    # Build a map: requirement_id -> list of test cases
    req_tc_map: Dict[uuid.UUID, List] = {}
    orphan_tcs = []
    for tc in test_cases:
        if tc.requirement_id:
            req_tc_map.setdefault(tc.requirement_id, []).append(tc)
        else:
            orphan_tcs.append(tc)

    # Get latest execution per test case
    tc_exec_map: Dict[uuid.UUID, str] = {}
    for tc in test_cases:
        latest = (
            db.query(ExecutionResult)
            .filter(ExecutionResult.test_case_id == tc.id)
            .order_by(ExecutionResult.executed_at.desc())
            .first()
        )
        if latest:
            tc_exec_map[tc.id] = latest.status

    # Build matrix
    matrix = []
    covered = 0
    for req in requirements:
        tcs = req_tc_map.get(req.id, [])
        tc_entries = []
        for tc in tcs:
            tc_entries.append({
                "test_case_id": tc.test_case_id,
                "title": tc.title,
                "status": tc.status,
                "execution_status": tc_exec_map.get(tc.id),
            })

        if tcs:
            covered += 1

        matrix.append({
            "requirement": {
                "req_id": req.req_id,
                "title": req.title,
                "priority": req.priority,
            },
            "test_cases": tc_entries,
            "covered": len(tcs) > 0,
        })

    total_reqs = len(requirements)
    coverage_pct = (covered / total_reqs * 100) if total_reqs > 0 else 0

    return {
        "plan_id": plan_id,
        "plan_name": plan.name,
        "total_requirements": total_reqs,
        "covered_requirements": covered,
        "coverage_percentage": round(coverage_pct, 1),
        "orphan_test_cases": len(orphan_tcs),
        "matrix": matrix,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Executive Summary
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/{project_id}/test-plans/{plan_id}/summary")
def get_plan_summary(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an executive summary for a test plan."""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id,
    ).first()
    if not plan:
        raise HTTPException(404, "Test plan not found")

    # Test case stats
    tc_stats = (
        db.query(TestCase.status, func.count(TestCase.id))
        .filter(TestCase.test_plan_id == plan_id)
        .group_by(TestCase.status)
        .all()
    )
    tc_by_status = dict(tc_stats)
    total_tcs = sum(tc_by_status.values())

    # Execution stats
    ex_stats = (
        db.query(ExecutionResult.status, func.count(ExecutionResult.id))
        .filter(ExecutionResult.test_plan_id == plan_id)
        .group_by(ExecutionResult.status)
        .all()
    )
    ex_by_status = dict(ex_stats)
    total_execs = sum(ex_by_status.values())
    passed = ex_by_status.get("passed", 0)
    failed = ex_by_status.get("failed", 0)

    # Review stats
    review_stats = (
        db.query(ExecutionResult.review_status, func.count(ExecutionResult.id))
        .filter(ExecutionResult.test_plan_id == plan_id)
        .group_by(ExecutionResult.review_status)
        .all()
    )
    review_by_status = dict(review_stats)

    # Checkpoint stats
    checkpoints = (
        db.query(ValidationCheckpoint)
        .filter(ValidationCheckpoint.test_plan_id == plan_id)
        .all()
    )

    # By category
    cat_stats = (
        db.query(TestCase.category, func.count(TestCase.id))
        .filter(TestCase.test_plan_id == plan_id)
        .group_by(TestCase.category)
        .all()
    )

    # By priority
    pri_stats = (
        db.query(TestCase.priority, func.count(TestCase.id))
        .filter(TestCase.test_plan_id == plan_id)
        .group_by(TestCase.priority)
        .all()
    )

    pass_rate = (passed / total_execs * 100) if total_execs > 0 else None

    return {
        "plan": {
            "id": plan.id,
            "name": plan.name,
            "type": plan.plan_type,
            "status": plan.status,
        },
        "test_cases": {
            "total": total_tcs,
            "by_status": tc_by_status,
            "by_category": dict(cat_stats),
            "by_priority": dict(pri_stats),
        },
        "executions": {
            "total": total_execs,
            "passed": passed,
            "failed": failed,
            "errors": ex_by_status.get("error", 0),
            "skipped": ex_by_status.get("skipped", 0),
            "pass_rate": round(pass_rate, 1) if pass_rate is not None else None,
        },
        "reviews": {
            "pending": review_by_status.get("pending", 0),
            "approved": review_by_status.get("approved", 0),
            "rejected": review_by_status.get("rejected", 0),
        },
        "checkpoints": [
            {
                "type": cp.checkpoint_type,
                "status": cp.status,
                "reviewed_at": cp.reviewed_at.isoformat() if cp.reviewed_at else None,
            }
            for cp in checkpoints
        ],
    }
