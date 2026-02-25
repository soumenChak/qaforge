"""
QAForge -- Authentication routes.

Prefix: /api/auth

Endpoints:
    POST /login    — email + password -> JWT token
    POST /register — admin-only user registration
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from db_models import User
from db_session import get_db
from dependencies import (
    audit_log,
    create_access_token,
    get_client_ip,
    get_current_user,
    require_roles,
    sanitize_string,
)
from models import LoginRequest, TokenResponse, UserCreate, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email and password",
    status_code=status.HTTP_200_OK,
)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Validate email/password credentials and return a JWT access token.

    Returns 401 if credentials are invalid or user account is deactivated.
    """
    user = db.query(User).filter(User.email == body.email).first()

    if user is None or not pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        roles=user.roles,
    )

    audit_log(
        db,
        user_id=user.id,
        action="login",
        entity_type="user",
        entity_id=str(user.id),
        ip_address=get_client_ip(request),
    )

    logger.info("User logged in: %s", user.email)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=UserResponse,
    summary="Register a new user (admin only)",
    status_code=status.HTTP_201_CREATED,
)
def register(
    body: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """
    Create a new user account. Requires admin role.

    Returns 409 if email is already registered.
    """
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{body.email}' already exists",
        )

    user = User(
        email=body.email,
        name=sanitize_string(body.name) or body.name,
        password_hash=pwd_context.hash(body.password),
        roles=body.roles,
        is_active=True,
    )
    db.add(user)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="register_user",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email, "roles": user.roles},
        ip_address=get_client_ip(request),
    )

    logger.info("User registered by %s: %s", current_user.email, user.email)

    return UserResponse.model_validate(user)
