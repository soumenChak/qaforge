"""
QAForge -- Project management routes.

Prefix: /api/projects

Endpoints:
    POST   /             — create project
    GET    /             — list projects with stats (filter by domain, status)
    GET    /{id}         — project detail with counts
    PUT    /{id}         — update project
    POST   /{id}/archive — archive project
    DELETE /{id}         — delete project (cascades test cases & requirements)
"""

import hashlib
import ipaddress
import json
import logging
import secrets
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from db_models import ExecutionResult, FeedbackEntry, GenerationRun, Project, Requirement, TestCase, TestPlan, User
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    sanitize_string,
)
from models import (
    AgentKeyResponse,
    CoverageResult,
    MessageResponse,
    OpenAPIDiscoverRequest,
    ProfileValidationResult,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    UIDiscoverRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=ProjectResponse,
    summary="Create a new project",
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    body: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new QA project scoped to a domain and sub-domain."""
    project = Project(
        name=sanitize_string(body.name) or body.name,
        domain=body.domain,
        sub_domain=sanitize_string(body.sub_domain) or body.sub_domain,
        description=sanitize_string(body.description) if body.description else None,
        template_id=body.template_id,
        app_profile=body.app_profile,
        created_by=current_user.id,
    )
    db.add(project)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="create_project",
        entity_type="project",
        entity_id=str(project.id),
        details={"name": project.name, "domain": project.domain},
        ip_address=get_client_ip(request),
    )

    logger.info("Project created: %s by %s", project.name, current_user.email)

    return ProjectResponse.model_validate(project)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=list[ProjectListResponse],
    summary="List projects with stats",
)
def list_projects(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    project_status: Optional[str] = Query(
        None, alias="status", description="Filter by status (active/completed/archived)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all projects with aggregated stats.

    Supports filtering by domain and status.
    """
    query = db.query(Project)

    if domain:
        query = query.filter(Project.domain == domain)
    if project_status:
        query = query.filter(Project.status == project_status)

    projects = query.order_by(Project.created_at.desc()).all()

    results = []
    for p in projects:
        # Compute aggregate stats
        tc_count = db.query(func.count(TestCase.id)).filter(
            TestCase.project_id == p.id
        ).scalar() or 0

        passed_count = db.query(func.count(TestCase.id)).filter(
            TestCase.project_id == p.id,
            TestCase.status == "passed",
        ).scalar() or 0

        failed_count = db.query(func.count(TestCase.id)).filter(
            TestCase.project_id == p.id,
            TestCase.status == "failed",
        ).scalar() or 0

        req_count = db.query(func.count(Requirement.id)).filter(
            Requirement.project_id == p.id
        ).scalar() or 0

        item = ProjectListResponse.model_validate(p)
        item.test_case_count = tc_count
        item.passed_count = passed_count
        item.failed_count = failed_count
        item.requirement_count = req_count
        results.append(item)

    return results


# ---------------------------------------------------------------------------
# GET /{id}
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}",
    response_model=ProjectListResponse,
    summary="Get project detail with counts",
)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single project with its aggregated counts."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    tc_count = db.query(func.count(TestCase.id)).filter(
        TestCase.project_id == project.id
    ).scalar() or 0

    passed_count = db.query(func.count(TestCase.id)).filter(
        TestCase.project_id == project.id,
        TestCase.status == "passed",
    ).scalar() or 0

    failed_count = db.query(func.count(TestCase.id)).filter(
        TestCase.project_id == project.id,
        TestCase.status == "failed",
    ).scalar() or 0

    req_count = db.query(func.count(Requirement.id)).filter(
        Requirement.project_id == project.id
    ).scalar() or 0

    item = ProjectListResponse.model_validate(project)
    item.test_case_count = tc_count
    item.passed_count = passed_count
    item.failed_count = failed_count
    item.requirement_count = req_count

    return item


# ---------------------------------------------------------------------------
# PUT /{id}
# ---------------------------------------------------------------------------
@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
)
def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update project fields (name, description, status, template)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if body.name is not None:
        project.name = sanitize_string(body.name) or body.name
    if body.description is not None:
        project.description = sanitize_string(body.description)
    if body.status is not None:
        project.status = body.status
    if body.template_id is not None:
        project.template_id = body.template_id
    if body.app_profile is not None:
        project.app_profile = body.app_profile
        flag_modified(project, "app_profile")

    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="update_project",
        entity_type="project",
        entity_id=str(project.id),
        details=body.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )

    logger.info("Project updated: %s by %s", project.name, current_user.email)

    return ProjectResponse.model_validate(project)


