"""
QAForge -- Testing Frameworks routes.

Prefix: /api/frameworks

Dedicated endpoint for testing framework management, separate from
the Knowledge Base entries API.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from db_models import KnowledgeEntry, User
from db_session import get_db
from dependencies import get_current_user, sanitize_string

logger = logging.getLogger(__name__)

router = APIRouter()

FRAMEWORK_TYPE = "framework_pattern"


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get("/", summary="List testing frameworks")
def list_frameworks(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all testing framework entries. No pagination — frameworks are few."""
    query = db.query(KnowledgeEntry).filter(
        KnowledgeEntry.entry_type == FRAMEWORK_TYPE,
    )
    if domain:
        query = query.filter(KnowledgeEntry.domain == domain)

    entries = query.order_by(
        KnowledgeEntry.domain,
        KnowledgeEntry.title,
    ).all()

    return [
        {
            "id": str(e.id),
            "domain": e.domain,
            "sub_domain": e.sub_domain,
            "title": e.title,
            "content": e.content,
            "tags": e.tags or [],
            "version": e.version,
            "usage_count": e.usage_count or 0,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------
@router.get("/stats", summary="Framework statistics")
def framework_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Quick stats for frameworks: total, by domain, usage."""
    base = db.query(KnowledgeEntry).filter(
        KnowledgeEntry.entry_type == FRAMEWORK_TYPE,
    )
    total = base.count()

    domain_rows = (
        base.with_entities(KnowledgeEntry.domain, func.count(KnowledgeEntry.id))
        .group_by(KnowledgeEntry.domain)
        .all()
    )
    by_domain = {row[0]: row[1] for row in domain_rows}

    total_usage = base.with_entities(
        func.coalesce(func.sum(KnowledgeEntry.usage_count), 0)
    ).scalar()
    active = base.filter(KnowledgeEntry.usage_count > 0).count()

    return {
        "total": total,
        "domains": len(by_domain),
        "by_domain": by_domain,
        "total_usage": total_usage,
        "active": active,
    }
