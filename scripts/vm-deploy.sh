#!/usr/bin/env bash
# =============================================================================
# QAForge — On-VM Deploy Script
# =============================================================================
# Runs on the VM after code is updated. Builds containers, runs migrations,
# and verifies all services are healthy.
#
# Usage (on the VM):
#   cd /opt/qaforge && bash scripts/vm-deploy.sh
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[QAForge]${NC} $*"; }
warn() { echo -e "${YELLOW}[QAForge]${NC} $*"; }
fail() { echo -e "${RED}[QAForge]${NC} $*" >&2; exit 1; }
step() { echo -e "${CYAN}[QAForge]${NC} ── $* ──"; }

DEPLOY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DEPLOY_DIR"

# ── Preflight ────────────────────────────────────────────────────────────────
step "Preflight checks"

[[ -f ".env" ]] || {
    warn ".env not found — copying from .env.example"
    cp .env.example .env
    warn "IMPORTANT: Edit .env with real secrets before production use!"
}

command -v docker >/dev/null || fail "docker not found"
docker compose version >/dev/null 2>&1 || fail "docker compose not available"

# ── Build ────────────────────────────────────────────────────────────────────
step "Building containers"
docker compose build --parallel

# ── Start Services ───────────────────────────────────────────────────────────
step "Starting services"
docker compose up -d

# ── Wait for DB ──────────────────────────────────────────────────────────────
step "Waiting for database to be ready"
MAX_WAIT=60
WAITED=0
until docker compose exec -T db pg_isready -U qaforge -d qaforge >/dev/null 2>&1; do
    if [[ $WAITED -ge $MAX_WAIT ]]; then
        fail "Database did not become ready within ${MAX_WAIT}s"
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done
log "Database ready (${WAITED}s)"

# ── Run Alembic Migrations ───────────────────────────────────────────────────
step "Running database migrations"
docker compose exec -T backend sh -c "cd /app && alembic upgrade head" || {
    warn "Alembic migration failed — this may be expected on first run."
    warn "If this is a fresh install, migrations will run on next deploy."
}

# ── Health Checks ────────────────────────────────────────────────────────────
step "Verifying container health"

check_health() {
    local service="$1"
    local max_attempts=20
    local attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' "qaforge_${service}" 2>/dev/null || echo "missing")

        case "$status" in
            healthy)
                log "  $service: ${GREEN}healthy${NC}"
                return 0
                ;;
            unhealthy)
                fail "  $service: ${RED}unhealthy${NC}"
                ;;
            *)
                sleep 3
                attempt=$((attempt + 1))
                ;;
        esac
    done

    warn "  $service: health check timed out (status: $status)"
    return 1
}

HEALTHY=true
for svc in db redis chromadb backend frontend mcp; do
    check_health "$svc" || HEALTHY=false
done

# ── QAForge MCP Path Check ──────────────────────────────────────────────────
step "Verifying QAForge MCP SSE path"
MCP_SSE=$(curl -s -N --max-time 3 http://localhost:${MCP_PORT:-8090}/qaforge-mcp/sse 2>&1 || true)
if echo "$MCP_SSE" | grep -q '/qaforge-mcp/messages/'; then
    log "QAForge MCP path prefix: ${GREEN}correct${NC}"
elif echo "$MCP_SSE" | grep -q '/messages/'; then
    warn "QAForge MCP path prefix missing — check FASTMCP_MOUNT_PATH env var"
else
    warn "QAForge MCP SSE not responding on direct port — will verify after nginx starts"
fi

# ── Final Status ─────────────────────────────────────────────────────────────
step "Deployment status"
echo ""
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""

if $HEALTHY; then
    log "All services healthy. QAForge is ready!"
    log "Frontend: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${FRONTEND_PORT:-8090}"
else
    warn "Some services may not be fully healthy yet. Check logs with:"
    warn "  docker compose logs -f <service>"
fi
