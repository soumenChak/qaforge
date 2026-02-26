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

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from db_models import Project, Requirement, TestCase, User
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    sanitize_string,
)
from models import (
    MessageResponse,
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
