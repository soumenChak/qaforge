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

    # ── Pre-flight: verify target URL is reachable before spending LLM tokens ──
    target_url = (
        app_profile.get("api_base_url")
        or app_profile.get("app_url")
        or ""
    )
    if target_url:
        import httpx as _httpx
        try:
            _preflight = _httpx.get(
                target_url,
                timeout=10,
                verify=False,
                follow_redirects=True,
            )
            logger.info(
                "Pre-flight OK: %s → %d", target_url, _preflight.status_code,
            )
        except (_httpx.ConnectError, _httpx.ConnectTimeout) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Target URL unreachable: {target_url} ({exc.__class__.__name__})",
            )
        except Exception as exc:
            # Any HTTP status (401, 403, 500) means the URL is reachable
            logger.warning("Pre-flight warning for %s: %s", target_url, exc)

    # ── Resolve connection config overrides ──
    conn_config: dict = {}
    if connection_id:
        conn = db.query(Connection).filter(Connection.id == connection_id).first()
        if conn is None:
            raise HTTPException(status_code=400, detail="Connection not found")
        conn_config = conn.config or {}
        # Connection's base_url / auth_token override app_profile values
        if conn_config.get("base_url"):
            target_url = conn_config["base_url"]
        logger.info("Using connection override: %s (driver=%s)", conn.name, conn.driver)

    # ── Pre-authenticate: get a working token before generation ──
    pre_auth_token: str | None = None
    auth_info = app_profile.get("auth", {})
    if isinstance(auth_info, dict) and auth_info.get("login_endpoint"):
        login_ep = auth_info["login_endpoint"]
        test_creds = auth_info.get("test_credentials", {})
        req_body_template = auth_info.get("request_body", {})

        # Build login URL
        login_url = target_url.rstrip("/") + "/" + login_ep.lstrip("/") if target_url else ""
        if login_url and isinstance(test_creds, dict) and test_creds.get("email"):
            import httpx as _httpx

            # Build request body: merge template with actual credentials
            login_body = {}
            if isinstance(req_body_template, dict):
                login_body = dict(req_body_template)
            # Common patterns for credential fields
            login_body.update({
                k: v for k, v in {
                    "email": test_creds.get("email"),
                    "password": test_creds.get("password"),
                    "username": test_creds.get("email"),
                }.items() if v
            })

            try:
                login_resp = _httpx.post(
                    login_url,
                    json=login_body,
                    timeout=15,
                    verify=False,
                    follow_redirects=True,
                )
                if login_resp.status_code == 200:
                    data = login_resp.json()
                    # Try common token field names
                    token_field = auth_info.get("token_field", "access_token")
                    pre_auth_token = (
                        data.get(token_field)
                        or data.get("access_token")
                        or data.get("token")
                        or data.get("jwt")
                        or ""
                    )
                    if pre_auth_token:
                        logger.info("Pre-auth succeeded: got token from %s", login_url)
                    else:
                        logger.warning("Pre-auth 200 but no token found in keys: %s", list(data.keys()))
                else:
                    logger.warning(
                        "Pre-auth failed: %s → %d %s",
                        login_url, login_resp.status_code, login_resp.text[:200],
                    )
            except Exception as exc:
                logger.warning("Pre-auth request failed: %s — %s", login_url, exc)

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

    # ── Build QAFORGE_* env dict for subprocess ──
    qaforge_env: dict[str, str] = {
        "QAFORGE_BASE_URL": (conn_config.get("base_url") or app_profile.get("api_base_url") or ""),
        "QAFORGE_APP_URL": app_profile.get("app_url", ""),
        "QAFORGE_SSL_VERIFY": "false",
    }
    if pre_auth_token:
        qaforge_env["QAFORGE_AUTH_TOKEN"] = pre_auth_token
    if isinstance(auth_info, dict):
        creds = auth_info.get("test_credentials", {})
        if isinstance(creds, dict):
            qaforge_env["QAFORGE_AUTH_EMAIL"] = creds.get("email", "")
            qaforge_env["QAFORGE_AUTH_PASSWORD"] = creds.get("password", "")
        qaforge_env["QAFORGE_TOKEN_HEADER"] = auth_info.get("token_header", "Authorization")
        if auth_info.get("login_endpoint"):
            qaforge_env["QAFORGE_LOGIN_ENDPOINT"] = auth_info["login_endpoint"]

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
        qaforge_env=qaforge_env,
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
    qaforge_env: dict[str, str] | None = None,
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

            # --- Step 2a: Generate conftest.py with shared fixtures ---
            conftest_code = _build_conftest(execution_type)
            conftest_path = os.path.join(tmpdir, "conftest.py")
            with open(conftest_path, "w") as f:
                f.write(conftest_code)

            # Build subprocess env: inherit system env + QAFORGE_* vars
            run_env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            if qaforge_env:
                for k, v in qaforge_env.items():
                    if v:  # Only set non-empty values
                        run_env[k] = v

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
                    env=run_env,
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


