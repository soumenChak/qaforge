# Fresh VM Deployment — Complete Setup Guide

**Deploy QAForge + MCP servers on a brand-new Ubuntu VM in ~35 minutes.**

This is the single guide for a complete first-time deployment. For ongoing operations, see [RUNBOOK.md](RUNBOOK.md). For MCP architecture details, see [MCP_OPERATIONS_GUIDE.md](MCP_OPERATIONS_GUIDE.md).

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **VM** | Ubuntu 22.04+, 4 GB RAM, 20 GB disk |
| **Docker** | 24+ with Docker Compose v2 |
| **Ports** | 8080 (HTTPS), 8090 (QAForge MCP direct), 8002 (Reltio MCP direct), 5434 (PostgreSQL), 6381 (Redis) |
| **LLM key** | At least one: Anthropic, OpenAI, or Groq |
| **Reltio creds** | CLIENT_ID, CLIENT_SECRET, TENANT, AUTH_SERVER (only if deploying Reltio MCP) |
| **SSH access** | Key-based SSH to the VM |

---

## Phase 1: System Preparation (~5 min)

```bash
# SSH into the VM
ssh -i ~/Desktop/your-key.pem ubuntu@YOUR_VM_IP

# Install Docker (if not already installed)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group to take effect

# Verify
docker --version        # Should be 24+
docker compose version  # Should be v2+
```

---

## Phase 2: QAForge Core (~10 min)

### 2.1 Clone and Configure

```bash
cd /opt
git clone git@bitbucket.org:lifio/qaforge.git
cd qaforge

# Create environment file
cp .env.example .env
```

Edit `.env` — set these at minimum:

```bash
# REQUIRED: Generate a strong secret
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

# REQUIRED: At least one LLM API key
ANTHROPIC_API_KEY=sk-ant-...
# or GROQ_API_KEY=gsk_...

# RECOMMENDED: Change default DB password
DB_PASSWORD=your-secure-password
```

### 2.2 SSL Certificates

```bash
mkdir -p certs

# Option A: Self-signed (development/testing)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=qaforge.local"

# Option B: Let's Encrypt (production — requires DNS pointing to this VM)
# See RUNBOOK.md Section 4 for certbot setup
```

### 2.3 Build and Start

```bash
docker compose up -d --build

# Wait for all 6 containers to show "healthy" (~60 seconds)
watch -n 5 'docker compose ps'
# Ctrl+C when all show "Up (healthy)"
```

### 2.4 Run Migrations

```bash
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

### 2.5 Verify

```bash
# Backend health
curl -k https://localhost:8080/api/health
# Expected: {"status": "ok", ...}

# QAForge MCP SSE
curl -sk -N --max-time 3 https://localhost:8080/qaforge-mcp/sse
# Expected: event: endpoint
#           data: /qaforge-mcp/messages/?session_id=...
# IMPORTANT: The path MUST include /qaforge-mcp/ prefix!
```

---

## Phase 3: Agent Key Configuration (~5 min)

The QAForge MCP server needs an agent key to call the backend API.

### 3.1 Create Project in UI

1. Open `https://YOUR_VM_IP:8080` in browser (accept self-signed cert warning)
2. Login: `admin@freshgravity.com` / `admin123`
3. **Projects** > **New Project** > fill name, domain > **Create**
4. On the project page: **Agent API Key** > **Generate**
5. **Copy the key immediately** (format: `qf_...`, shown only once)

### 3.2 Configure MCP Server

```bash
cd /opt/qaforge

# Add the key to .env
echo 'QAFORGE_MCP_AGENT_KEY=qf_YOUR_KEY_HERE' >> .env

# Restart MCP server to pick up the key
docker compose up -d qaforge_mcp

# Verify key works
curl -sk https://localhost:8080/api/agent/summary \
  -H "X-Agent-Key: qf_YOUR_KEY_HERE"
# Expected: {"project_name": "...", "test_cases": {...}, ...}
```

---

## Phase 4: Reltio MCP Server (Optional, ~10 min)

Skip this phase if you don't need Reltio MDM tools.

### 4.1 Clone and Configure

```bash
cd /opt
git clone https://github.com/reltio-ai/reltio-mcp-server.git
cd reltio-mcp-server

# Create .env with Reltio credentials
cat > .env << 'EOF'
RELTIO_SERVER_NAME=FGServer
RELTIO_ENVIRONMENT=dev
RELTIO_CLIENT_ID=YOUR_CLIENT_ID
RELTIO_CLIENT_SECRET='YOUR_SECRET_HERE'
RELTIO_TENANT=YOUR_TENANT_ID
RELTIO_AUTH_SERVER=https://auth.reltio.com
EOF
```

> **WARNING:** If `RELTIO_CLIENT_SECRET` contains `$` characters, you **must** wrap the value in single quotes. Otherwise Docker interprets `$` as shell variable interpolation and strips part of the secret.

### 4.2 Change Port Mapping

The default port (8000) conflicts with QAForge MCP. Change to 8002:

```bash
# Edit docker-compose.yaml — change ports from "8000:8000" to "8002:8000"
sed -i 's/"8000:8000"/"8002:8000"/' docker-compose.yaml
```

