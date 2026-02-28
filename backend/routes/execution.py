"""
QAForge -- Execution run management routes.

Prefix: /api/execution

Endpoints:
    POST   /                              — create & queue execution run
    POST   /generate-and-execute          — generate executable tests + run them
    GET    /                              — list runs (filter by project_id, status)
    GET    /{run_id}                      — full run detail with results
    GET    /{run_id}/status               — lightweight poll (status + progress)
    POST   /{run_id}/cancel               — cancel a running execution
    DELETE /{run_id}                      — delete a completed/failed/cancelled run
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

    # Use query-level delete to avoid ORM cascade side-effects
    db.query(ExecutionRun).filter(ExecutionRun.id == run_id).delete()
    db.flush()

    return MessageResponse(message="Execution run deleted")


# ---------------------------------------------------------------------------
# POST /generate-and-execute  (NEW — Executable Mode)
# ---------------------------------------------------------------------------
@router.post(
    "/generate-and-execute",
    summary="Generate executable Python tests and run them",
    status_code=status.HTTP_201_CREATED,
)
def generate_and_execute(
    body: dict,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    New Executable Mode: generates a Python test script (httpx or Playwright)
    from the app profile + description, then runs it via subprocess.

    Body:
    {
        "project_id": "uuid",
        "description": "What to test",
        "execution_type": "api" | "ui",
        "count": 10,
        "connection_id": "uuid" (optional),
        "additional_context": "" (optional)
    }

    Returns immediately with a run_id. Poll /execution/{run_id}/status.
    """
    from db_models import Project

    project_id = body.get("project_id")
    if not project_id:
        raise HTTPException(400, "project_id is required")

    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(404, "Project not found")

    description = body.get("description", "")
    execution_type = body.get("execution_type", "api")
    count = body.get("count", 10)
    additional_context = body.get("additional_context", "")
    connection_id = body.get("connection_id")

    app_profile = project.app_profile or {}

    # Gather requirements from project
    from db_models import Requirement
    reqs = (
        db.query(Requirement)
        .filter(
            Requirement.project_id == project_id,
            Requirement.status != "deferred",
        )
        .order_by(Requirement.created_at.asc())
        .limit(30)
        .all()
    )
    req_texts = [
        f"[{r.priority.upper()}] {r.req_id}: {r.title} — {r.description or ''}"
        for r in reqs
    ] if reqs else None

    # Create an execution run record to track progress
    run = ExecutionRun(
        project_id=project_id,
        connection_id=connection_id,
        test_case_ids=[],
        status="queued",
        executed_by=current_user.id,
        results={
            "mode": "executable",
            "execution_type": execution_type,
            "description": description[:500],
        },
    )
    db.add(run)
    db.flush()
    db.commit()

    logger.info(
        "Executable run created: %s (type=%s, count=%d) by %s",
        run.id, execution_type, count, current_user.email,
    )

    # Run generation + execution in background
    background_tasks.add_task(
        _run_executable_generation,
        run_id=run.id,
        app_profile=app_profile,
        description=description,
        execution_type=execution_type,
        count=count,
        requirements=req_texts,
        additional_context=additional_context,
        connection_id=connection_id,
    )

    return {
        "id": str(run.id),
        "status": "queued",
        "message": f"Generating {execution_type} tests and executing...",
    }


