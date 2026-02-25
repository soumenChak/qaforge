"""
QAForge -- Requirements management routes.

Prefix: /api/projects/{project_id}/requirements

Note: The main.py prefix_map has "requirements" -> "/api/requirements", but
these routes use path-based project scoping. The router itself defines the
full sub-paths including the project_id prefix.

Endpoints:
    POST   /                              — add manual requirement
    GET    /                              — list requirements for project
    PUT    /{req_id}                      — update requirement
    DELETE /{req_id}                      — delete requirement
    POST   /upload                        — upload raw BRD/PRD text
    POST   /extract                       — LLM-powered extraction
"""

import json
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from db_models import Project, Requirement, User
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    sanitize_string,
    track_cost,
)
from models import (
    MessageResponse,
    RequirementCreate,
    RequirementExtractRequest,
    RequirementResponse,
    RequirementUpdate,
    UploadTextRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for uploaded BRD/PRD text, keyed by project_id.
# In production this would be persisted, but for Phase 1 this is sufficient.
_uploaded_texts: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_project_or_404(project_id: uuid.UUID, db: Session) -> Project:
    """Fetch a project by ID or raise 404."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def _get_next_req_id(project_id: uuid.UUID, db: Session) -> str:
    """Generate the next sequential REQ-NNN id for a project."""
    count = db.query(Requirement).filter(
        Requirement.project_id == project_id
    ).count()
    return f"REQ-{count + 1:03d}"


# ---------------------------------------------------------------------------
# POST /{project_id}/requirements/
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/requirements",
    response_model=RequirementResponse,
    summary="Add a manual requirement",
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    project_id: uuid.UUID,
    body: RequirementCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a requirement to a project."""
    _get_project_or_404(project_id, db)

    # Check for duplicate req_id within this project
    existing = db.query(Requirement).filter(
        Requirement.project_id == project_id,
        Requirement.req_id == body.req_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Requirement '{body.req_id}' already exists in this project",
        )

    req = Requirement(
        project_id=project_id,
        req_id=body.req_id,
        title=sanitize_string(body.title) or body.title,
        description=sanitize_string(body.description) if body.description else None,
        priority=body.priority,
        category=sanitize_string(body.category) if body.category else None,
        source=body.source,
    )
    db.add(req)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="create_requirement",
        entity_type="requirement",
        entity_id=str(req.id),
        details={"project_id": str(project_id), "req_id": req.req_id},
        ip_address=get_client_ip(request),
    )

    return RequirementResponse.model_validate(req)


# ---------------------------------------------------------------------------
# GET /{project_id}/requirements/
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/requirements",
    response_model=list[RequirementResponse],
    summary="List requirements for a project",
)
def list_requirements(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all requirements belonging to a project."""
    _get_project_or_404(project_id, db)

    reqs = (
        db.query(Requirement)
        .filter(Requirement.project_id == project_id)
        .order_by(Requirement.created_at.asc())
        .all()
    )
    return [RequirementResponse.model_validate(r) for r in reqs]


# ---------------------------------------------------------------------------
# PUT /{project_id}/requirements/{req_id}
# ---------------------------------------------------------------------------
@router.put(
    "/{project_id}/requirements/{requirement_id}",
    response_model=RequirementResponse,
    summary="Update a requirement",
)
def update_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    body: RequirementUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update fields of an existing requirement."""
    _get_project_or_404(project_id, db)

    req = db.query(Requirement).filter(
        Requirement.id == requirement_id,
        Requirement.project_id == project_id,
    ).first()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requirement not found",
        )

    if body.title is not None:
        req.title = sanitize_string(body.title) or body.title
    if body.description is not None:
        req.description = sanitize_string(body.description)
    if body.priority is not None:
        req.priority = body.priority
    if body.category is not None:
        req.category = sanitize_string(body.category)
    if body.status is not None:
        req.status = body.status

    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="update_requirement",
        entity_type="requirement",
        entity_id=str(req.id),
        details=body.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )

    return RequirementResponse.model_validate(req)


# ---------------------------------------------------------------------------
# DELETE /{project_id}/requirements/{req_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{project_id}/requirements/{requirement_id}",
    response_model=MessageResponse,
    summary="Delete a requirement",
)
def delete_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a requirement from a project."""
    _get_project_or_404(project_id, db)

    req = db.query(Requirement).filter(
        Requirement.id == requirement_id,
        Requirement.project_id == project_id,
    ).first()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requirement not found",
        )

    req_display = req.req_id
    db.delete(req)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_requirement",
        entity_type="requirement",
        entity_id=str(requirement_id),
        details={"project_id": str(project_id), "req_id": req_display},
        ip_address=get_client_ip(request),
    )

    return MessageResponse(message=f"Requirement '{req_display}' deleted")


# ---------------------------------------------------------------------------
# POST /{project_id}/requirements/upload
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/requirements/upload",
    response_model=MessageResponse,
    summary="Upload BRD/PRD text",
    status_code=status.HTTP_201_CREATED,
)
def upload_text(
    project_id: uuid.UUID,
    body: UploadTextRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accept raw BRD/PRD text for a project.

    The text is stored temporarily and can be used by the /extract endpoint
    to perform LLM-powered requirement extraction.
    """
    _get_project_or_404(project_id, db)

    _uploaded_texts[str(project_id)] = {
        "text": body.document_text,
        "type": body.document_type,
        "uploaded_by": str(current_user.id),
    }

    audit_log(
        db,
        user_id=current_user.id,
        action="upload_requirements_text",
        entity_type="requirement",
        entity_id=str(project_id),
        details={
            "document_type": body.document_type,
            "text_length": len(body.document_text),
        },
        ip_address=get_client_ip(request),
    )

    return MessageResponse(
        message="Document text uploaded successfully",
        detail=f"Stored {len(body.document_text)} characters of {body.document_type.upper()} text",
    )


