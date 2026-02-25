"""
QAForge -- Knowledge base routes.

Prefix: /api/knowledge

Endpoints:
    GET  /search — search knowledge entries (ILIKE text search; vector search in Phase 2)
    POST /       — add a knowledge entry manually
    GET  /stats  — knowledge base statistics
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from db_models import KnowledgeEntry, User
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    sanitize_string,
)
from models import KnowledgeEntryCreate, KnowledgeEntryResponse, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------
@router.get(
    "/search",
    response_model=list[KnowledgeEntryResponse],
    summary="Search knowledge entries",
)
def search_knowledge(
    q: str = Query(..., min_length=2, description="Search text"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    entry_type: Optional[str] = Query(None, description="Filter by entry_type"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search knowledge entries using ILIKE text search.

    Searches across title, content, and tags. In Phase 2 this will be
    augmented with ChromaDB vector/semantic search.
    """
    search_pattern = f"%{q}%"

    query = db.query(KnowledgeEntry).filter(
        or_(
            KnowledgeEntry.title.ilike(search_pattern),
            KnowledgeEntry.content.ilike(search_pattern),
        )
    )

    if domain:
        query = query.filter(KnowledgeEntry.domain == domain)
    if entry_type:
        query = query.filter(KnowledgeEntry.entry_type == entry_type)

    entries = (
        query.order_by(KnowledgeEntry.usage_count.desc(), KnowledgeEntry.created_at.desc())
        .limit(limit)
        .all()
    )

    # Increment usage_count for returned entries
    for entry in entries:
        entry.usage_count += 1
    db.flush()

    return [KnowledgeEntryResponse.model_validate(e) for e in entries]


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=KnowledgeEntryResponse,
    summary="Add a knowledge entry",
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_entry(
    body: KnowledgeEntryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add a knowledge entry manually to the knowledge base.

    Knowledge entries represent domain-specific patterns, defects,
    best practices, or reusable test cases.
    """
    entry = KnowledgeEntry(
        domain=body.domain,
        sub_domain=body.sub_domain,
        entry_type=body.entry_type,
        title=sanitize_string(body.title) or body.title,
        content=sanitize_string(body.content) or body.content,
        tags=body.tags,
        source_project_id=body.source_project_id,
        created_by=current_user.id,
    )
    db.add(entry)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="create_knowledge_entry",
        entity_type="knowledge_entry",
        entity_id=str(entry.id),
        details={
            "domain": entry.domain,
            "entry_type": entry.entry_type,
            "title": entry.title,
        },
        ip_address=get_client_ip(request),
    )

    logger.info(
        "Knowledge entry created: %s [%s/%s] by %s",
        entry.title[:50],
        entry.domain,
        entry.entry_type,
        current_user.email,
    )

    return KnowledgeEntryResponse.model_validate(entry)


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------
@router.get(
    "/stats",
    summary="Knowledge base statistics",
)
def get_knowledge_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return knowledge base statistics.

    Includes:
    - Total entry count
    - Entries per domain
    - Entries per type
    - Most-used entries
    """
    total = db.query(func.count(KnowledgeEntry.id)).scalar() or 0

    # Entries per domain
    domain_rows = (
        db.query(KnowledgeEntry.domain, func.count(KnowledgeEntry.id))
        .group_by(KnowledgeEntry.domain)
        .order_by(func.count(KnowledgeEntry.id).desc())
        .all()
    )
    entries_by_domain: Dict[str, int] = {row[0]: row[1] for row in domain_rows}

    # Entries per type
    type_rows = (
        db.query(KnowledgeEntry.entry_type, func.count(KnowledgeEntry.id))
        .group_by(KnowledgeEntry.entry_type)
        .order_by(func.count(KnowledgeEntry.id).desc())
        .all()
    )
    entries_by_type: Dict[str, int] = {row[0]: row[1] for row in type_rows}

    # Top used entries
    top_used = (
        db.query(KnowledgeEntry)
        .filter(KnowledgeEntry.usage_count > 0)
        .order_by(KnowledgeEntry.usage_count.desc())
        .limit(10)
        .all()
    )
    top_used_list: List[Dict[str, Any]] = [
        {
            "id": str(e.id),
            "title": e.title,
            "domain": e.domain,
            "entry_type": e.entry_type,
            "usage_count": e.usage_count,
        }
        for e in top_used
    ]

    return {
        "total_entries": total,
        "entries_by_domain": entries_by_domain,
        "entries_by_type": entries_by_type,
        "top_used": top_used_list,
    }