# ---------------------------------------------------------------------------
# PUT /{id}/app-profile
# ---------------------------------------------------------------------------
@router.put(
    "/{project_id}/app-profile",
    response_model=ProjectResponse,
    summary="Update project application profile",
)
def update_app_profile(
    project_id: uuid.UUID,
    body: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the application profile (URLs, auth config, endpoints, UI pages) for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Detect if api_base_url was just set/changed — trigger auto-discovery
    old_profile = project.app_profile or {}
    old_base_url = old_profile.get("api_base_url", "")
    new_base_url = body.get("api_base_url", "")

    project.app_profile = body
    flag_modified(project, "app_profile")
    db.flush()

    # Auto-discover OpenAPI spec if base URL was newly set or changed
    auto_discovered = False
    if new_base_url and new_base_url != old_base_url:
        auto_discovered = _try_auto_discover_openapi(project, db)

    audit_log(
        db,
        user_id=current_user.id,
        action="update_app_profile",
        entity_type="project",
        entity_id=str(project.id),
        details={"keys": list(body.keys()), "auto_discovered": auto_discovered},
        ip_address=get_client_ip(request),
    )

    logger.info(
        "App profile updated for project %s by %s (auto_discovered=%s)",
        project.name, current_user.email, auto_discovered,
    )

    return ProjectResponse.model_validate(project)


def _try_auto_discover_openapi(project, db) -> bool:
    """
    Attempt to auto-discover OpenAPI spec when api_base_url is set.
    Tries common spec paths. Non-blocking — returns False on any failure.
    """
    import httpx as _httpx

    ap = project.app_profile or {}
    base_url = ap.get("api_base_url", "").rstrip("/")
    if not base_url:
        return False

    # Common OpenAPI spec paths to try
    spec_paths = [
        "/openapi.json",
        "/api/openapi.json",
        "/docs/openapi.json",
        "/swagger.json",
        "/api/swagger.json",
        "/v1/openapi.json",
    ]

    for path in spec_paths:
        url = base_url + path
        try:
            resp = _httpx.get(url, timeout=10, follow_redirects=True, verify=False)
            if resp.status_code == 200:
                spec = resp.json()
                if isinstance(spec, dict) and ("paths" in spec or "openapi" in spec or "swagger" in spec):
                    discovered = _parse_openapi_spec(spec)
                    if discovered.get("api_endpoints"):
                        # Merge discovered endpoints into existing profile
                        existing_endpoints = ap.get("api_endpoints", [])
                        existing_paths = {
                            (ep.get("method"), ep.get("path"))
                            for ep in existing_endpoints
                            if isinstance(ep, dict)
                        }
                        new_endpoints = [
                            ep for ep in discovered["api_endpoints"]
                            if (ep.get("method"), ep.get("path")) not in existing_paths
                        ]
                        ap["api_endpoints"] = existing_endpoints + new_endpoints

                        # Merge auth if discovered
                        if discovered.get("auth") and not ap.get("auth", {}).get("login_endpoint"):
                            ap.setdefault("auth", {}).update(discovered["auth"])

                        project.app_profile = ap
                        flag_modified(project, "app_profile")
                        db.flush()

                        logger.info(
                            "Auto-discovered %d API endpoints from %s for project %s",
                            len(new_endpoints), url, project.name,
                        )
                        return True
        except Exception as exc:
            logger.debug("Auto-discovery failed for %s: %s", url, exc)
            continue

    logger.info("No OpenAPI spec found for %s (tried %d paths)", base_url, len(spec_paths))
    return False


# ---------------------------------------------------------------------------
# POST /{id}/archive
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/archive",
    response_model=MessageResponse,
    summary="Archive a project",
)
def archive_project(
    project_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a project's status to 'archived'."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project is already archived",
        )

    project.status = "archived"
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="archive_project",
        entity_type="project",
        entity_id=str(project.id),
        details={"name": project.name},
        ip_address=get_client_ip(request),
    )

    logger.info("Project archived: %s by %s", project.name, current_user.email)

    return MessageResponse(message=f"Project '{project.name}' has been archived")


# ---------------------------------------------------------------------------
# DELETE /{id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{project_id}",
    response_model=MessageResponse,
    summary="Delete a project and all its data",
)
def delete_project(
    project_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete a project and cascade-delete its requirements and test cases."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project_name = project.name

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_project",
        entity_type="project",
        entity_id=str(project_id),
        details={"name": project_name},
        ip_address=get_client_ip(request),
    )

    # Cascade-delete all related entities using query-level deletes
    # (avoids ORM cascade side-effects that cause IntegrityError)
    # Order: children first, then parent

    # 1. FeedbackEntries (FK to test_cases)
    tc_ids = db.query(TestCase.id).filter(TestCase.project_id == project_id)
    db.query(FeedbackEntry).filter(
        FeedbackEntry.test_case_id.in_(tc_ids)
    ).delete(synchronize_session=False)

    # 2. Execution results (via test cases)
    tc_id_list = [r[0] for r in db.query(TestCase.id).filter(TestCase.project_id == project_id).all()]
    if tc_id_list:
        db.query(ExecutionResult).filter(ExecutionResult.test_case_id.in_(tc_id_list)).delete(
            synchronize_session=False
        )

    # 2b. Test plans
    db.query(TestPlan).filter(TestPlan.project_id == project_id).delete(
        synchronize_session=False
    )

    # 3. Generation runs
    db.query(GenerationRun).filter(GenerationRun.project_id == project_id).delete(
        synchronize_session=False
    )

    # 4. Test cases
    db.query(TestCase).filter(TestCase.project_id == project_id).delete(
        synchronize_session=False
    )

    # 5. Requirements
    db.query(Requirement).filter(Requirement.project_id == project_id).delete(
        synchronize_session=False
    )

    # 6. Project itself
    db.query(Project).filter(Project.id == project_id).delete(
        synchronize_session=False
    )

    db.flush()

    logger.info("Project deleted: %s by %s", project_name, current_user.email)

    return MessageResponse(message=f"Project '{project_name}' has been deleted")


