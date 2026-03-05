#!/usr/bin/env bash
# =============================================================================
# QAForge — MCP Post-Deploy Verification
# =============================================================================
# Verifies all MCP proxy routing, container health, and connectivity.
# Run after vm-deploy.sh or full-deploy.sh to confirm everything works.
#
# Usage:
#   cd /opt/qaforge && bash scripts/verify-mcp.sh
#
# Exit code = number of failures (0 = all passed)
# =============================================================================

set -uo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

log()  { echo -e "  ${GREEN}PASS${NC}  $*"; PASS=$((PASS + 1)); }
err()  { echo -e "  ${RED}FAIL${NC}  $*"; FAIL=$((FAIL + 1)); }
warn() { echo -e "  ${YELLOW}WARN${NC}  $*"; WARN=$((WARN + 1)); }
step() { echo -e "\n${CYAN}[$1]${NC} $2"; }

DEPLOY_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── 1. Container Health ─────────────────────────────────────────────────────
step "1/6" "Container health"

QAFORGE_CONTAINERS="qaforge_db qaforge_redis qaforge_chromadb qaforge_backend qaforge_frontend qaforge_mcp"
for name in $QAFORGE_CONTAINERS; do
    status=$(docker inspect --format='{{.State.Status}}' "$name" 2>/dev/null || echo "missing")
    health=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$name" 2>/dev/null || echo "n/a")
    if [[ "$status" == "running" ]]; then
        log "$name: running ($health)"
    else
        err "$name: $status"
    fi
done

# Reltio MCP is optional
if docker inspect reltio_mcp_server >/dev/null 2>&1; then
    status=$(docker inspect --format='{{.State.Status}}' "reltio_mcp_server" 2>/dev/null || echo "missing")
    if [[ "$status" == "running" ]]; then
        log "reltio_mcp_server: running"
    else
        err "reltio_mcp_server: $status"
    fi
else
    warn "reltio_mcp_server: not found (optional)"
fi

# ── 2. Backend Health ────────────────────────────────────────────────────────
step "2/6" "Backend health endpoint"

health_response=$(curl -sk --max-time 5 https://localhost:8080/api/health 2>/dev/null || echo "")
if echo "$health_response" | grep -q '"status"'; then
    log "Backend /api/health: OK"
else
    # Try direct port
    health_response=$(curl -s --max-time 5 http://localhost:8000/health 2>/dev/null || echo "")
    if echo "$health_response" | grep -q '"status"'; then
        log "Backend health: OK (direct port)"
        warn "Backend not reachable via nginx — check frontend container"
    else
        err "Backend health: unreachable"
    fi
fi

# ── 3. QAForge MCP SSE Path ─────────────────────────────────────────────────
step "3/6" "QAForge MCP SSE path verification"

# Try via nginx first, fall back to direct port
sse_response=""
for attempt in 1 2 3; do
    sse_response=$(curl -sk -N --max-time 3 https://localhost:8080/qaforge-mcp/sse 2>&1 || true)
    if [[ -n "$sse_response" ]]; then break; fi
    sleep 2
done

if echo "$sse_response" | grep -q '/qaforge-mcp/messages/'; then
    log "QAForge MCP: path prefix correct (/qaforge-mcp/messages/)"
elif echo "$sse_response" | grep -q '/messages/'; then
    err "QAForge MCP: path prefix MISSING — SSE shows /messages/ instead of /qaforge-mcp/messages/"
    echo -e "       ${YELLOW}Fix: Set FASTMCP_MOUNT_PATH=/qaforge-mcp in docker-compose.yml${NC}"
elif [[ -z "$sse_response" ]]; then
    err "QAForge MCP: no SSE response — server may be down"
else
    err "QAForge MCP: unexpected response: $(echo "$sse_response" | head -2)"
fi

# ── 4. Reltio MCP SSE Path ──────────────────────────────────────────────────
step "4/6" "Reltio MCP SSE path verification"

if docker inspect reltio_mcp_server >/dev/null 2>&1; then
    sse_response=""
    for attempt in 1 2 3; do
        sse_response=$(curl -sk -N --max-time 3 https://localhost:8080/mcp/sse 2>&1 || true)
        if [[ -n "$sse_response" ]]; then break; fi
        sleep 2
    done

    if echo "$sse_response" | grep -q '/mcp/messages/'; then
        log "Reltio MCP: sub_filter rewrite correct (/mcp/messages/)"
    elif echo "$sse_response" | grep -q '/messages/'; then
        err "Reltio MCP: sub_filter NOT working — SSE shows /messages/ instead of /mcp/messages/"
        echo -e "       ${YELLOW}Fix: Check nginx.conf /mcp/ location has sub_filter directive${NC}"
    elif [[ -z "$sse_response" ]]; then
        err "Reltio MCP: no SSE response — check container and docker network"
    else
        err "Reltio MCP: unexpected response: $(echo "$sse_response" | head -2)"
    fi
else
    warn "Reltio MCP: skipped (container not found)"
fi

# ── 5. Agent Key Verification ────────────────────────────────────────────────
step "5/6" "QAForge MCP agent key"

AGENT_KEY=""
if [[ -f "$DEPLOY_DIR/.env" ]]; then
    AGENT_KEY=$(grep -E '^QAFORGE_MCP_AGENT_KEY=' "$DEPLOY_DIR/.env" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
fi

if [[ -z "$AGENT_KEY" ]]; then
    warn "QAFORGE_MCP_AGENT_KEY not set in .env — MCP tools won't authenticate"
    echo -e "       ${YELLOW}Fix: Generate key in UI (Projects > Agent API Key) and add to .env${NC}"
else
    # Test with actual API call
    api_response=$(curl -sk --max-time 5 -o /dev/null -w "%{http_code}" \
        https://localhost:8080/api/agent/summary \
        -H "X-Agent-Key: $AGENT_KEY" 2>/dev/null || echo "000")
    if [[ "$api_response" == "200" ]]; then
        log "Agent key: valid (API returned 200)"
    elif [[ "$api_response" == "401" ]]; then
        err "Agent key: invalid or expired (API returned 401)"
        echo -e "       ${YELLOW}Fix: Regenerate in QAForge UI and update .env${NC}"
    else
        warn "Agent key: could not verify (API returned $api_response)"
    fi
fi

# ── 6. Docker Network ────────────────────────────────────────────────────────
step "6/6" "Docker network connectivity"

if docker inspect reltio_mcp_server >/dev/null 2>&1; then
    network_containers=$(docker network inspect qaforge_default --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null || echo "")
    if echo "$network_containers" | grep -q "reltio_mcp_server"; then
        log "Reltio MCP: connected to qaforge_default network"
    else
        err "Reltio MCP: NOT on qaforge_default network — nginx cannot proxy"
        echo -e "       ${YELLOW}Fix: docker network connect qaforge_default reltio_mcp_server${NC}"
    fi
else
    warn "Docker network check: skipped (Reltio not deployed)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${GREEN}$PASS passed${NC}  ${RED}$FAIL failed${NC}  ${YELLOW}$WARN warnings${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [[ $FAIL -eq 0 ]]; then
    echo -e "\n  ${GREEN}All MCP verifications passed.${NC}\n"
else
    echo -e "\n  ${RED}$FAIL verification(s) failed. See details above.${NC}\n"
fi

exit $FAIL