# ---------------------------------------------------------------------------
# POST /{project_id}/requirements/extract
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/requirements/extract",
    response_model=list[RequirementResponse],
    summary="Extract requirements using LLM",
    status_code=status.HTTP_201_CREATED,
)
def extract_requirements(
    project_id: uuid.UUID,
    body: RequirementExtractRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Use an LLM to extract structured requirements from document text.

    Attempts to use the core LLM provider. Falls back to a simple
    heuristic extractor if the LLM is not configured or fails.
    """
    project = _get_project_or_404(project_id, db)

    document_text = body.document_text

    # Attempt LLM extraction
    extracted = _extract_via_llm(
        document_text=document_text,
        document_type=body.document_type,
        domain=body.domain or project.domain,
        sub_domain=body.sub_domain or project.sub_domain,
        project_id=project_id,
        user_id=current_user.id,
        db=db,
    )

    # Persist extracted requirements
    created_reqs = []
    base_count = db.query(Requirement).filter(
        Requirement.project_id == project_id
    ).count()

    for i, item in enumerate(extracted):
        req_id = f"REQ-{base_count + i + 1:03d}"

        # Check for duplicate req_id
        existing = db.query(Requirement).filter(
            Requirement.project_id == project_id,
            Requirement.req_id == req_id,
        ).first()
        if existing:
            req_id = f"REQ-{base_count + i + 100:03d}"

        req = Requirement(
            project_id=project_id,
            req_id=req_id,
            title=sanitize_string(item.get("title", "Untitled Requirement")) or "Untitled",
            description=sanitize_string(item.get("description")),
            priority=item.get("priority", "medium"),
            category=sanitize_string(item.get("category")),
            source=body.document_type,
        )
        db.add(req)
        db.flush()
        created_reqs.append(req)

    audit_log(
        db,
        user_id=current_user.id,
        action="extract_requirements",
        entity_type="requirement",
        entity_id=str(project_id),
        details={
            "document_type": body.document_type,
            "extracted_count": len(created_reqs),
        },
        ip_address=get_client_ip(request),
    )

    logger.info(
        "Extracted %d requirements for project %s by %s",
        len(created_reqs),
        project.name,
        current_user.email,
    )

    return [RequirementResponse.model_validate(r) for r in created_reqs]


# ---------------------------------------------------------------------------
# LLM extraction helper
# ---------------------------------------------------------------------------
def _extract_via_llm(
    document_text: str,
    document_type: str,
    domain: str,
    sub_domain: str,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
) -> list[dict]:
    """
    Call the LLM to extract testable requirements from document text.

    Falls back to a heuristic paragraph-based splitter if the LLM
    provider is not available.
    """
    prompt = f"""You are a QA requirements analyst. Extract testable requirements from the following {document_type.upper()} document text.

Domain: {domain}
Sub-domain: {sub_domain}

For each requirement, return a JSON array of objects with these fields:
- "title": A concise requirement title (max 100 chars)
- "description": Detailed description of the requirement
- "priority": One of "high", "medium", "low"
- "category": A category label (e.g., "functional", "data_quality", "integration", "security", "performance")

Return ONLY the JSON array, no other text.

Document text:
---
{document_text[:8000]}
---"""

    # Try the core LLM provider
    try:
        from core.llm_provider import get_llm_provider  # type: ignore

        provider = get_llm_provider()
        response = provider.generate(prompt=prompt)
        parsed = json.loads(response)
        if isinstance(parsed, list):
            track_cost(
                db,
                user_id=user_id,
                project_id=project_id,
                operation_type="llm",
                provider=getattr(provider, "provider_name", "unknown"),
                model=getattr(provider, "model_name", "unknown"),
            )
            return parsed
    except ImportError:
        logger.info("core.llm_provider not available; using heuristic extraction")
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON response; falling back to heuristic")
    except Exception:
        logger.warning("LLM extraction failed; falling back to heuristic", exc_info=True)

    # Heuristic fallback: split on paragraphs / numbered lines
    return _heuristic_extract(document_text, document_type)


def _heuristic_extract(document_text: str, document_type: str) -> list[dict]:
    """
    Simple heuristic: split text into paragraphs and treat each
    substantial paragraph as a requirement.
    """
    import re

    # Split on double newlines, numbered lists, or bullet points
    segments = re.split(r"\n\s*\n|\n\s*\d+\.\s+|\n\s*[-*]\s+", document_text)
    results = []

    for seg in segments:
        text = seg.strip()
        if len(text) < 20:
            continue

        # Use first sentence or first 100 chars as title
        title_end = min(
            text.find(".") if text.find(".") > 0 else len(text),
            100,
        )
        title = text[:title_end].strip()

        results.append({
            "title": title,
            "description": text,
            "priority": "medium",
            "category": "functional",
        })

        # Limit to 50 requirements from heuristic extraction
        if len(results) >= 50:
            break

    return results
