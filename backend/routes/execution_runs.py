"""
QAForge -- Execution Run routes (test plan execution).

Prefix: /api/projects (nested under project)

Endpoints:
    POST   /{pid}/test-plans/{tpid}/execute       -- trigger execution
    GET    /{pid}/execution-runs                   -- list runs for project
    GET    /{pid}/execution-runs/{run_id}          -- get run detail + progress
    POST   /{pid}/execution-runs/{run_id}/cancel   -- cancel running execution
    DELETE /{pid}/execution-runs/{run_id}          -- delete an execution run
    GET    /{pid}/connections                       -- list connections
    POST   /{pid}/connections                       -- create connection
"""

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from db_models import Connection, ExecutionRun, Project, TestCase, TestPlan, User
from db_session import get_db
from dependencies import audit_log, get_client_ip, get_current_user
from models import (
    ConnectionCreate,
    ConnectionResponse,
    ExecuteTestPlanRequest,
    ExecutionRunResponse,
    MessageResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_project_or_404(project_id: uuid.UUID, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _auto_create_connection(
    db: Session, project: Project, user_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    """Auto-create a Connection from the project's app_profile."""
    profile = project.app_profile or {}
    if not profile.get("api_base_url") and not profile.get("app_url"):
        return None

    config = {}
    if profile.get("api_base_url"):
        config["base_url"] = profile["api_base_url"]
    if profile.get("app_url"):
        config["app_url"] = profile["app_url"]

    auth = profile.get("auth", {})
    if auth.get("login_endpoint"):
        config["login_endpoint"] = auth["login_endpoint"]
    if auth.get("test_credentials"):
        config["credentials"] = auth["test_credentials"]
    elif auth.get("request_body"):
        config["credentials"] = auth["request_body"]
    if auth.get("token_field") or auth.get("response_fields"):
        config["token_field"] = auth.get("token_field") or (
            auth["response_fields"][0] if auth.get("response_fields") else "access_token"
        )

    # Include API endpoints as execution_context for the engine
    if profile.get("api_endpoints"):
        config["execution_context"] = "\n".join(
            f"{ep.get('method', 'GET')} {ep.get('path', '')} — {ep.get('description', '')}"
            for ep in profile["api_endpoints"][:50]
        )

    conn = Connection(
        id=uuid.uuid4(),
        project_id=project.id,
        name=f"{project.name} (Auto)",
        connection_type="rest_api",
        config=config,
        is_default=True,
        created_by=user_id,
    )
    db.add(conn)
    db.flush()
    return conn.id


# ---------------------------------------------------------------------------
# POST /{project_id}/test-plans/{plan_id}/execute
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/test-plans/{plan_id}/execute",
    response_model=ExecutionRunResponse,
    summary="Trigger execution of a test plan",
)
def execute_test_plan(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: ExecuteTestPlanRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger execution of a test plan. Returns immediately; execution runs
    in background. Poll GET /execution-runs/{run_id} for progress.
    """
    project = _get_project_or_404(project_id, db)

    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id,
    ).first()
    if not plan:
        raise HTTPException(404, "Test plan not found")

    # -- Resolve connection --
    connection_id = body.connection_id
    if not connection_id:
        # Try to find default connection for project
        default_conn = db.query(Connection).filter(
            Connection.project_id == project_id,
            Connection.is_default == True,  # noqa: E712
        ).first()
        if default_conn:
            connection_id = default_conn.id
        else:
            # Auto-create connection from app_profile
            connection_id = _auto_create_connection(db, project, current_user.id)

    # -- Collect test case IDs --
    if body.test_case_ids:
        tc_ids = body.test_case_ids
    else:
        tcs = db.query(TestCase.id).filter(TestCase.test_plan_id == plan_id).all()
        tc_ids = [tc.id for tc in tcs]

    if not tc_ids:
        raise HTTPException(400, "No test cases found in this plan")

    # -- Create ExecutionRun --
    run = ExecutionRun(
        id=uuid.uuid4(),
        project_id=project_id,
        test_plan_id=plan_id,
        connection_id=connection_id,
        test_case_ids=[str(tid) for tid in tc_ids],
        status="pending",
        triggered_by=current_user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # -- Kick off background execution --
    try:
        from execution.engine import run_execution
        background_tasks.add_task(run_execution, run.id)
    except ImportError:
        logger.warning("execution.engine not available; run will stay pending")

    audit_log(
        db,
        user_id=current_user.id,
        action="execute_test_plan",
        entity_type="execution_run",
        entity_id=str(run.id),
        details={"test_plan_id": str(plan_id), "test_case_count": len(tc_ids)},
        ip_address=get_client_ip(request),
    )

    return run


# ---------------------------------------------------------------------------
# GET /{project_id}/execution-runs
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/execution-runs",
    response_model=List[ExecutionRunResponse],
    summary="List execution runs for a project",
)
def list_execution_runs(
    project_id: uuid.UUID,
    test_plan_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List execution runs for a project, optionally filtered by test plan or status."""
    _get_project_or_404(project_id, db)

    q = db.query(ExecutionRun).filter(ExecutionRun.project_id == project_id)
    if test_plan_id:
        q = q.filter(ExecutionRun.test_plan_id == test_plan_id)
    if status:
        q = q.filter(ExecutionRun.status == status)

    return q.order_by(ExecutionRun.created_at.desc()).limit(50).all()


# ---------------------------------------------------------------------------
# GET /{project_id}/execution-runs/{run_id}
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/execution-runs/{run_id}",
    response_model=ExecutionRunResponse,
    summary="Get execution run detail with progress",
)
def get_execution_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get execution run detail with real-time progress."""
    run = db.query(ExecutionRun).filter(
        ExecutionRun.id == run_id,
        ExecutionRun.project_id == project_id,
    ).first()
    if not run:
        raise HTTPException(404, "Execution run not found")
    return run


# ---------------------------------------------------------------------------
# POST /{project_id}/execution-runs/{run_id}/cancel
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/execution-runs/{run_id}/cancel",
    response_model=MessageResponse,
    summary="Cancel a running execution",
)
def cancel_execution_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a running execution."""
    run = db.query(ExecutionRun).filter(
        ExecutionRun.id == run_id,
        ExecutionRun.project_id == project_id,
    ).first()
    if not run:
        raise HTTPException(404, "Execution run not found")
    if run.status not in ("pending", "running"):
        raise HTTPException(400, f"Cannot cancel run in '{run.status}' state")

    run.status = "cancelled"
    db.commit()

    audit_log(
        db,
        user_id=current_user.id,
        action="cancel_execution",
        entity_type="execution_run",
        entity_id=str(run.id),
        ip_address=None,
    )

    return MessageResponse(message="Execution cancelled")


# ---------------------------------------------------------------------------
# DELETE /{project_id}/execution-runs/{run_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{project_id}/execution-runs/{run_id}",
    response_model=MessageResponse,
    summary="Delete an execution run",
)
def delete_execution_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an execution run and its results. Only admin users can delete runs."""
    if current_user.role != "admin":
        raise HTTPException(403, "Only admins can delete execution runs")

    run = db.query(ExecutionRun).filter(
        ExecutionRun.id == run_id,
        ExecutionRun.project_id == project_id,
    ).first()
    if not run:
        raise HTTPException(404, "Execution run not found")

    if run.status == "running":
        raise HTTPException(400, "Cannot delete a running execution. Cancel it first.")

    db.delete(run)
    db.commit()

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_execution_run",
        entity_type="execution_run",
        entity_id=str(run_id),
        ip_address=get_client_ip(request),
    )

    return MessageResponse(message=f"Execution run {run_id} deleted")


# ---------------------------------------------------------------------------
# GET /{project_id}/connections
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/connections",
    response_model=List[ConnectionResponse],
    summary="List connections for a project",
)
def list_connections(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all connections for a project."""
    _get_project_or_404(project_id, db)
    return (
        db.query(Connection)
        .filter(Connection.project_id == project_id)
        .order_by(Connection.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# POST /{project_id}/connections
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/connections",
    response_model=ConnectionResponse,
    summary="Create a connection",
    status_code=201,
)
def create_connection(
    project_id: uuid.UUID,
    body: ConnectionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new connection for a project."""
    _get_project_or_404(project_id, db)

    # Check for name uniqueness
    existing = db.query(Connection).filter(
        Connection.project_id == project_id,
        Connection.name == body.name,
    ).first()
    if existing:
        raise HTTPException(409, f"Connection '{body.name}' already exists")

    # If marking as default, unset existing defaults
    if body.is_default:
        db.query(Connection).filter(
            Connection.project_id == project_id,
            Connection.is_default == True,  # noqa: E712
        ).update({"is_default": False})

    conn = Connection(
        id=uuid.uuid4(),
        project_id=project_id,
        name=body.name,
        connection_type=body.connection_type,
        config=body.config,
        is_default=body.is_default,
        created_by=current_user.id,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)

    audit_log(
        db,
        user_id=current_user.id,
        action="create_connection",
        entity_type="connection",
        entity_id=str(conn.id),
        details={"name": body.name, "type": body.connection_type},
        ip_address=get_client_ip(request),
    )

    return conn
