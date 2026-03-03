"""
QAForge -- Review aggregation routes.

Prefix: /api/reviews

Endpoints:
    GET /pending — aggregated pending reviews across projects
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db_models import ExecutionResult, Project, TestCase, User
from db_session import get_db
from dependencies import get_current_user, is_admin

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/pending")
def get_pending_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all pending reviews across the user's projects.
    Admin sees all; engineer sees only assigned projects.
    """
    # Build project filter
    if is_admin(current_user):
        project_ids = [p.id for p in db.query(Project.id).filter(Project.status == "active").all()]
    else:
        # Engineer: projects where assigned_users contains their ID or they created
        all_projects = db.query(Project).filter(Project.status == "active").all()
        uid_str = str(current_user.id)
        project_ids = [
            p.id for p in all_projects
            if p.created_by == current_user.id
            or (p.assigned_users and uid_str in [str(u) for u in p.assigned_users])
        ]

    # Pending test cases (status=draft)
    pending_tcs = (
        db.query(TestCase)
        .filter(
            TestCase.project_id.in_(project_ids),
            TestCase.status == "draft",
        )
        .order_by(TestCase.created_at.desc())
        .limit(100)
        .all()
    )

    # Pending execution reviews (review_status is NULL)
    pending_execs = (
        db.query(ExecutionResult)
        .filter(
            ExecutionResult.test_case_id.in_(
                db.query(TestCase.id).filter(TestCase.project_id.in_(project_ids))
            ),
            ExecutionResult.review_status.is_(None),
        )
        .order_by(ExecutionResult.executed_at.desc())
        .limit(100)
        .all()
    )

    # Build response with project names
    project_map = {p.id: p for p in db.query(Project).filter(Project.id.in_(project_ids)).all()}

    tc_items = []
    for tc in pending_tcs:
        proj = project_map.get(tc.project_id)
        tc_items.append({
            "id": str(tc.id),
            "project_id": str(tc.project_id),
            "project_name": proj.name if proj else "Unknown",
            "test_case_id": tc.test_case_id,
            "title": tc.title,
            "priority": tc.priority,
            "category": tc.category,
            "source": tc.source,
            "execution_type": tc.execution_type,
            "created_at": tc.created_at.isoformat() if tc.created_at else None,
        })

    exec_items = []
    for er in pending_execs:
        tc = db.query(TestCase).filter(TestCase.id == er.test_case_id).first()
        proj = project_map.get(tc.project_id) if tc else None
        exec_items.append({
            "id": str(er.id),
            "project_id": str(tc.project_id) if tc else None,
            "project_name": proj.name if proj else "Unknown",
            "test_case_id": tc.test_case_id if tc else None,
            "test_case_title": tc.title if tc else None,
            "status": er.status,
            "actual_result": er.actual_result,
            "duration_ms": er.duration_ms,
            "executed_by": er.executed_by,
            "executed_at": er.executed_at.isoformat() if er.executed_at else None,
            "proof_count": len(er.proof_artifacts) if er.proof_artifacts else 0,
        })

    return {
        "test_cases": tc_items,
        "executions": exec_items,
        "counts": {
            "tc_pending": len(tc_items),
            "exec_pending": len(exec_items),
        },
    }
