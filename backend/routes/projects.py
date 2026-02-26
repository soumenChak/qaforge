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

import ipaddress
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from db_models import Project, Requirement, TestCase, User
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    sanitize_string,
)
from models import (
    CoverageResult,
    MessageResponse,
    OpenAPIDiscoverRequest,
    ProfileValidationResult,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
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

    project.app_profile = body
    flag_modified(project, "app_profile")
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="update_app_profile",
        entity_type="project",
        entity_id=str(project.id),
        details={"keys": list(body.keys())},
        ip_address=get_client_ip(request),
    )

    logger.info("App profile updated for project %s by %s", project.name, current_user.email)

    return ProjectResponse.model_validate(project)


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

    # Cascade delete test cases and requirements
    db.query(TestCase).filter(TestCase.project_id == project_id).delete()
    db.query(Requirement).filter(Requirement.project_id == project_id).delete()
    db.delete(project)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_project",
        entity_type="project",
        entity_id=str(project_id),
        details={"name": project_name},
        ip_address=get_client_ip(request),
    )

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
        login_url = f"{base_url.rstrip('/')}{path}" if base_url and not path.startswith("http") else path

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
        sample_url = f"{base_url.rstrip('/')}{sample_ep['path']}"
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
def _parse_openapi_spec(spec: dict) -> Dict[str, Any]:
    """Parse an OpenAPI v2/v3 spec and extract app_profile fields."""
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
        for method_name, details in methods.items():
            if method_name.lower() in ("get", "post", "put", "delete", "patch"):
                ep: Dict[str, Any] = {
                    "method": method_name.upper(),
                    "path": path,
                    "description": (details.get("summary") or details.get("description") or "")[:200],
                }

                # Extract required fields from request body (v3)
                req_body = details.get("requestBody", {})
                if req_body:
                    content = req_body.get("content", {})
                    json_schema = content.get("application/json", {}).get("schema", {})
                    # Resolve $ref if present
                    if "$ref" in json_schema:
                        ref_path = json_schema["$ref"].split("/")
                        schema_obj = spec
                        for part in ref_path[1:]:  # skip '#'
                            schema_obj = schema_obj.get(part, {})
                        json_schema = schema_obj
                    if json_schema.get("required"):
                        ep["required_fields"] = json_schema["required"][:20]
                    if json_schema.get("properties"):
                        ep["response_fields"] = list(json_schema["properties"].keys())[:20]

                # Extract required fields from parameters (v2)
                params = details.get("parameters", [])
                if params:
                    required_params = [
                        p.get("name") for p in params
                        if isinstance(p, dict) and p.get("required") and p.get("in") == "body"
                    ]
                    body_params = [p for p in params if isinstance(p, dict) and p.get("in") == "body"]
                    if body_params:
                        schema = body_params[0].get("schema", {})
                        if "$ref" in schema:
                            ref_path = schema["$ref"].split("/")
                            schema_obj = spec
                            for part in ref_path[1:]:
                                schema_obj = schema_obj.get(part, {})
                            schema = schema_obj
                        if schema.get("required"):
                            ep["required_fields"] = schema["required"][:20]
                        if schema.get("properties"):
                            ep["response_fields"] = list(schema["properties"].keys())[:20]

                # Extract response fields from 200 response
                responses = details.get("responses", {})
                ok_resp = responses.get("200") or responses.get("201") or responses.get("2XX") or {}
                if ok_resp:
                    # v3
                    resp_content = ok_resp.get("content", {})
                    resp_schema = resp_content.get("application/json", {}).get("schema", {})
                    if "$ref" in resp_schema:
                        ref_path = resp_schema["$ref"].split("/")
                        schema_obj = spec
                        for part in ref_path[1:]:
                            schema_obj = schema_obj.get(part, {})
                        resp_schema = schema_obj
                    # Handle array response with items
                    if resp_schema.get("type") == "array" and resp_schema.get("items"):
                        items_schema = resp_schema["items"]
                        if "$ref" in items_schema:
                            ref_path = items_schema["$ref"].split("/")
                            schema_obj = spec
                            for part in ref_path[1:]:
                                schema_obj = schema_obj.get(part, {})
                            items_schema = schema_obj
                        if items_schema.get("properties"):
                            ep["response_fields"] = list(items_schema["properties"].keys())[:20]
                    elif resp_schema.get("properties"):
                        ep["response_fields"] = list(resp_schema["properties"].keys())[:20]

                    # v2 schema
                    if not ep.get("response_fields"):
                        v2_schema = ok_resp.get("schema", {})
                        if "$ref" in v2_schema:
                            ref_path = v2_schema["$ref"].split("/")
                            schema_obj = spec
                            for part in ref_path[1:]:
                                schema_obj = schema_obj.get(part, {})
                            v2_schema = schema_obj
                        if v2_schema.get("properties"):
                            ep["response_fields"] = list(v2_schema["properties"].keys())[:20]

                endpoints.append(ep)

    result["api_endpoints"] = endpoints

    # Extract auth schemes
    security_schemes = {}
    if is_v3:
        security_schemes = spec.get("components", {}).get("securitySchemes", {})
    elif is_v2:
        security_schemes = spec.get("securityDefinitions", {})

    if security_schemes:
        auth_info: Dict[str, Any] = {}
        for name, scheme in security_schemes.items():
            scheme_type = scheme.get("type", "")
            if scheme_type == "http" and scheme.get("scheme") == "bearer":
                auth_info["token_header"] = "Authorization: Bearer <access_token>"
            elif scheme_type == "apiKey":
                key_name = scheme.get("name", "X-API-Key")
                key_in = scheme.get("in", "header")
                auth_info["token_header"] = f"{key_name}: <api_key> (in {key_in})"
            elif scheme_type == "oauth2":
                auth_info["token_header"] = "Authorization: Bearer <oauth2_token>"
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