### 4.3 Build, Start, and Connect Network

```bash
# Build and start
docker compose up -d --build

# CRITICAL: Connect to QAForge Docker network for nginx proxy
docker network connect qaforge_default reltio_mcp_server
```

> **NOTE:** You must re-run `docker network connect` after every restart or recreate of the Reltio MCP container.

### 4.4 Verify

```bash
# Test SSE endpoint (via nginx proxy)
curl -sk -N --max-time 3 https://localhost:8080/mcp/sse
# Expected: event: endpoint
#           data: /mcp/messages/?session_id=...
# IMPORTANT: Path MUST include /mcp/ prefix (nginx sub_filter rewrite)
```

---

## Phase 5: Post-Deploy Verification (~5 min)

Run the verification script from the QAForge directory:

```bash
cd /opt/qaforge
bash scripts/verify-mcp.sh
```

**Expected output (all green):**

```
[1/6] Container health
  PASS  qaforge_db: running (healthy)
  PASS  qaforge_redis: running (healthy)
  PASS  qaforge_chromadb: running (healthy)
  PASS  qaforge_backend: running (healthy)
  PASS  qaforge_frontend: running (healthy)
  PASS  qaforge_mcp: running (healthy)
  PASS  reltio_mcp_server: running

[2/6] Backend health endpoint
  PASS  Backend /api/health: OK

[3/6] QAForge MCP SSE path verification
  PASS  QAForge MCP: path prefix correct (/qaforge-mcp/messages/)

[4/6] Reltio MCP SSE path verification
  PASS  Reltio MCP: sub_filter rewrite correct (/mcp/messages/)

[5/6] QAForge MCP agent key
  PASS  Agent key: valid (API returned 200)

[6/6] Docker network connectivity
  PASS  Reltio MCP: connected to qaforge_default network

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  7 passed  0 failed  0 warnings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If any checks fail, the script shows the fix command.

---

## Phase 6: Security Hardening

- [ ] **Change admin password:** Login to UI > profile settings > change from `admin123`
- [ ] **Firewall:** Only expose port 8080 externally. Block 5434, 6381, 8001, 8090, 8002
- [ ] **CORS:** Set `CORS_ORIGINS=https://your-domain.com` in `.env` (not `*`)
- [ ] **SSL:** Switch from self-signed to Let's Encrypt (see [RUNBOOK.md Section 4](RUNBOOK.md#4-ssl-certificates))
- [ ] **Agent keys:** Rotate periodically via QAForge UI

---

## Quick Commands After Deployment

| Task | Command |
|------|---------|
| **Full redeploy** | `cd /opt/qaforge && git pull && bash scripts/full-deploy.sh` |
| **QAForge only** | `cd /opt/qaforge && git pull && bash scripts/vm-deploy.sh` |
| **Quick restart** | `bash scripts/full-deploy.sh --skip-build` |
| **Verify MCP** | `bash scripts/verify-mcp.sh` |
| **Check status** | `docker ps --format 'table {{.Names}}\t{{.Status}}'` |
| **View logs** | `docker logs qaforge_backend --tail 30` |
| **DB shell** | `docker exec -it qaforge_db psql -U qaforge` |
| **Reltio restart** | `cd /opt/reltio-mcp-server && docker compose restart && docker network connect qaforge_default reltio_mcp_server` |

---

## Connecting Claude Code / Codex

After deployment, AI tools connect to the MCP servers like this:

```bash
# QAForge MCP (16 test management tools)
claude mcp add qaforge "https://YOUR_VM_IP:8080/qaforge-mcp/sse" --transport sse

# Reltio MCP (45 MDM tools, optional)
claude mcp add reltio "https://YOUR_VM_IP:8080/mcp/sse" --transport sse

# Start Claude Code
mkdir -p ~/qa-workspace && cd ~/qa-workspace && claude
```

For self-signed certs, clients may need `NODE_TLS_REJECT_UNAUTHORIZED=0` (or use the direct HTTP ports `8090` / `8002` instead of HTTPS).

See [MCP_OPERATIONS_GUIDE.md Section 7](MCP_OPERATIONS_GUIDE.md#7-claude-code--qa-user-setup-step-by-step) for detailed Claude Code setup.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| MCP returns 405 on POST | SSE path missing prefix | Check `FASTMCP_MOUNT_PATH` in docker-compose.yml |
| Reltio MCP 502 | Not on QAForge network | `docker network connect qaforge_default reltio_mcp_server` |
| Agent tools return 401 | Key not set or expired | Regenerate in QAForge UI, update `.env`, restart `qaforge_mcp` |
| Frontend blank page | Missing SSL certs | Check `ls certs/` has `cert.pem` and `key.pem` |
| Database errors | Migrations not run | `docker compose exec backend sh -c "cd /app && alembic upgrade head"` |

For more: [RUNBOOK.md Section 10](RUNBOOK.md#10-troubleshooting) | [MCP_OPERATIONS_GUIDE.md Section 13](MCP_OPERATIONS_GUIDE.md#13-troubleshooting)
