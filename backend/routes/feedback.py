"""
QAForge -- Feedback and learning metrics routes.

Prefix: /api/feedback

Endpoints:
    GET /metrics     — quality trends: avg rating over time, distribution, improvement
    GET /corrections — recent corrections (low-rated feedback with corrected content)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session

from db_models import FeedbackEntry, User
from db_session import get_db
from dependencies import get_current_user
from models import FeedbackCorrectionResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /metrics
# ---------------------------------------------------------------------------
@router.get(
    "/metrics",
    summary="Get quality metrics and trends",
)
def get_feedback_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Return aggregated feedback metrics for the quality dashboard.

    Includes:
    - Average rating (overall and daily trend over the requested period)
    - Rating distribution (count per star level 1-5)
    - Improvement trend (comparing first half vs second half of the period)
    - Total feedback count
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # ── Overall stats ──
    total = db.query(func.count(FeedbackEntry.id)).filter(
        FeedbackEntry.created_at >= cutoff
    ).scalar() or 0

    avg_rating = db.query(func.avg(FeedbackEntry.rating)).filter(
        FeedbackEntry.created_at >= cutoff
    ).scalar()

    # ── Rating distribution ──
    distribution_rows = (
        db.query(FeedbackEntry.rating, func.count(FeedbackEntry.id))
        .filter(FeedbackEntry.created_at >= cutoff)
        .group_by(FeedbackEntry.rating)
        .all()
    )
    rating_distribution: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for rating_val, count in distribution_rows:
        if rating_val in rating_distribution:
            rating_distribution[rating_val] = count

    # ── Daily trend ──
    daily_rows = (
        db.query(
            cast(FeedbackEntry.created_at, Date).label("day"),
            func.avg(FeedbackEntry.rating).label("avg_rating"),
            func.count(FeedbackEntry.id).label("count"),
        )
        .filter(FeedbackEntry.created_at >= cutoff)
        .group_by(cast(FeedbackEntry.created_at, Date))
        .order_by(cast(FeedbackEntry.created_at, Date).asc())
        .all()
    )

    daily_trend: List[Dict[str, Any]] = [
        {
            "date": str(row.day),
            "avg_rating": round(float(row.avg_rating), 2) if row.avg_rating else 0,
            "count": row.count,
        }
        for row in daily_rows
    ]

    # ── Improvement trend ──
    # Compare average rating in the first half vs second half of the period
    midpoint = cutoff + timedelta(days=days // 2)

    first_half_avg = db.query(func.avg(FeedbackEntry.rating)).filter(
        FeedbackEntry.created_at >= cutoff,
        FeedbackEntry.created_at < midpoint,
    ).scalar()

    second_half_avg = db.query(func.avg(FeedbackEntry.rating)).filter(
        FeedbackEntry.created_at >= midpoint,
    ).scalar()

    improvement = None
    if first_half_avg is not None and second_half_avg is not None:
        improvement = round(float(second_half_avg) - float(first_half_avg), 2)

    return {
        "total_feedback": total,
        "average_rating": round(float(avg_rating), 2) if avg_rating is not None else None,
        "rating_distribution": rating_distribution,
        "daily_trend": daily_trend,
        "improvement_trend": improvement,
        "period_days": days,
    }


# ---------------------------------------------------------------------------
# GET /corrections
# ---------------------------------------------------------------------------
@router.get(
    "/corrections",
    response_model=list[FeedbackCorrectionResponse],
    summary="Get recent corrections (low-rated feedback)",
)
def get_corrections(
    limit: int = Query(20, ge=1, le=100, description="Max entries to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return recent low-rated feedback entries (rating <= 2) that include
    corrected content. These represent corrections the user made to
    AI-generated test cases and are used to improve the learning loop.
    """
    entries = (
        db.query(FeedbackEntry)
        .filter(
            FeedbackEntry.rating <= 2,
            FeedbackEntry.corrected_content.isnot(None),
        )
        .order_by(FeedbackEntry.created_at.desc())
        .limit(limit)
        .all()
    )

    return [FeedbackCorrectionResponse.model_validate(e) for e in entries]
