"""
QAForge -- FastAPI application entry point.

Features:
- CORS middleware (all origins in dev, configurable allowlist in prod)
- Rate limiting with slowapi (200/min general, 20/min AI endpoints)
- Auto-creation of tables on startup
- Admin user seeding (admin@freshgravity.com / admin123)
- Health endpoints: /health AND /api/health
- Auto-discovery of route modules from routes/
- SECRET_KEY strength check on startup
- Request logging middleware
"""

import importlib
import logging
import os
import pkgutil
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.orm import Session

from db_models import Base, User
from db_session import SessionLocal, engine

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("qaforge")

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
)


# ---------------------------------------------------------------------------
# SECRET_KEY strength check
# ---------------------------------------------------------------------------
def _check_secret_key() -> None:
    """Warn loudly if the SECRET_KEY is weak or unchanged from the default."""
    secret = os.environ.get("SECRET_KEY", "change-me-in-production")
    weak_values = {
        "change-me-in-production",
        "secret",
        "changeme",
        "password",
        "test",
        "",
    }
    if secret in weak_values or len(secret) < 32:
        logger.warning(
            "SECRET_KEY is weak or unchanged from default. "
            "Generate a strong key: python3 -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    else:
        logger.info("SECRET_KEY strength check passed (length=%d)", len(secret))


# ---------------------------------------------------------------------------
# Admin seed
# ---------------------------------------------------------------------------
def _seed_admin_user(db: Session) -> None:
    """Create the default admin user if it doesn't already exist."""
    admin_email = "admin@freshgravity.com"
    existing = db.query(User).filter(User.email == admin_email).first()
    if existing:
        logger.info("Admin user already exists: %s", admin_email)
        return

    admin = User(
        id=uuid.uuid4(),
        email=admin_email,
        name="QAForge Admin",
        password_hash=pwd_context.hash("admin123"),
        roles=["admin"],
        is_active=True,
    )
    db.add(admin)
    db.commit()
    logger.info("Seeded default admin user: %s", admin_email)


# ---------------------------------------------------------------------------
# Startup / shutdown (lifespan)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: run startup tasks, yield, then cleanup."""
    # ── Startup ──
    _check_secret_key()

    logger.info("Creating database tables (if not exist)...")
    Base.metadata.create_all(bind=engine)

    # Create performance indexes (idempotent)
    with engine.begin() as conn:
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS ix_test_cases_status ON test_cases(status)",
            "CREATE INDEX IF NOT EXISTS ix_test_cases_execution_type ON test_cases(execution_type)",
            "CREATE INDEX IF NOT EXISTS ix_execution_results_status ON execution_results(status)",
            "CREATE INDEX IF NOT EXISTS ix_projects_domain ON projects(domain)",
            "CREATE INDEX IF NOT EXISTS ix_projects_status ON projects(status)",
        ]:
            conn.execute(text(idx_sql))
    logger.info("Database tables and indexes ready.")

    db = SessionLocal()
    try:
        _seed_admin_user(db)
    except Exception:
        logger.error("Failed to seed admin user", exc_info=True)
    finally:
        db.close()

    logger.info("QAForge backend started successfully.")

    yield

    # ── Shutdown ──
    logger.info("QAForge backend shutting down.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="QAForge API",
    description="Intelligent QA Test Case Generator Platform for FreshGravity",
    version="0.1.0",
    lifespan=lifespan,
)

# Attach limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Agent-Key"],
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    """Log every request with method, path, status code, and duration."""
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    # Skip noisy health-check logs
    path = request.url.path
    if path not in ("/health", "/api/health"):
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            path,
            response.status_code,
            duration_ms,
        )

    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
    return response


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health():
    """Basic health check for Docker / load balancer."""
    return {"status": "ok", "service": "qaforge-backend"}


@app.get("/api/health", tags=["health"])
async def api_health():
    """Health check behind the /api prefix (nginx reverse proxy)."""
    return {"status": "ok", "service": "qaforge-backend", "api": True}


# ---------------------------------------------------------------------------
# Auto-discover and include route modules
# ---------------------------------------------------------------------------
def _register_routes() -> None:
    """
    Import every module in the ``routes`` package that exposes an
    ``APIRouter`` named ``router``, and include it in the app.
    """
    import routes as routes_pkg

    package_path = routes_pkg.__path__
    prefix_map = {
        "auth": "/api/auth",
        "users": "/api/users",
        "projects": "/api/projects",
        "requirements": "/api/projects",
        "test_cases": "/api/projects",
        "templates": "/api/templates",
        "knowledge": "/api/knowledge",
        "feedback": "/api/feedback",
        "settings": "/api/settings",
        "agent_api": "/api/agent",
        "test_plans": "/api/projects",
        "reviews": "/api/reviews",
    }

    for importer, module_name, is_pkg in pkgutil.iter_modules(package_path):
        if module_name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"routes.{module_name}")
            router = getattr(module, "router", None)
            if router is None:
                logger.debug("Skipping routes.%s (no 'router' attribute)", module_name)
                continue

            prefix = prefix_map.get(module_name, f"/api/{module_name}")
            tag = module_name.replace("_", " ").title()
            app.include_router(router, prefix=prefix, tags=[tag])
            logger.info("Registered route module: routes.%s -> %s", module_name, prefix)
        except Exception:
            logger.error("Failed to load route module: routes.%s", module_name, exc_info=True)


_register_routes()
