"""
QAForge -- Shared FastAPI dependencies.

Provides:
- get_db()          — request-scoped database session
- get_current_user() — JWT extraction + validation
- require_roles()   — RBAC role enforcement
- audit_log()       — writes to the audit_log table
- sanitize_string() — strips dangerous HTML tags/event handlers
- track_cost()      — writes to the cost_tracking table

JWT config reads SECRET_KEY from env; algorithm HS256; 24-hour expiry.
"""

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from db_models import AuditLog, CostTracking, Project, User
from db_session import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT configuration
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-me-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS: int = 24

_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------
def create_access_token(
    user_id: uuid.UUID,
    email: str,
    roles: List[str],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        user_id: The user's UUID (stored as ``sub``).
        email: Stored in the ``email`` claim.
        roles: Stored in the ``roles`` claim.
        expires_delta: Custom expiry; defaults to ACCESS_TOKEN_EXPIRE_HOURS.

    Returns:
        Encoded JWT string.
    """
    if expires_delta is None:
        expires_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "roles": roles,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises:
        HTTPException 401 on invalid / expired tokens.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# get_current_user dependency
# ---------------------------------------------------------------------------
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate the JWT from the Authorization header, then return
    the corresponding active User record.

    Raises:
        HTTPException 401 if token missing/invalid or user not found.
        HTTPException 403 if user account is deactivated.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


# ---------------------------------------------------------------------------
# require_roles -- RBAC decorator
# ---------------------------------------------------------------------------
def require_roles(*allowed_roles: str) -> Callable:
    """
    Return a FastAPI dependency that enforces role-based access.

    Usage::

        @router.post("/admin-action")
        def admin_only(
            user: User = Depends(require_roles("admin")),
        ):
            ...

    Allowed role values: ``admin``, ``lead``, ``tester``.
    """

    async def _role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_roles = set(current_user.roles or [])
        required = set(allowed_roles)
        if not user_roles & required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {sorted(required)}. You have: {sorted(user_roles)}",
            )
        return current_user

    return _role_checker


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------
def audit_log(
    db: Session,
    user_id: Optional[uuid.UUID],
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    Write an entry to the audit_log table.

    This is a fire-and-forget helper -- errors are logged but never raised
    to avoid breaking the primary request flow.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(entry)
        db.flush()  # flush so the ID is assigned; commit happens at request end
    except Exception:
        logger.error("Failed to write audit log entry", exc_info=True)


def get_client_ip(request: Request) -> Optional[str]:
    """
    Extract the real client IP from the request, respecting X-Forwarded-For
    when behind a reverse proxy.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ---------------------------------------------------------------------------
# Agent API key authentication
# ---------------------------------------------------------------------------
async def get_agent_project(
    request: Request,
    db: Session = Depends(get_db),
) -> Project:
    """
    Validate the X-Agent-Key header and return the matching project.

    This is the auth mechanism for the agent API — no JWT needed.
    The API key is SHA-256 hashed and matched against
    ``project.agent_api_key_hash``.

    Raises:
        HTTPException 401 if key missing or invalid.
    """
    api_key = request.headers.get("X-Agent-Key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Agent-Key header",
        )

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    project = (
        db.query(Project)
        .filter(Project.agent_api_key_hash == key_hash)
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent API key",
        )
    return project


# ---------------------------------------------------------------------------
# Input sanitisation
# ---------------------------------------------------------------------------
# Patterns that match dangerous HTML -- script tags, event handlers, iframes, etc.
_DANGEROUS_PATTERNS: List[re.Pattern] = [
    re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*script[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*/\s*script\s*>", re.IGNORECASE),
    re.compile(r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*iframe[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*object[^>]*>.*?<\s*/\s*object\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*embed[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*link[^>]*>", re.IGNORECASE),
    re.compile(r"\bon\w+\s*=\s*[\"'][^\"']*[\"']", re.IGNORECASE),
    re.compile(r"\bon\w+\s*=\s*\S+", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
]


def sanitize_string(value: Optional[str]) -> Optional[str]:
    """
    Strip dangerous HTML tags and event handlers from a string.

    This does NOT use ``html.escape()`` to avoid double-encoding issues
    (e.g. ``&`` becoming ``&amp;``). Instead it strips known-dangerous
    patterns while preserving safe content.

    Args:
        value: The input string (may be None).

    Returns:
        Sanitised string, or None if input was None.
    """
    if value is None:
        return None

    result = value
    for pattern in _DANGEROUS_PATTERNS:
        result = pattern.sub("", result)

    # Strip any remaining HTML tags as a final safety net
    result = re.sub(r"<[^>]+>", "", result)

    return result.strip()


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------
def track_cost(
    db: Session,
    user_id: Optional[uuid.UUID],
    project_id: Optional[uuid.UUID],
    operation_type: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    compute_units: float = 0.0,
    cost: float = 0.0,
) -> None:
    """
    Write an entry to the cost_tracking table.

    Fire-and-forget -- errors are logged but never raised.

    Args:
        db: Active database session.
        user_id: Who triggered the operation.
        project_id: Optional project scope.
        operation_type: One of ``llm``, ``snowflake``, ``databricks``, ``api``.
        provider: LLM provider name (e.g. ``anthropic``).
        model: Model identifier (e.g. ``claude-sonnet-4-20250514``).
        tokens_in: Input tokens consumed.
        tokens_out: Output tokens produced.
        compute_units: Non-LLM compute units (e.g. Snowflake credits).
        cost: Estimated cost in USD.
    """
    try:
        entry = CostTracking(
            user_id=user_id,
            project_id=project_id,
            operation_type=operation_type,
            provider=provider,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            compute_units=compute_units,
            estimated_cost_usd=cost,
        )
        db.add(entry)
        db.flush()
    except Exception:
        logger.error("Failed to write cost tracking entry", exc_info=True)