# ---------------------------------------------------------------------------
# GET /{id}/coverage  (Feature 2: Test Coverage Score)
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/coverage",
    response_model=CoverageResult,
    summary="Get test coverage score for a project",
)
def get_coverage(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calculate requirement coverage: how many requirements have at least one test case.
    Returns a priority-weighted score, grade, and detailed breakdown.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load all requirements
    requirements = (
        db.query(Requirement)
        .filter(Requirement.project_id == project_id)
        .all()
    )

    if not requirements:
        return CoverageResult(
            score=100.0,
            grade="A",
            total_requirements=0,
            covered_requirements=0,
            uncovered_requirements=0,
            coverage_by_priority={},
            uncovered_details=[],
            orphan_test_count=0,
            scoring_explanation="No requirements defined for this project. Score defaults to 100%.",
        )

    # Get requirement IDs that have at least one test case
    covered_req_ids = set()
    covered_rows = (
        db.query(TestCase.requirement_id)
        .filter(
            TestCase.project_id == project_id,
            TestCase.requirement_id.isnot(None),
        )
        .distinct()
        .all()
    )
    for row in covered_rows:
        covered_req_ids.add(row[0])

    # Count orphan test cases (no requirement_id)
    orphan_count = (
        db.query(func.count(TestCase.id))
        .filter(
            TestCase.project_id == project_id,
            TestCase.requirement_id.is_(None),
        )
        .scalar()
    ) or 0

    # Priority weights
    PRIORITY_WEIGHTS = {"high": 3, "medium": 2, "low": 1}

    total_reqs = len(requirements)
    covered_count = 0
    uncovered_details = []
    coverage_by_priority: Dict[str, Dict[str, Any]] = {}

    weighted_total = 0
    weighted_covered = 0

    for req in requirements:
        priority = (req.priority or "medium").lower()
        weight = PRIORITY_WEIGHTS.get(priority, 1)
        weighted_total += weight

        is_covered = req.id in covered_req_ids
        if is_covered:
            covered_count += 1
            weighted_covered += weight
        else:
            uncovered_details.append({
                "req_id": req.req_id,
                "title": req.title,
                "priority": req.priority,
                "id": str(req.id),
            })

        if priority not in coverage_by_priority:
            coverage_by_priority[priority] = {"total": 0, "covered": 0, "uncovered_ids": []}
        coverage_by_priority[priority]["total"] += 1
        if is_covered:
            coverage_by_priority[priority]["covered"] += 1
        else:
            coverage_by_priority[priority]["uncovered_ids"].append(req.req_id)

    # Calculate score
    score = round((weighted_covered / weighted_total) * 100, 1) if weighted_total > 0 else 0.0

    # Grade
    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    # Build explanation
    explanation_parts = [
        f"Coverage score: {score}% (grade {grade})",
        f"  {covered_count}/{total_reqs} requirements have at least one test case",
        f"  Scoring weights: high=3x, medium=2x, low=1x",
        f"  Weighted coverage: {weighted_covered}/{weighted_total}",
    ]
    if orphan_count > 0:
        explanation_parts.append(
            f"  Note: {orphan_count} test case(s) are not linked to any requirement"
        )

    uncovered_high = coverage_by_priority.get("high", {}).get("uncovered_ids", [])
    if uncovered_high:
        explanation_parts.append(
            f"  ⚠ {len(uncovered_high)} HIGH priority requirement(s) uncovered: {', '.join(uncovered_high[:5])}"
        )

    return CoverageResult(
        score=score,
        grade=grade,
        total_requirements=total_reqs,
        covered_requirements=covered_count,
        uncovered_requirements=total_reqs - covered_count,
        coverage_by_priority=coverage_by_priority,
        uncovered_details=uncovered_details,
        orphan_test_count=orphan_count,
        scoring_explanation="\n".join(explanation_parts),
    )


# ---------------------------------------------------------------------------
# POST /{id}/app-profile/validate  (Feature 3: Profile Validation)
# ---------------------------------------------------------------------------
def _is_safe_url(url: str) -> bool:
    """Check that a URL is not targeting localhost or private IPs (SSRF prevention)."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        try:
            ip = ipaddress.ip_address(hostname)
            return not ip.is_private and not ip.is_loopback
        except ValueError:
            # hostname is not an IP — likely a domain name, generally OK
            return True
    except Exception:
        return False


@router.post(
    "/{project_id}/app-profile/validate",
    response_model=ProfileValidationResult,
    summary="Validate app profile against live application",
)
async def validate_app_profile(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate the app_profile by making real HTTP calls:
    1. Base URL reachability
    2. Auth credentials verification
    3. Sample GET endpoint check
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    profile = project.app_profile
    if not profile or not isinstance(profile, dict):
        raise HTTPException(status_code=400, detail="No app_profile configured for this project")

    checks: List[Dict[str, Any]] = []

    # -- Check 1: Base URL reachability --
    base_url = profile.get("api_base_url") or profile.get("app_url") or ""
    if base_url:
        if not _is_safe_url(base_url):
            checks.append({
                "name": "Base URL Reachability",
                "status": "fail",
                "message": f"URL blocked for security (private/localhost): {base_url}",
            })
        else:
            try:
                async with httpx.AsyncClient(verify=False, timeout=10) as client:
                    resp = await client.get(base_url)
                    if resp.status_code < 500:
                        checks.append({
                            "name": "Base URL Reachability",
                            "status": "pass",
                            "message": f"Base URL reachable (HTTP {resp.status_code})",
                        })
                    else:
                        checks.append({
                            "name": "Base URL Reachability",
                            "status": "fail",
                            "message": f"Server error: HTTP {resp.status_code}",
                        })
            except Exception as exc:
                checks.append({
                    "name": "Base URL Reachability",
                    "status": "fail",
                    "message": f"Cannot reach: {type(exc).__name__}: {str(exc)[:100]}",
                })
    else:
        checks.append({
            "name": "Base URL Reachability",
            "status": "skip",
            "message": "No api_base_url or app_url configured",
        })

    # -- Check 2: Auth verification --
    auth = profile.get("auth", {})
    auth_token = None
    if auth.get("login_endpoint") and auth.get("test_credentials"):
        login_ep = auth["login_endpoint"]
        creds = auth["test_credentials"]

        # Parse method and path from "POST /api/auth/login"
        parts = login_ep.strip().split(None, 1)
        method = parts[0].upper() if len(parts) > 1 else "POST"
        path = parts[-1] if parts else "/api/auth/login"
        # Use app_url (root) if available, to avoid double /api prefix
        # If path starts with /api and base_url ends with /api, use app_url instead
        root_url = profile.get("app_url", "").rstrip("/") or base_url.rstrip("/")
        if root_url.endswith("/api") and path.startswith("/api"):
            root_url = root_url[:-4]  # Strip trailing /api
        login_url = f"{root_url}{path}" if root_url and not path.startswith("http") else path

        if not _is_safe_url(login_url):
            checks.append({
                "name": "Authentication",
                "status": "fail",
                "message": f"Login URL blocked for security: {login_url}",
            })
        else:
            try:
                async with httpx.AsyncClient(verify=False, timeout=10) as client:
                    resp = await client.request(method=method, url=login_url, json=creds)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if "access_token" in data or "token" in data:
                                auth_token = data.get("access_token") or data.get("token")
                                checks.append({
                                    "name": "Authentication",
                                    "status": "pass",
                                    "message": "Login successful, received access token",
                                })
                            else:
                                checks.append({
                                    "name": "Authentication",
                                    "status": "warn",
                                    "message": f"Login returned 200 but no access_token in response. Keys: {list(data.keys())[:5]}",
                                })
                        except Exception:
                            checks.append({
                                "name": "Authentication",
                                "status": "warn",
                                "message": "Login returned 200 but response is not valid JSON",
                            })
                    else:
                        checks.append({
                            "name": "Authentication",
                            "status": "fail",
                            "message": f"Login failed with HTTP {resp.status_code}",
                        })
            except Exception as exc:
                checks.append({
                    "name": "Authentication",
                    "status": "fail",
                    "message": f"Login request failed: {type(exc).__name__}: {str(exc)[:100]}",
                })
    else:
        checks.append({
            "name": "Authentication",
            "status": "skip",
            "message": "No login_endpoint or test_credentials configured",
        })

    # -- Check 3: Sample GET endpoint --
    api_endpoints = profile.get("api_endpoints", [])
    sample_ep = None
    for ep in api_endpoints:
        if isinstance(ep, dict) and ep.get("method", "").upper() == "GET":
            path = ep.get("path", "")
            # Skip parameterised endpoints like /candidates/{id}
            if "{" not in path:
                sample_ep = ep
                break

    if sample_ep and base_url:
        # Use root URL to avoid double /api prefix
        sample_root = profile.get("app_url", "").rstrip("/") or base_url.rstrip("/")
        ep_path = sample_ep['path']
        if sample_root.endswith("/api") and ep_path.startswith("/api"):
            sample_root = sample_root[:-4]
        sample_url = f"{sample_root}{ep_path}"
        if not _is_safe_url(sample_url):
            checks.append({
                "name": "Sample Endpoint",
                "status": "fail",
                "message": f"URL blocked for security: {sample_url}",
            })
        else:
            try:
                headers = {}
                if auth_token:
                    headers["Authorization"] = f"Bearer {auth_token}"

                async with httpx.AsyncClient(verify=False, timeout=15) as client:
                    resp = await client.get(sample_url, headers=headers)

                    if resp.status_code == 200:
                        # Check expected fields
                        expected_fields = sample_ep.get("response_fields", [])
                        try:
                            data = resp.json()
                            check_obj = data
                            if isinstance(data, list) and len(data) > 0:
                                check_obj = data[0]

                            if expected_fields and isinstance(check_obj, dict):
                                found = [f for f in expected_fields[:5] if f in check_obj]
                                missing = [f for f in expected_fields[:5] if f not in check_obj]
                                if missing:
                                    checks.append({
                                        "name": "Sample Endpoint",
                                        "status": "warn",
                                        "message": f"GET {sample_ep['path']} returned 200. Found fields: {found}. Missing: {missing}",
                                    })
                                else:
                                    checks.append({
                                        "name": "Sample Endpoint",
                                        "status": "pass",
                                        "message": f"GET {sample_ep['path']} returned 200 with expected fields: {found}",
                                    })
                            else:
                                checks.append({
                                    "name": "Sample Endpoint",
                                    "status": "pass",
                                    "message": f"GET {sample_ep['path']} returned 200",
                                })
                        except Exception:
                            checks.append({
                                "name": "Sample Endpoint",
                                "status": "pass",
                                "message": f"GET {sample_ep['path']} returned 200 (non-JSON response)",
                            })
                    else:
                        checks.append({
                            "name": "Sample Endpoint",
                            "status": "fail",
                            "message": f"GET {sample_ep['path']} returned HTTP {resp.status_code}",
                        })
            except Exception as exc:
                checks.append({
                    "name": "Sample Endpoint",
                    "status": "fail",
                    "message": f"Request failed: {type(exc).__name__}: {str(exc)[:100]}",
                })
    else:
        checks.append({
            "name": "Sample Endpoint",
            "status": "skip",
            "message": "No suitable GET endpoint found in app_profile or no base_url",
        })

    # Determine overall status
    statuses = [c["status"] for c in checks]
    if all(s in ("pass", "skip") for s in statuses):
        overall = "pass"
    elif any(s == "pass" for s in statuses):
        overall = "partial"
    else:
        overall = "fail"

    return ProfileValidationResult(overall_status=overall, checks=checks)


# ---------------------------------------------------------------------------
# POST /{id}/app-profile/discover  (Feature 4: OpenAPI Auto-Discovery)
# ---------------------------------------------------------------------------
def _resolve_ref(spec: dict, ref_string: str) -> dict:
    """Resolve a $ref pointer (e.g. '#/components/schemas/User') against the spec.

    Works for both OpenAPI 3.x (#/components/schemas/...) and
    Swagger 2.0 (#/definitions/...) references.
    """
    if not ref_string or not isinstance(ref_string, str):
        return {}
    parts = ref_string.split("/")
    obj = spec
    for part in parts[1:]:  # skip '#'
        if isinstance(obj, dict):
            obj = obj.get(part, {})
        else:
            return {}
    return obj if isinstance(obj, dict) else {}


def _resolve_schema(spec: dict, schema: dict) -> dict:
    """Resolve a schema object, following $ref if present."""
    if not isinstance(schema, dict):
        return {}
    if "$ref" in schema:
        return _resolve_ref(spec, schema["$ref"])
    return schema


def _format_field_with_type(name: str, prop: dict, required_set: set) -> str:
    """Format a field as 'name: type' or 'name: type (required)'."""
    field_type = prop.get("type", "object")
    fmt = prop.get("format")
    if fmt:
        field_type = f"{field_type}({fmt})"
    if prop.get("enum"):
        field_type = f"enum[{','.join(str(v) for v in prop['enum'][:5])}]"
    suffix = " (required)" if name in required_set else ""
    return f"{name}: {field_type}{suffix}"


def _extract_schema_fields_typed(spec: dict, schema: dict) -> List[str]:
    """Extract field names with types from a resolved schema's properties.

    Returns up to 20 entries like: ["name: string (required)", "age: integer"].
    """
    schema = _resolve_schema(spec, schema)
    props = schema.get("properties", {})
    if not props:
        return []
    required_set = set(schema.get("required", []))
    result = []
    for fname, fprop in list(props.items())[:20]:
        if not isinstance(fprop, dict):
            fprop = {}
        result.append(_format_field_with_type(fname, fprop, required_set))
    return result


def _extract_response_fields_typed(spec: dict, schema: dict) -> List[str]:
    """Extract response field names with types, handling array wrappers."""
    schema = _resolve_schema(spec, schema)
    # Unwrap array -> items
    if schema.get("type") == "array" and schema.get("items"):
        schema = _resolve_schema(spec, schema["items"])
    return _extract_schema_fields_typed(spec, schema)


def _extract_examples(spec: dict, schema: dict) -> Optional[Dict[str, Any]]:
    """Extract example data from a schema (example / examples / property-level examples).

    Returns a dict of example values, or None if no examples found.
    """
    schema = _resolve_schema(spec, schema)
    # Top-level example
    if schema.get("example"):
        return schema["example"] if isinstance(schema["example"], dict) else {"_value": schema["example"]}
    # Top-level examples (OpenAPI 3.1)
    if schema.get("examples"):
        examples = schema["examples"]
        if isinstance(examples, list) and examples:
            return examples[0] if isinstance(examples[0], dict) else {"_value": examples[0]}
        if isinstance(examples, dict):
            first = next(iter(examples.values()), None)
            if isinstance(first, dict) and "value" in first:
                return first["value"] if isinstance(first["value"], dict) else {"_value": first["value"]}
            return first if isinstance(first, dict) else None
    # Property-level examples
    props = schema.get("properties", {})
    if props:
        prop_examples = {}
        for fname, fprop in props.items():
            if not isinstance(fprop, dict):
                continue
            if "example" in fprop:
                prop_examples[fname] = fprop["example"]
            elif "default" in fprop:
                prop_examples[fname] = fprop["default"]
        if prop_examples:
            return prop_examples
    return None


def _parse_openapi_spec(spec: dict) -> Dict[str, Any]:
    """Parse an OpenAPI v2/v3 spec and extract enriched app_profile fields.

    Extracts:
    - api_base_url from servers (v3) or host+basePath (v2)
    - api_endpoints with typed required_fields, response_fields, test_data_hints
    - auth config from securitySchemes (v3) or securityDefinitions (v2)
    - info notes (title, version)
    """
    result: Dict[str, Any] = {}

    # Detect version
    is_v3 = spec.get("openapi", "").startswith("3")
    is_v2 = spec.get("swagger", "").startswith("2")

    # Extract base URL
    if is_v3 and spec.get("servers"):
        result["api_base_url"] = spec["servers"][0].get("url", "")
    elif is_v2:
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        schemes = spec.get("schemes", ["https"])
        scheme = schemes[0] if schemes else "https"
        if host:
            result["api_base_url"] = f"{scheme}://{host}{base_path}"

    # Extract API endpoints
    paths = spec.get("paths", {})
    endpoints = []
    for path, methods in list(paths.items())[:50]:  # Limit to 50 paths
        if not isinstance(methods, dict):
            continue
        for method_name, details in methods.items():
            if method_name.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            if not isinstance(details, dict):
                continue

            ep: Dict[str, Any] = {
                "method": method_name.upper(),
                "path": path,
                "description": (details.get("summary") or details.get("description") or "")[:200],
            }

            # ── Request body schema extraction ──

            # OpenAPI 3.x: requestBody -> content -> application/json -> schema
            req_body = details.get("requestBody", {})
            req_schema_resolved = None
            if req_body and isinstance(req_body, dict):
                content = req_body.get("content", {})
                json_schema = content.get("application/json", {}).get("schema", {})
                if json_schema:
                    req_schema_resolved = _resolve_schema(spec, json_schema)
                    typed_fields = _extract_schema_fields_typed(spec, json_schema)
                    if typed_fields:
                        ep["required_fields"] = typed_fields

                    # Extract request body examples for test_data_hints
                    examples = _extract_examples(spec, json_schema)
                    # Also check requestBody-level examples (OAS 3.x)
                    if not examples:
                        media = content.get("application/json", {})
                        if media.get("example"):
                            examples = media["example"] if isinstance(media["example"], dict) else {"_value": media["example"]}
                        elif media.get("examples"):
                            ex_map = media["examples"]
                            if isinstance(ex_map, dict):
                                first_ex = next(iter(ex_map.values()), {})
                                if isinstance(first_ex, dict) and "value" in first_ex:
                                    examples = first_ex["value"] if isinstance(first_ex["value"], dict) else {"_value": first_ex["value"]}
                    if examples:
                        ep["test_data_hints"] = examples

            # Swagger 2.0: parameters with in=body -> schema (refs go to #/definitions/...)
            params = details.get("parameters", [])
            if params and not req_schema_resolved:
                body_params = [p for p in params if isinstance(p, dict) and p.get("in") == "body"]
                if body_params:
                    schema = body_params[0].get("schema", {})
                    req_schema_resolved = _resolve_schema(spec, schema)
                    typed_fields = _extract_schema_fields_typed(spec, schema)
                    if typed_fields:
                        ep["required_fields"] = typed_fields
                    # Extract examples from v2 body schema
                    examples = _extract_examples(spec, schema)
                    if examples:
                        ep["test_data_hints"] = examples

            # ── Response schema extraction (typed) ──

            responses = details.get("responses", {})
            ok_resp = responses.get("200") or responses.get("201") or responses.get("2XX") or {}
            if ok_resp and isinstance(ok_resp, dict):
                # v3: content -> application/json -> schema
                resp_content = ok_resp.get("content", {})
                resp_schema = resp_content.get("application/json", {}).get("schema", {})
                if resp_schema:
                    typed_resp = _extract_response_fields_typed(spec, resp_schema)
                    if typed_resp:
                        ep["response_fields"] = typed_resp

                # v2 fallback: schema directly on response object
                if not ep.get("response_fields"):
                    v2_schema = ok_resp.get("schema", {})
                    if v2_schema:
                        typed_resp = _extract_response_fields_typed(spec, v2_schema)
                        if typed_resp:
                            ep["response_fields"] = typed_resp

                # Extract response examples for test_data_hints (if no request examples found)
                if not ep.get("test_data_hints"):
                    resp_ex_schema = resp_schema if resp_schema else ok_resp.get("schema", {})
                    if resp_ex_schema:
                        resp_examples = _extract_examples(spec, resp_ex_schema)
                        if resp_examples:
                            ep["test_data_hints"] = resp_examples

            endpoints.append(ep)

    result["api_endpoints"] = endpoints

    # ── Auth schemes extraction (enriched) ──

    security_schemes = {}
    if is_v3:
        security_schemes = spec.get("components", {}).get("securitySchemes", {})
    elif is_v2:
        security_schemes = spec.get("securityDefinitions", {})

    if security_schemes:
        auth_info: Dict[str, Any] = {}
        for name, scheme in security_schemes.items():
            if not isinstance(scheme, dict):
                continue
            scheme_type = scheme.get("type", "")

            # Bearer token (HTTP bearer scheme)
            if scheme_type == "http" and scheme.get("scheme", "").lower() == "bearer":
                auth_info["token_header"] = "Authorization"
                auth_info["token_prefix"] = "Bearer"
                auth_info["request_body"] = "POST to auth endpoint with credentials to obtain a Bearer token"
                bearer_format = scheme.get("bearerFormat")
                if bearer_format:
                    auth_info["bearer_format"] = bearer_format

            # API Key
            elif scheme_type == "apiKey":
                key_name = scheme.get("name", "X-API-Key")
                key_in = scheme.get("in", "header")
                if key_in == "header":
                    auth_info["token_header"] = key_name
                    auth_info["request_body"] = f"Include API key in header: {key_name}: <your-api-key>"
                elif key_in == "query":
                    auth_info["token_header"] = f"Query param: {key_name}"
                    auth_info["request_body"] = f"Include API key as query parameter: ?{key_name}=<your-api-key>"
                elif key_in == "cookie":
                    auth_info["token_header"] = f"Cookie: {key_name}"
                    auth_info["request_body"] = f"Include API key as cookie: {key_name}=<your-api-key>"

            # OAuth2 (v3 and v2)
            elif scheme_type == "oauth2":
                auth_info["token_header"] = "Authorization"
                auth_info["token_prefix"] = "Bearer"
                flows = scheme.get("flows") or scheme.get("flow")
                if isinstance(flows, dict):
                    # v3 flows object
                    flow_info = {}
                    for flow_name, flow_detail in flows.items():
                        if isinstance(flow_detail, dict):
                            fi: Dict[str, Any] = {"type": flow_name}
                            if flow_detail.get("authorizationUrl"):
                                fi["authorization_url"] = flow_detail["authorizationUrl"]
                            if flow_detail.get("tokenUrl"):
                                fi["token_url"] = flow_detail["tokenUrl"]
                            scopes = flow_detail.get("scopes", {})
                            if scopes:
                                fi["scopes"] = list(scopes.keys())[:10]
                            flow_info[flow_name] = fi
                    if flow_info:
                        auth_info["oauth2_flows"] = flow_info
                elif isinstance(flows, str):
                    # v2: flow is a string (implicit, password, application, accessCode)
                    auth_info["oauth2_flows"] = {flows: {"type": flows}}
                    if scheme.get("authorizationUrl"):
                        auth_info["oauth2_flows"][flows]["authorization_url"] = scheme["authorizationUrl"]
                    if scheme.get("tokenUrl"):
                        auth_info["oauth2_flows"][flows]["token_url"] = scheme["tokenUrl"]
                    scopes = scheme.get("scopes", {})
                    if scopes:
                        auth_info["oauth2_flows"][flows]["scopes"] = list(scopes.keys())[:10]

                auth_info["request_body"] = "OAuth2 flow - obtain token from authorization/token endpoint"

            # Basic auth
            elif scheme_type == "http" and scheme.get("scheme", "").lower() == "basic":
                auth_info["token_header"] = "Authorization"
                auth_info["token_prefix"] = "Basic"
                auth_info["request_body"] = "Base64-encode 'username:password' and include as Authorization: Basic <encoded>"

        if auth_info:
            result["auth"] = auth_info

    # Extract description from info
    info = spec.get("info", {})
    notes_parts = []
    if info.get("title"):
        notes_parts.append(f"API: {info['title']}")
    if info.get("version"):
        notes_parts.append(f"Version: {info['version']}")
    if notes_parts:
        result["notes"] = ". ".join(notes_parts)

    return result


@router.post(
    "/{project_id}/app-profile/discover",
    response_model=ProjectResponse,
    summary="Auto-discover API endpoints from OpenAPI spec",
)
async def discover_openapi(
    project_id: uuid.UUID,
    body: OpenAPIDiscoverRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch an OpenAPI/Swagger spec from a URL, parse it, and merge
    discovered endpoints into the project's app_profile.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    openapi_url = body.openapi_url.strip()
    if not _is_safe_url(openapi_url):
        raise HTTPException(status_code=400, detail="URL is blocked for security (private/localhost)")

    # Fetch the spec
    try:
        async with httpx.AsyncClient(verify=False, timeout=20) as client:
            resp = await client.get(openapi_url)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch OpenAPI spec: HTTP {exc.response.status_code}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch OpenAPI spec: {type(exc).__name__}: {str(exc)[:200]}",
        )

    # Parse JSON or YAML
    content_type = resp.headers.get("content-type", "")
    try:
        if "yaml" in content_type or "yml" in content_type or openapi_url.endswith((".yaml", ".yml")):
            try:
                import yaml
                spec = yaml.safe_load(resp.text)
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="YAML parsing not available. Install pyyaml: pip install pyyaml",
                )
        else:
            spec = resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse OpenAPI spec: {str(exc)[:200]}",
        )

    if not isinstance(spec, dict):
        raise HTTPException(status_code=400, detail="OpenAPI spec must be a JSON/YAML object")

    # Parse the spec
    discovered = _parse_openapi_spec(spec)

    # Merge with existing app_profile (don't overwrite user edits)
    existing = project.app_profile or {}

    # Only set api_base_url if not already configured
    if discovered.get("api_base_url") and not existing.get("api_base_url"):
        existing["api_base_url"] = discovered["api_base_url"]

    # Merge endpoints: add new ones, keep existing
    existing_paths = set()
    for ep in existing.get("api_endpoints", []):
        if isinstance(ep, dict):
            existing_paths.add(f"{ep.get('method', 'GET')}:{ep.get('path', '')}")

    merged_endpoints = list(existing.get("api_endpoints", []))
    new_count = 0
    for ep in discovered.get("api_endpoints", []):
        key = f"{ep.get('method', 'GET')}:{ep.get('path', '')}"
        if key not in existing_paths:
            merged_endpoints.append(ep)
            new_count += 1
    existing["api_endpoints"] = merged_endpoints

    # Merge auth if not already configured
    if discovered.get("auth") and not existing.get("auth"):
        existing["auth"] = discovered["auth"]

    # Append notes
    if discovered.get("notes"):
        existing_notes = existing.get("notes", "")
        if existing_notes:
            existing["notes"] = f"{existing_notes}\n{discovered['notes']}"
        else:
            existing["notes"] = discovered["notes"]

    project.app_profile = existing
    flag_modified(project, "app_profile")
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="discover_openapi",
        entity_type="project",
        entity_id=str(project.id),
        details={"openapi_url": openapi_url, "endpoints_discovered": len(discovered.get("api_endpoints", [])), "new_endpoints": new_count},
        ip_address=get_client_ip(request),
    )

    logger.info(
        "OpenAPI discovery for project %s: %d endpoints found, %d new (from %s)",
        project.name, len(discovered.get("api_endpoints", [])), new_count, openapi_url,
    )

    return ProjectResponse.model_validate(project)


# ---------------------------------------------------------------------------
# POST /{id}/app-profile/discover-ui  (AI-Powered UI Discovery)
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/app-profile/discover-ui",
    response_model=ProjectResponse,
    summary="AI-discover UI pages using Playwright + LLM vision",
)
async def discover_ui_pages_route(
    project_id: uuid.UUID,
    body: UIDiscoverRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Launch an AI discovery agent that uses Playwright headless browser to:
    1. Navigate to each specified route
    2. Take a screenshot + capture accessibility tree
    3. Send both to LLM (with vision) for analysis
    4. Extract semantic Playwright locators (get_by_role, get_by_label, etc.)
    5. Merge discovered pages into the project's app_profile.ui_pages
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    profile = project.app_profile or {}
    app_url = profile.get("app_url", "")
    if not app_url:
        raise HTTPException(
            status_code=400,
            detail="No app_url configured in the App Profile. Set the Application URL first.",
        )

    if not _is_safe_url(app_url):
        raise HTTPException(status_code=400, detail="app_url is blocked for security (private/localhost)")

    # Build auth config from app profile
    auth_config = None
    auth = profile.get("auth", {})
    creds = auth.get("test_credentials", {})
    if creds.get("email") and creds.get("password"):
        auth_config = {
            "email": creds["email"],
            "password": creds["password"],
            "login_url": auth.get("login_url") or "/login",
            "selectors": {
                "username_selector": auth.get("username_selector"),
                "password_selector": auth.get("password_selector"),
                "submit_selector": auth.get("submit_selector"),
            },
        }

    # Run discovery
    try:
        from execution.ui_discovery import discover_ui_pages

        result = await discover_ui_pages(
            app_url=app_url,
            routes=body.routes,
            auth_config=auth_config,
            crawl=body.crawl,
            max_pages=body.max_pages,
        )
    except Exception as exc:
        logger.error("UI discovery failed for project %s: %s", project.name, exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"UI discovery failed: {type(exc).__name__}: {str(exc)[:200]}",
        )

    # Merge discovered pages into app_profile.ui_pages (additive)
    existing_pages = profile.get("ui_pages", [])
    existing_routes = {pg.get("route") for pg in existing_pages if isinstance(pg, dict)}

    new_count = 0
    for page_info in result.get("pages", []):
        route = page_info.get("route", "")
        if route in existing_routes:
            # Update existing page with fresh discovery data
            for i, ep in enumerate(existing_pages):
                if ep.get("route") == route:
                    existing_pages[i] = page_info
                    break
        else:
            existing_pages.append(page_info)
            new_count += 1

    profile["ui_pages"] = existing_pages
    project.app_profile = profile
    flag_modified(project, "app_profile")
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="discover_ui",
        entity_type="project",
        entity_id=str(project.id),
        details={
            "routes_requested": body.routes,
            "crawl": body.crawl,
            "pages_discovered": result["stats"]["pages_discovered"],
            "elements_found": result["stats"]["elements_found"],
            "new_pages": new_count,
            "duration_seconds": result["stats"]["duration_seconds"],
            "errors": result.get("errors", []),
        },
        ip_address=get_client_ip(request),
    )

    logger.info(
        "UI discovery for project %s: %d pages discovered, %d elements, %d new (%s)",
        project.name,
        result["stats"]["pages_discovered"],
        result["stats"]["elements_found"],
        new_count,
        f"{result['stats']['duration_seconds']}s",
    )

    return ProjectResponse.model_validate(project)


# ═══════════════════════════════════════════════════════════════════════════
# Agent API Key Management
# ═══════════════════════════════════════════════════════════════════════════
@router.post("/{project_id}/agent-key", response_model=AgentKeyResponse)
def generate_agent_key(
    project_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate an agent API key for the project.
    The raw key is returned ONCE — only the SHA-256 hash is stored.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    # Generate a secure random key with prefix for identification
    raw_key = f"qf_{secrets.token_urlsafe(48)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    project.agent_api_key_hash = key_hash
    db.commit()

    audit_log(
        db,
        current_user.id,
        action="generate_agent_key",
        entity_type="project",
        entity_id=str(project.id),
        ip_address=get_client_ip(request),
    )

    logger.info("Agent API key generated for project %s by %s", project.name, current_user.email)

    return AgentKeyResponse(
        api_key=raw_key,
        project_id=project.id,
        project_name=project.name,
    )


@router.delete("/{project_id}/agent-key", response_model=MessageResponse)
def revoke_agent_key(
    project_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the agent API key for the project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    if not project.agent_api_key_hash:
        raise HTTPException(400, "No agent key exists for this project")

    project.agent_api_key_hash = None
    db.commit()

    audit_log(
        db,
        current_user.id,
        action="revoke_agent_key",
        entity_type="project",
        entity_id=str(project.id),
        ip_address=get_client_ip(request),
    )

    logger.info("Agent API key revoked for project %s by %s", project.name, current_user.email)

    return MessageResponse(message="Agent API key revoked")
