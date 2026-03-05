#!/usr/bin/env bash
# =============================================================================
# QAForge — Full Stack Deploy (QAForge + Reltio MCP)
# =============================================================================
# Orchestrates deployment of the complete stack:
#   1. QAForge core (6 containers) via vm-deploy.sh
#   2. Reltio MCP server (separate compose, optional)
#   3. Docker network connect for Reltio → QAForge
#   4. MCP proxy verification via verify-mcp.sh
#
# Usage:
#   cd /opt/qaforge && bash scripts/full-deploy.sh
#
# Options:
#   --qaforge-only    Skip Reltio MCP deployment
#   --skip-build      Restart services without rebuilding images
#   --skip-verify     Skip post-deploy verification
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[FullDeploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[FullDeploy]${NC} $*"; }
fail() { echo -e "${RED}[FullDeploy]${NC} $*" >&2; exit 1; }
step() { echo -e "\n${CYAN}[FullDeploy]${NC} ━━ $* ━━"; }

DEPLOY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RELTIO_DIR="/opt/reltio-mcp-server"
QAFORGE_ONLY=false
SKIP_BUILD=false
SKIP_VERIFY=false

# Parse flags
for arg in "$@"; do
    case "$arg" in
        --qaforge-only) QAFORGE_ONLY=true ;;
        --skip-build)   SKIP_BUILD=true ;;
        --skip-verify)  SKIP_VERIFY=true ;;
        --help|-h)
            echo "Usage: bash scripts/full-deploy.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --qaforge-only    Skip Reltio MCP deployment"
            echo "  --skip-build      Restart without rebuilding images"
            echo "  --skip-verify     Skip post-deploy verification"
            exit 0
            ;;
        *) warn "Unknown flag: $arg (ignored)" ;;
    esac
done

cd "$DEPLOY_DIR"

# ── Phase 1: QAForge Core ───────────────────────────────────────────────────
step "Phase 1: QAForge Core (vm-deploy.sh)"

if [[ "$SKIP_BUILD" == "true" ]]; then
    log "Restarting QAForge services (skip-build mode)"
    docker compose up -d
    docker compose exec -T backend sh -c "cd /app && alembic upgrade head" 2>/dev/null || true
else
    bash scripts/vm-deploy.sh
fi

# ── Phase 2: Reltio MCP Server ──────────────────────────────────────────────
if [[ "$QAFORGE_ONLY" == "true" ]]; then
    log "Skipping Reltio MCP (--qaforge-only)"
elif [[ ! -d "$RELTIO_DIR" ]]; then
    warn "Reltio MCP directory not found at $RELTIO_DIR — skipping"
    warn "To deploy Reltio MCP, clone the repo there first."
else
    step "Phase 2: Reltio MCP Server"

    cd "$RELTIO_DIR"

    if [[ ! -f ".env" ]]; then
        warn "Reltio MCP .env not found — skipping (create .env with Reltio credentials)"
    else
        if [[ "$SKIP_BUILD" == "true" ]]; then
            log "Restarting Reltio MCP (skip-build mode)"
            docker compose up -d
        else
            log "Building and starting Reltio MCP server"
            docker compose up -d --build
        fi

        # Wait for container to start
        local_wait=0
        while [[ $local_wait -lt 30 ]]; do
            status=$(docker inspect --format='{{.State.Status}}' reltio_mcp_server 2>/dev/null || echo "missing")
            if [[ "$status" == "running" ]]; then
                log "Reltio MCP container: running"
                break
            fi
            sleep 2
            local_wait=$((local_wait + 2))
        done

        # Connect to QAForge Docker network (idempotent)
        log "Connecting Reltio MCP to qaforge_default network"
        docker network connect qaforge_default reltio_mcp_server 2>/dev/null || true
    fi

    cd "$DEPLOY_DIR"
fi

# ── Phase 3: Verify ─────────────────────────────────────────────────────────
if [[ "$SKIP_VERIFY" == "true" ]]; then
    log "Skipping verification (--skip-verify)"
else
    step "Phase 3: MCP Verification"
    bash scripts/verify-mcp.sh || {
        warn "Some verifications failed — see details above"
    }
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
log "Full deploy complete."
log "QAForge UI: https://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${FRONTEND_PORT:-8080}"