def _build_conftest(execution_type: str = "api") -> str:
    """Generate a conftest.py with shared pytest fixtures for test execution.

    Fixtures read from QAFORGE_* environment variables so generated tests
    never need to hardcode URLs or credentials.
    """
    return '''\
"""
QAForge — Shared pytest fixtures (auto-generated conftest.py).

All configuration comes from QAFORGE_* environment variables injected
by the execution engine. Tests should use these fixtures rather than
hardcoding URLs, tokens, or credentials.
"""
import os
import httpx
import pytest


# ── Configuration from environment ─────────────────────────────────────────
BASE_URL = os.environ.get("QAFORGE_BASE_URL", "")
APP_URL = os.environ.get("QAFORGE_APP_URL", "")
AUTH_TOKEN = os.environ.get("QAFORGE_AUTH_TOKEN", "")
AUTH_EMAIL = os.environ.get("QAFORGE_AUTH_EMAIL", "")
AUTH_PASSWORD = os.environ.get("QAFORGE_AUTH_PASSWORD", "")
TOKEN_HEADER = os.environ.get("QAFORGE_TOKEN_HEADER", "Authorization")
LOGIN_ENDPOINT = os.environ.get("QAFORGE_LOGIN_ENDPOINT", "")
SSL_VERIFY = os.environ.get("QAFORGE_SSL_VERIFY", "false").lower() == "true"


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url():
    """Target API base URL from environment."""
    return BASE_URL


@pytest.fixture(scope="session")
def app_url():
    """Target application frontend URL from environment."""
    return APP_URL or BASE_URL


@pytest.fixture(scope="session")
def auth_token():
    """Acquire auth token: prefer pre-authenticated token, fallback to login.

    The execution engine pre-authenticates and passes QAFORGE_AUTH_TOKEN.
    If that's missing, attempt login with QAFORGE_AUTH_EMAIL/PASSWORD.
    Returns empty string if no auth is available (login tests don't need it).
    """
    if AUTH_TOKEN:
        return AUTH_TOKEN

    if not LOGIN_ENDPOINT or not AUTH_EMAIL:
        return ""  # No auth available — login tests still work

    login_url = BASE_URL.rstrip("/") + "/" + LOGIN_ENDPOINT.lstrip("/")
    try:
        resp = httpx.post(
            login_url,
            json={"email": AUTH_EMAIL, "password": AUTH_PASSWORD},
            timeout=15,
            verify=SSL_VERIFY,
        )
        if resp.status_code == 200:
            data = resp.json()
            return (
                data.get("access_token")
                or data.get("token")
                or data.get("jwt")
                or ""
            )
    except Exception:
        pass
    return ""


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    """Standard authorization headers. Empty dict if no token available."""
    if auth_token:
        return {TOKEN_HEADER: f"Bearer {auth_token}"}
    return {}


@pytest.fixture(scope="session")
def client():
    """Pre-configured httpx client with SSL disabled, reasonable timeout.
    Does NOT include auth headers — use auth_headers fixture separately.
    base_url has trailing slash so relative paths work correctly.
    """
    url = BASE_URL.rstrip("/") + "/" if BASE_URL else ""
    with httpx.Client(
        base_url=url,
        verify=SSL_VERIFY,
        timeout=30.0,
    ) as c:
        yield c


@pytest.fixture(scope="session")
def authenticated_client(auth_headers):
    """Pre-configured httpx client WITH auth headers, SSL disabled."""
    url = BASE_URL.rstrip("/") + "/" if BASE_URL else ""
    with httpx.Client(
        base_url=url,
        headers=auth_headers,
        verify=SSL_VERIFY,
        timeout=30.0,
    ) as c:
        yield c
'''


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
