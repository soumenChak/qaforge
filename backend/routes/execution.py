"""
QAForge -- Execution run management routes.

Prefix: /api/execution

Endpoints:
    POST   /              — create & queue execution run
    GET    /              — list runs (filter by project_id, status)
    GET    /{run_id}      — full run detail with results
    GET    /{run_id}/status — lightweight poll (status + progress)
    POST   /{run_id}/cancel — cancel a running execution
    DELETE /{run_id}      — delete a completed/failed/cancelled run
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from db_models import Connection, ExecutionRun, TestAgent, TestCase, User
from db_session import get_db
from dependencies import audit_log, get_client_ip, get_current_user
from execution.engine import run_execution
from models import (
    ExecutionRunCreate,
    ExecutionRunResponse,
    ExecutionRunStatus,
    MessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=ExecutionRunResponse,
    summary="Create and queue an execution run",
    status_code=status.HTTP_201_CREATED,
)
def create_execution_run(
    body: ExecutionRunCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new execution run and kick off background execution."""

    # Validate test case IDs exist
    existing_ids = set()
    for tc_id in body.test_case_ids:
        tc = db.query(TestCase).filter(TestCase.id == tc_id).first()
        if tc is None:
            raise HTTPException(
                status_code=400,
                detail=f"Test case {tc_id} not found",
            )
        existing_ids.add(tc_id)

    # Validate connection if provided
    if body.connection_id:
        conn = db.query(Connection).filter(Connection.id == body.connection_id).first()
        if conn is None:
            raise HTTPException(status_code=400, detail="Connection not found")

    # Validate agent if provided
    if body.test_agent_id:
        agent = db.query(TestAgent).filter(TestAgent.id == body.test_agent_id).first()
        if agent is None:
            raise HTTPException(status_code=400, detail="Test agent not found")

    run = ExecutionRun(
        project_id=body.project_id,
        test_agent_id=body.test_agent_id,
        test_case_ids=[str(tid) for tid in body.test_case_ids],
        connection_id=body.connection_id,
        status="queued",
        executed_by=current_user.id,
    )
    db.add(run)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="create_execution_run",
        entity_type="execution_run",
        entity_id=str(run.id),
        details={
            "project_id": str(body.project_id),
            "test_case_count": len(body.test_case_ids),
        },
        ip_address=get_client_ip(request),
    )

    # Commit NOW so the background task (which uses its own DB session)
    # can see the run row. Without this, the background task may start
    # before the get_db() dependency auto-commits on response completion.
    db.commit()

    logger.info(
        "Execution run created: %s (%d test cases) by %s",
        run.id, len(body.test_case_ids), current_user.email,
    )

    # Schedule background execution
    background_tasks.add_task(run_execution, run.id)

    return ExecutionRunResponse.model_validate(run)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=list[ExecutionRunResponse],
    summary="List execution runs",
)
def list_execution_runs(
    project_id: Optional[uuid.UUID] = Query(None),
    run_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ExecutionRun)
    if project_id:
        query = query.filter(ExecutionRun.project_id == project_id)
    if run_status:
        query = query.filter(ExecutionRun.status == run_status)

    runs = query.order_by(ExecutionRun.started_at.desc().nullslast()).limit(limit).all()
    return [ExecutionRunResponse.model_validate(r) for r in runs]


# ---------------------------------------------------------------------------
# GET /{run_id}
# ---------------------------------------------------------------------------
@router.get(
    "/{run_id}",
    response_model=ExecutionRunResponse,
    summary="Get execution run detail",
)
def get_execution_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Execution run not found")
    return ExecutionRunResponse.model_validate(run)


# ---------------------------------------------------------------------------
# GET /{run_id}/status
# ---------------------------------------------------------------------------
@router.get(
    "/{run_id}/status",
    response_model=ExecutionRunStatus,
    summary="Lightweight execution status for polling",
)
def get_execution_status(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Execution run not found")

    # Calculate elapsed time
    elapsed = None
    if run.started_at:
        end = run.completed_at or datetime.now(timezone.utc)
        elapsed = (end - run.started_at).total_seconds()

    # Extract progress from results
    progress = None
    if run.results and isinstance(run.results, dict):
        progress = run.results.get("summary")

    return ExecutionRunStatus(
        id=run.id,
        status=run.status,
        progress=progress,
        started_at=run.started_at,
        elapsed_seconds=round(elapsed, 1) if elapsed else None,
    )


# ---------------------------------------------------------------------------
# POST /{run_id}/cancel
# ---------------------------------------------------------------------------
@router.post(
    "/{run_id}/cancel",
    response_model=MessageResponse,
    summary="Cancel a running execution",
)
def cancel_execution_run(
    run_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Execution run not found")

    if run.status not in ("queued", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status '{run.status}'",
        )

    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="cancel_execution_run",
        entity_type="execution_run",
        entity_id=str(run_id),
        details={},
        ip_address=get_client_ip(request),
    )

    return MessageResponse(message="Execution run cancelled")


# ---------------------------------------------------------------------------
# DELETE /{run_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{run_id}",
    response_model=MessageResponse,
    summary="Delete an execution run",
)
def delete_execution_run(
    run_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Execution run not found")

    if run.status in ("queued", "running"):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a run that is still in progress. Cancel it first.",
        )

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_execution_run",
        entity_type="execution_run",
        entity_id=str(run_id),
        details={"project_id": str(run.project_id), "status": run.status},
        ip_address=get_client_ip(request),
    )

    db.delete(run)
    db.flush()

    return MessageResponse(message="Execution run deleted")
