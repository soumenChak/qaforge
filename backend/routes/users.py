"""
QAForge -- User management routes.

Prefix: /api/users

Endpoints:
    GET    /me              — current user profile
    GET    /                — list all users (admin only)
    PUT    /{id}            — update user (admin, or self)
    DELETE /{id}            — deactivate user (admin only, cannot delete self)
    POST   /me/change-password — change own password
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from db_models import User
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    require_roles,
    sanitize_string,
)
from models import (
    ChangePasswordRequest,
    MessageResponse,
    UserResponse,
    UserUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List all users (admin only)",
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Return all users in the system. Requires admin role."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]


# ---------------------------------------------------------------------------
# PUT /{id}
# ---------------------------------------------------------------------------
@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user (admin, or self for name only)",
)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a user's profile.

    - Admins can update any user's name, roles, and is_active status.
    - Non-admin users can only update their own name.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    is_admin = "admin" in (current_user.roles or [])
    is_self = current_user.id == user_id

    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile",
        )

    # Non-admins can only change their name
    if not is_admin:
        if body.roles is not None or body.is_active is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change roles or active status",
            )

    if body.name is not None:
        user.name = sanitize_string(body.name) or body.name

    if body.roles is not None and is_admin:
        user.roles = body.roles

    if body.is_active is not None and is_admin:
        user.is_active = body.is_active

    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="update_user",
        entity_type="user",
        entity_id=str(user.id),
        details=body.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )

    logger.info("User updated: %s by %s", user.email, current_user.email)

    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# DELETE /{id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Deactivate a user (admin only)",
)
def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """
    Deactivate (soft-delete) a user account. Requires admin role.

    Admins cannot deactivate themselves.
    """
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_active = False
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="deactivate_user",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email},
        ip_address=get_client_ip(request),
    )

    logger.info("User deactivated: %s by %s", user.email, current_user.email)

    return MessageResponse(message=f"User '{user.email}' has been deactivated")


# ---------------------------------------------------------------------------
# POST /me/change-password
# ---------------------------------------------------------------------------
@router.post(
    "/me/change-password",
    response_model=MessageResponse,
    summary="Change own password",
)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Change the current user's password.

    Requires the current password for verification.
    """
    if not pwd_context.verify(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = pwd_context.hash(body.new_password)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="change_password",
        entity_type="user",
        entity_id=str(current_user.id),
        ip_address=get_client_ip(request),
    )

    logger.info("Password changed for user: %s", current_user.email)

    return MessageResponse(message="Password changed successfully")