def _run_executable_generation(
    run_id: uuid.UUID,
    app_profile: dict,
    description: str,
    execution_type: str,
    count: int,
    requirements: list | None,
    additional_context: str,
    connection_id: uuid.UUID | None,
):
    """Background task: generate executable tests → run via subprocess."""
    import subprocess
    import tempfile
    import os
    from datetime import datetime, timezone
    from sqlalchemy.orm.attributes import flag_modified

    from db_session import SessionLocal

    db = SessionLocal()
    try:
        run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
        if not run:
            logger.error("Executable run %s not found in DB", run_id)
            return

        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        flag_modified(run, "results")
        db.commit()

        # --- Step 1: Generate executable test script ---
        from generation.executable_generator import ExecutableGenerator

        gen = ExecutableGenerator()

        if execution_type == "ui":
            result = gen.generate_ui_tests(
                app_profile=app_profile,
                description=description,
                requirements=requirements,
                count=count,
                additional_context=additional_context,
            )
        else:
            result = gen.generate_api_tests(
                app_profile=app_profile,
                description=description,
                requirements=requirements,
                count=count,
                additional_context=additional_context,
            )

        if not result.scripts or not result.scripts[0].code:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            run.results = {
                **(run.results or {}),
                "error": "Failed to generate executable test script",
                "summary": {"total": 0, "passed": 0, "failed": 0},
                "generation": {
                    "tokens_in": result.tokens_in,
                    "tokens_out": result.tokens_out,
                    "model": result.model,
                    "provider": result.provider,
                },
            }
            flag_modified(run, "results")
            db.commit()
            return

        script = result.scripts[0]
        logger.info(
            "Executable script generated: %s (%d functions, %d chars)",
            script.filename, len(script.test_functions), len(script.code),
        )

        # Store generated code in results for debugging/viewing
        run.results = {
            **(run.results or {}),
            "generated_code": script.code,
            "test_functions": script.test_functions,
            "generation": {
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "model": result.model,
                "provider": result.provider,
            },
        }
        flag_modified(run, "results")
        db.commit()

        # --- Step 2: Execute the script via subprocess ---
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, script.filename)
            with open(script_path, "w") as f:
                f.write(script.code)

            # Install dependencies hint (httpx/playwright should already be in venv)
            cmd = [
                "python", "-m", "pytest", script_path,
                "--tb=short", "-q", "--no-header",
                f"--junit-xml={os.path.join(tmpdir, 'results.xml')}",
            ]

            logger.info("Running: %s", " ".join(cmd))

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,  # 2 minutes max
                    cwd=tmpdir,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )

                stdout = proc.stdout or ""
                stderr = proc.stderr or ""
                exit_code = proc.returncode

                # Parse pytest output for pass/fail counts
                test_results = _parse_pytest_output(stdout, stderr, exit_code)

                run.results = {
                    **(run.results or {}),
                    "stdout": stdout[-5000:],   # Last 5K chars
                    "stderr": stderr[-2000:],   # Last 2K chars
                    "exit_code": exit_code,
                    "summary": test_results["summary"],
                    "test_results": test_results.get("details", []),
                }
                run.status = "completed"

            except subprocess.TimeoutExpired:
                run.results = {
                    **(run.results or {}),
                    "error": "Test execution timed out after 120 seconds",
                    "summary": {"total": 0, "passed": 0, "failed": 0, "error": 1},
                }
                run.status = "failed"

            except Exception as exc:
                run.results = {
                    **(run.results or {}),
                    "error": f"Execution error: {str(exc)}",
                    "summary": {"total": 0, "passed": 0, "failed": 0, "error": 1},
                }
                run.status = "failed"

        run.completed_at = datetime.now(timezone.utc)
        flag_modified(run, "results")
        db.commit()

        elapsed = (run.completed_at - run.started_at).total_seconds()
        summary = run.results.get("summary", {})
        logger.info(
            "Executable run %s completed: %s — %d passed, %d failed in %.1fs",
            run_id, run.status,
            summary.get("passed", 0), summary.get("failed", 0), elapsed,
        )

    except Exception:
        logger.error("Executable run %s crashed", run_id, exc_info=True)
        try:
            run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
            if run:
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                run.results = {**(run.results or {}), "error": "Internal crash"}
                flag_modified(run, "results")
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _parse_pytest_output(stdout: str, stderr: str, exit_code: int) -> dict:
    """Parse pytest console output into structured results."""
    import re

    details: list[dict] = []
    passed = 0
    failed = 0
    errored = 0

    # Parse individual test results from pytest -q output
    # Format: "test_file.py::test_name PASSED" or "FAILED"
    for line in stdout.split("\n"):
        line = line.strip()
        if "PASSED" in line:
            name = line.split(" ")[0].split("::")[-1] if "::" in line else line.split(" ")[0]
            details.append({"name": name, "status": "passed"})
            passed += 1
        elif "FAILED" in line:
            name = line.split(" ")[0].split("::")[-1] if "::" in line else line.split(" ")[0]
            details.append({"name": name, "status": "failed"})
            failed += 1
        elif "ERROR" in line:
            name = line.split(" ")[0].split("::")[-1] if "::" in line else line.split(" ")[0]
            details.append({"name": name, "status": "error"})
            errored += 1

    # Also try the summary line: "5 passed, 2 failed in 3.45s"
    summary_match = re.search(
        r"(\d+)\s+passed(?:.*?(\d+)\s+failed)?(?:.*?(\d+)\s+error)?",
        stdout + stderr,
    )
    if summary_match:
        passed = max(passed, int(summary_match.group(1)))
        if summary_match.group(2):
            failed = max(failed, int(summary_match.group(2)))
        if summary_match.group(3):
            errored = max(errored, int(summary_match.group(3)))

    total = passed + failed + errored
    pass_rate = round((passed / total) * 100, 1) if total > 0 else 0.0

    return {
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errored": errored,
            "pass_rate": pass_rate,
        },
        "details": details,
    }
