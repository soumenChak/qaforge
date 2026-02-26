"""
QAForge -- Template management routes.

Prefix: /api/templates

Endpoints:
    POST   /             — create template
    GET    /             — list templates (filter by domain)
    GET    /{id}         — template detail
    GET    /{id}/preview — preview template column mapping
    DELETE /{id}         — delete template
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from db_models import TestTemplate, User
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    sanitize_string,
)
from models import MessageResponse, TemplateCreate, TemplateResponse, TemplateUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=TemplateResponse,
    summary="Create an export template",
    status_code=status.HTTP_201_CREATED,
)
def create_template(
    body: TemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new export template for test case output formatting."""
    template = TestTemplate(
        name=sanitize_string(body.name) or body.name,
        domain=body.domain,
        format=body.format,
        template_file_path=body.template_file_path,
        column_mapping=body.column_mapping,
        branding_config=body.branding_config,
        created_by=current_user.id,
    )
    db.add(template)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="create_template",
        entity_type="template",
        entity_id=str(template.id),
        details={"name": template.name, "domain": template.domain, "format": template.format},
        ip_address=get_client_ip(request),
    )

    logger.info("Template created: %s by %s", template.name, current_user.email)

    return TemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=list[TemplateResponse],
    summary="List templates",
)
def list_templates(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all templates, optionally filtered by domain."""
    query = db.query(TestTemplate)

    if domain:
        query = query.filter(TestTemplate.domain == domain)

    templates = query.order_by(TestTemplate.created_at.desc()).all()
    return [TemplateResponse.model_validate(t) for t in templates]


# ---------------------------------------------------------------------------
# GET /{id}
# ---------------------------------------------------------------------------
@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Get template detail",
)
def get_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single template by ID."""
    template = db.query(TestTemplate).filter(TestTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    return TemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# GET /{id}/preview
# ---------------------------------------------------------------------------
@router.get(
    "/{template_id}/preview",
    summary="Preview template structure",
)
def preview_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview a template's column mapping and branding configuration.

    Returns the column_mapping and branding_config as-is for frontend rendering.
    """
    template = db.query(TestTemplate).filter(TestTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return {
        "id": str(template.id),
        "name": template.name,
        "format": template.format,
        "column_mapping": template.column_mapping or _default_column_mapping(),
        "branding_config": template.branding_config,
    }


# ---------------------------------------------------------------------------
# PUT /{id}
# ---------------------------------------------------------------------------
@router.put(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Update a template",
)
def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing export template (partial update)."""
    template = db.query(TestTemplate).filter(TestTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"]:
        update_data["name"] = sanitize_string(update_data["name"]) or update_data["name"]

    for field, value in update_data.items():
        setattr(template, field, value)

    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="update_template",
        entity_type="template",
        entity_id=str(template_id),
        details={"fields_updated": list(update_data.keys())},
        ip_address=get_client_ip(request),
    )

    logger.info("Template updated: %s by %s", template.name, current_user.email)

    return TemplateResponse.model_validate(template)


# ---------------------------------------------------------------------------
# DELETE /{id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{template_id}",
    response_model=MessageResponse,
    summary="Delete a template",
)
def delete_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an export template."""
    template = db.query(TestTemplate).filter(TestTemplate.id == template_id).first()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    name = template.name
    db.delete(template)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_template",
        entity_type="template",
        entity_id=str(template_id),
        details={"name": name},
        ip_address=get_client_ip(request),
    )

    logger.info("Template deleted: %s by %s", name, current_user.email)

    return MessageResponse(message=f"Template '{name}' deleted")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _default_column_mapping() -> dict:
    """Return the default column mapping for Excel export."""
    return {
        "A": "Test Case ID",
        "B": "Title",
        "C": "Description",
        "D": "Preconditions",
        "E": "Test Steps",
        "F": "Expected Result",
        "G": "Priority",
        "H": "Category",
        "I": "Status",
        "J": "Test Data",
    }
