"""
QAForge -- Connection profile management routes.

Prefix: /api/connections

Endpoints:
    POST   /             — create connection
    GET    /             — list connections
    GET    /{id}         — get connection detail
    PUT    /{id}         — update connection
    DELETE /{id}         — delete connection
    POST   /{id}/test    — test connection health
"""

import ipaddress
import logging
import uuid
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from db_models import Connection, User
from db_session import get_db
from dependencies import audit_log, get_client_ip, get_current_user, sanitize_string
from models import (
    ConnectionCreate,
    ConnectionResponse,
    ConnectionTestResponse,
    ConnectionUpdate,
    MessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=ConnectionResponse,
    summary="Create a connection profile",
    status_code=status.HTTP_201_CREATED,
)
def create_connection(
    body: ConnectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = Connection(
        name=sanitize_string(body.name) or body.name,
        type=body.type,
        driver=body.driver,
        config=body.config,
        credentials_ref=body.credentials_ref,
        created_by=current_user.id,
    )
    db.add(conn)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="create_connection",
        entity_type="connection",
        entity_id=str(conn.id),
        details={"name": conn.name, "type": conn.type, "driver": conn.driver},
        ip_address=get_client_ip(request),
    )

    logger.info("Connection created: %s by %s", conn.name, current_user.email)
    return ConnectionResponse.model_validate(conn)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=list[ConnectionResponse],
    summary="List connection profiles",
)
def list_connections(
    conn_type: str | None = Query(None, alias="type"),
    driver: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Connection)
    if conn_type:
        query = query.filter(Connection.type == conn_type)
    if driver:
        query = query.filter(Connection.driver == driver)
    connections = query.order_by(Connection.created_at.desc()).all()
    return [ConnectionResponse.model_validate(c) for c in connections]


# ---------------------------------------------------------------------------
# GET /{id}
# ---------------------------------------------------------------------------
@router.get(
    "/{conn_id}",
    response_model=ConnectionResponse,
    summary="Get connection detail",
)
def get_connection(
    conn_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = db.query(Connection).filter(Connection.id == conn_id).first()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return ConnectionResponse.model_validate(conn)


# ---------------------------------------------------------------------------
# PUT /{id}
# ---------------------------------------------------------------------------
@router.put(
    "/{conn_id}",
    response_model=ConnectionResponse,
    summary="Update a connection",
)
def update_connection(
    conn_id: uuid.UUID,
    body: ConnectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = db.query(Connection).filter(Connection.id == conn_id).first()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    if body.name is not None:
        conn.name = sanitize_string(body.name) or body.name
    if body.config is not None:
        conn.config = body.config
    if body.credentials_ref is not None:
        conn.credentials_ref = body.credentials_ref
    if body.status is not None:
        conn.status = body.status

    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="update_connection",
        entity_type="connection",
        entity_id=str(conn.id),
        details=body.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )

    return ConnectionResponse.model_validate(conn)


# ---------------------------------------------------------------------------
# DELETE /{id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{conn_id}",
    response_model=MessageResponse,
    summary="Delete a connection",
)
def delete_connection(
    conn_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = db.query(Connection).filter(Connection.id == conn_id).first()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    name = conn.name
    db.delete(conn)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_connection",
        entity_type="connection",
        entity_id=str(conn_id),
        details={"name": name},
        ip_address=get_client_ip(request),
    )

    return MessageResponse(message=f"Connection '{name}' deleted")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_safe_url(url: str) -> bool:
    """Check that a URL is not targeting localhost or private IPs (SSRF prevention)."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        try:
            ip = ipaddress.ip_address(hostname)
            return not ip.is_private and not ip.is_loopback
        except ValueError:
            return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# POST /{id}/test
# ---------------------------------------------------------------------------
@router.post(
    "/{conn_id}/test",
    response_model=ConnectionTestResponse,
    summary="Test connection health",
)
async def test_connection(
    conn_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = db.query(Connection).filter(Connection.id == conn_id).first()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    config = conn.config or {}

    if conn.type == "api" and conn.driver == "http":
        base_url = config.get("base_url", "")
        if not base_url:
            return ConnectionTestResponse(
                success=False, message="No base_url configured"
            )
        if not _is_safe_url(base_url):
            return ConnectionTestResponse(
                success=False, message="URL targets a private/internal network (blocked)"
            )
        try:
            async with httpx.AsyncClient(verify=False, timeout=10, follow_redirects=True) as client:
                resp = await client.get(base_url)
                latency = resp.elapsed.total_seconds() * 1000
                conn.status = "connected"
                from datetime import datetime, timezone
                conn.last_tested_at = datetime.now(timezone.utc)
                db.flush()
                return ConnectionTestResponse(
                    success=resp.status_code < 500,
                    message=f"HTTP {resp.status_code}",
                    latency_ms=round(latency, 1),
                )
        except httpx.ConnectError as e:
            conn.status = "error"
            db.flush()
            return ConnectionTestResponse(success=False, message=f"Connection failed: {e}")
        except httpx.TimeoutException:
            conn.status = "error"
            db.flush()
            return ConnectionTestResponse(success=False, message="Timeout")
    elif conn.type == "database":
        db_url = config.get("db_url", "")
        if not db_url:
            return ConnectionTestResponse(success=False, message="No db_url configured")
        if not _is_safe_url(db_url):
            return ConnectionTestResponse(
                success=False, message="DB URL targets a private/internal network (blocked)"
            )
        try:
            from sqlalchemy import create_engine, text as sa_text
            import time as _time
            engine = create_engine(db_url, connect_args={"connect_timeout": 10})
            start = _time.perf_counter()
            with engine.connect() as conn_db:
                conn_db.execute(sa_text("SELECT 1"))
            latency = (_time.perf_counter() - start) * 1000
            conn.status = "connected"
            from datetime import datetime, timezone
            conn.last_tested_at = datetime.now(timezone.utc)
            db.flush()
            return ConnectionTestResponse(
                success=True,
                message="Database connection successful",
                latency_ms=round(latency, 1),
            )
        except Exception as e:
            conn.status = "error"
            db.flush()
            return ConnectionTestResponse(success=False, message=f"Database error: {e}")

    elif conn.type == "browser":
        app_url = config.get("app_url", "")
        if not app_url:
            return ConnectionTestResponse(success=False, message="No app_url configured")
        if not _is_safe_url(app_url):
            return ConnectionTestResponse(
                success=False, message="URL targets a private/internal network (blocked)"
            )
        try:
            async with httpx.AsyncClient(verify=False, timeout=10, follow_redirects=True) as client:
                resp = await client.get(app_url)
                latency = resp.elapsed.total_seconds() * 1000
                conn.status = "connected"
                from datetime import datetime, timezone
                conn.last_tested_at = datetime.now(timezone.utc)
                db.flush()
                return ConnectionTestResponse(
                    success=resp.status_code < 500,
                    message=f"App reachable (HTTP {resp.status_code})",
                    latency_ms=round(latency, 1),
                )
        except httpx.ConnectError as e:
            conn.status = "error"
            db.flush()
            return ConnectionTestResponse(success=False, message=f"Connection failed: {e}")
        except httpx.TimeoutException:
            conn.status = "error"
            db.flush()
            return ConnectionTestResponse(success=False, message="Timeout")

    else:
        return ConnectionTestResponse(
            success=False,
            message=f"Testing not implemented for {conn.type}/{conn.driver}",
        )
