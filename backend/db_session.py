"""
QAForge -- Database session factory.

Provides the SQLAlchemy engine, session factory, and FastAPI dependency
for request-scoped database sessions.

Configuration:
    DATABASE_URL  env var (default: postgresql://qaforge:qaforge_pass@db:5432/qaforge)
"""

import os
import logging
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://qaforge:qaforge_pass@db:5432/qaforge",
)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,           # reconnect stale connections automatically
    pool_recycle=1800,             # recycle connections every 30 min
    echo=os.environ.get("SQL_ECHO", "").lower() == "true",
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Connection-level event: set statement timeout to 30s (safety net)
# ---------------------------------------------------------------------------
@event.listens_for(engine, "connect")
def _set_pg_statement_timeout(dbapi_conn, connection_record):
    """Set a 30-second statement timeout on each new connection."""
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("SET statement_timeout = '30s'")
        cursor.close()
    except Exception:  # noqa: BLE001 – best-effort; don't block startup
        pass


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """
    Yield a request-scoped SQLAlchemy session.

    Usage::

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...

    The session is committed on success and rolled back on exception,
    then closed in either case.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
