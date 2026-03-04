# QAForge MCP Platform — Operations Guide

**Complete setup, deployment, and connection guide for QAForge MCP + Reltio MCP + Claude Code.**
**Last updated: 2026-03-04**

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Two User Personas](#2-two-user-personas)
3. [Server Inventory](#3-server-inventory)
4. [QAForge — Setup & Deploy (From Scratch)](#4-qaforge--setup--deploy-from-scratch)
5. [QAForge MCP Server — Overview & Tools](#5-qaforge-mcp-server--overview--tools)
6. [Reltio MCP Server — Setup & Deploy](#6-reltio-mcp-server--setup--deploy)
7. [Claude Code — QA User Setup (Step-by-Step)](#7-claude-code--qa-user-setup-step-by-step)
8. [Claude Code — Developer Setup](#8-claude-code--developer-setup)
9. [Daily Operations — Start / Stop / Restart](#9-daily-operations--start--stop--restart)
10. [Environment Variables Reference](#10-environment-variables-reference)
11. [Database Operations](#11-database-operations)
12. [Updating & Redeployment](#12-updating--redeployment)
13. [Troubleshooting](#13-troubleshooting)
14. [Key IDs & URLs](#14-key-ids--urls)

---

## 1. Architecture Overview

```
  ┌────────────────────┐              ┌────────────────────┐
  │   QA User          │              │   Developer        │
  │   (Claude Code)    │              │   (Claude Code)    │
  │   No codebase      │              │   Full codebase    │
  └─────────┬──────────┘              └─────────┬──────────┘
            │ SSE (MCP protocol)                │ SSE + Git + local tools
            │                                    │
  ┌─────────▼────────────────────────────────────▼─────────┐
  │                  Nginx (HTTPS :8080)                     │
  │                                                          │
  │   /qaforge-mcp/*  →  QAForge MCP Server (17 tools)      │
  │   /mcp/*          →  Reltio MCP Server  (45 tools)      │
  │   /api/*          →  QAForge Backend    (REST API)      │
  │   /*              →  React SPA          (Web UI)        │
  └───┬──────────────────┬──────────────────┬───────────────┘
      │                  │                  │
  ┌───▼──────────┐ ┌────▼────────┐  ┌──────▼──────┐
  │ QAForge MCP  │ │ QAForge     │  │ Reltio MCP  │
  │ Server       │ │ Backend     │  │ Server      │
  │ (FastMCP)    │ │ (FastAPI)   │  │ (FastMCP)   │
  │ 17 tools     │ │ 11 routes   │  │ 45 tools    │
  │ Port 8000    │ │ Port 8000   │  │ Port 8000   │
  │ ─────────────│ │             │  │ ────────────│
  │ Calls Agent  │─►             │  │ Calls Reltio│
  │ API via httpx│ │             │  │ API via HTTP│
  └──────────────┘ └──┬──┬──┬───┘  └──────┬──────┘
                      │  │  │              │
              ┌───────┘  │  └───────┐      │
              │          │          │      │
         ┌────▼──┐  ┌───▼──┐  ┌───▼────┐ ┌▼──────────┐
         │Postgre│  │Redis │  │ChromaDB│ │Reltio API │
         │SQL 16 │  │  7   │  │ 0.4    │ │(cloud)    │
         │:5434  │  │:6381 │  │:8001   │ └───────────┘
         └───────┘  └──────┘  └────────┘
```

### Docker Containers (VM: 13.233.36.18)

| Container | Image | Internal Port | External Port | Purpose |
|-----------|-------|:---:|:---:|---------|
| `qaforge_frontend` | qaforge-frontend (nginx) | 443 | **8080** | HTTPS proxy + React SPA |
| `qaforge_backend` | qaforge-backend (FastAPI) | 8000 | *internal* | REST API + execution engine |
| `qaforge_mcp` | qaforge-qaforge_mcp (FastMCP) | 8000 | **8090** | QAForge MCP Server (17 tools, SSE) |
| `qaforge_db` | postgres:16-alpine | 5432 | 5434 | Primary data store |
| `qaforge_redis` | redis:7-alpine | 6379 | 6381 | Rate limiting, caching |
| `qaforge_chromadb` | chromadb/chroma:0.4.24 | 8000 | 8001 | Vector embeddings (RAG KB) |
| `reltio_mcp_server` | reltio-mcp-server | 8000 | 8002 | Reltio MCP Server (45 tools, SSE) |

**Network:** All QAForge containers share `qaforge_default`. The Reltio MCP server runs in its own compose but is connected to `qaforge_default` via `docker network connect`.

---

## 2. Two User Personas

QAForge supports two distinct user types with different levels of access:

### QA User (Test Management Only)

- **Access:** Claude Code + QAForge MCP + Reltio MCP (remote, via SSE)
- **Cannot:** Modify QAForge code, add features, access Git repos
- **Can:** List/generate/submit test cases, create test plans, submit results, manage KB, view summaries
- **Setup:** 3 commands in terminal (see [Section 7](#7-claude-code--qa-user-setup-step-by-step))

### Developer (Full Access)

- **Access:** Claude Code + QAForge MCP + Reltio MCP + Git repo + local tools
- **Can:** Everything QA users can + modify QAForge code, add features, fix bugs, deploy
- **Setup:** Clone repo + add MCP servers (see [Section 8](#8-claude-code--developer-setup))

---

## 3. Server Inventory

| Item | Value |
|------|-------|
| **VM IP** | 13.233.36.18 |
| **SSH key** | `~/Desktop/innovation-lab.pem` |
| **SSH command** | `ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18` |
| **QAForge code (VM)** | `/opt/qaforge` |
| **MCP server code (VM)** | `/opt/reltio-mcp-server` (Reltio), inside `/opt/qaforge/mcp-server` (QAForge) |
| **QAForge code (local)** | `/Users/soumenc/Downloads/qaforge` |
| **QAForge UI** | `https://13.233.36.18:8080` |
| **QAForge API** | `https://13.233.36.18:8080/api/` |
| **QAForge MCP (HTTPS)** | `https://13.233.36.18:8080/qaforge-mcp/sse` |
| **Reltio MCP (HTTPS)** | `https://13.233.36.18:8080/mcp/sse` |
| **QAForge MCP (direct)** | `http://13.233.36.18:8090/sse` |
| **Reltio MCP (direct)** | `http://13.233.36.18:8002/sse` |
| **Git remote** | `git@bitbucket.org:lifio/qaforge.git` |
| **Admin login** | `admin@freshgravity.com` / `admin123` |

---

## 4. QAForge — Setup & Deploy (From Scratch)

### 4.1 Prerequisites

- Ubuntu VM with Docker 24+ and Docker Compose v2
- 4 GB RAM minimum (8 GB recommended)
- 20 GB disk
- At least one LLM API key (Anthropic, OpenAI, or Groq)
- Ports available: 8080, 8090, 5434, 6381, 8001

### 4.2 Clone & Configure

```bash
# SSH into the VM
ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18

# Clone the repo
cd /opt
git clone git@bitbucket.org:lifio/qaforge.git
cd qaforge

# Create env file
cp .env.example .env
# Edit .env — set at minimum:
#   SECRET_KEY=<random 64-char string>
#   ANTHROPIC_API_KEY=sk-ant-...  (or GROQ_API_KEY)
#   DB_PASSWORD=qaforge_pass
```

### 4.3 Generate SSL Certificates

```bash
mkdir -p certs

# Option A: Self-signed (dev/testing)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=qaforge.local"

# Option B: Let's Encrypt (production)
# See RUNBOOK.md for certbot setup
```

### 4.4 Build & Start All Services

```bash
docker compose up -d --build

# Wait for all 6 containers to become healthy (~60 seconds)
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Expected output:
```
NAMES               STATUS                    PORTS
qaforge_mcp         Up (healthy)              0.0.0.0:8090->8000/tcp
qaforge_backend     Up (healthy)              8000/tcp
qaforge_frontend    Up (healthy)              0.0.0.0:8080->443/tcp
qaforge_db          Up (healthy)              0.0.0.0:5434->5432/tcp
qaforge_redis       Up (healthy)              0.0.0.0:6381->6379/tcp
qaforge_chromadb    Up (healthy)              0.0.0.0:8001->8000/tcp
```

### 4.5 Run Database Migrations

```bash
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

### 4.6 Verify QAForge Is Running

```bash
# Backend health
curl -k https://localhost:8080/api/health

# QAForge MCP SSE endpoint
curl -sk -N --max-time 3 https://localhost:8080/qaforge-mcp/sse
# Should return: event: endpoint\ndata: /messages/?session_id=...

# Login test
curl -sk -X POST https://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@freshgravity.com","password":"admin123"}'
```

### 4.7 Create a Project & Generate Agent Key

1. Open `https://YOUR_VM_IP:8080` in browser
2. Login: `admin@freshgravity.com` / `admin123`
3. **Projects** > **New Project** > fill name, domain, description > **Create**
4. On the project page: **Agent API Key** > **Generate**
5. **Copy the key immediately** (shown only once) — format: `qf_...`

### 4.8 Configure MCP Server Agent Key

The QAForge MCP server needs the agent key to call the backend API:

```bash
# On VM — edit .env to add the agent key
cd /opt/qaforge
# Add this line:
echo 'QAFORGE_MCP_AGENT_KEY=qf_YOUR_KEY_HERE' >> .env

# Restart MCP server to pick up the key
docker compose up -d qaforge_mcp
```

---

## 5. QAForge MCP Server — Overview & Tools

The QAForge MCP Server (`mcp-server/`) exposes QAForge operations as MCP tools over SSE transport. Any Claude Code instance can connect remotely and use these tools without needing the QAForge codebase.

### How It Works

```
Claude Code ──SSE──> QAForge MCP Server ──httpx──> QAForge Backend API
                     (mcp-server/)                  (/api/agent/*)
                     FastMCP + 17 tools             X-Agent-Key auth
```

The MCP server is a thin wrapper — each tool calls the corresponding Agent API endpoint.

### 17 Available Tools

| # | Tool | Description | Agent API Endpoint |
|---|------|-------------|-------------------|
| | **Project** | | |
| 1 | `get_project` | Get project metadata, app profile, domain | `GET /agent/project` |
| 2 | `update_project` | Update description or BRD/PRD text | `PUT /agent/project` |
| | **Requirements** | | |
| 3 | `list_requirements` | List all requirements | `GET /agent/requirements` |
| 4 | `extract_requirements` | AI-extract requirements from BRD text | `POST /agent/requirements/extract` |
| 5 | `submit_requirements` | Submit structured requirements | `POST /agent/requirements` |
| | **Test Cases** | | |
| 6 | `list_test_cases` | List test cases (filter by status/plan) | `GET /agent/test-cases` |
| 7 | `generate_test_cases` | AI-generate from requirements + KB | `POST /agent/generate-from-brd` |
| 8 | `submit_test_cases` | Submit structured test cases | `POST /agent/test-cases` |
| | **Test Plans** | | |
| 9 | `list_test_plans` | List plans with execution stats | `GET /agent/test-plans` |
| 10 | `create_test_plan` | Create a new test plan | `POST /agent/test-plans` |
| 11 | `get_plan_test_cases` | Get test cases in a plan | `GET /agent/test-plans/{id}/test-cases` |
| | **Executions** | | |
| 12 | `submit_results` | Submit execution results with proof | `POST /agent/executions` |
| 13 | `add_proof` | Add proof artifact to execution | `POST /agent/executions/{id}/proof` |
| | **Knowledge Base** | | |
| 14 | `kb_stats` | Get KB statistics by domain | `GET /agent/kb-stats` |
| 15 | `upload_reference` | Upload reference samples to KB | `POST /agent/upload-reference` |
| | **Summary** | | |
| 16 | `get_summary` | Project quality summary and stats | `GET /agent/summary` |
| 17 | `get_coverage` | Coverage analysis | `GET /agent/coverage` |

### MCP Server Configuration

The server reads these environment variables (set in `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `QAFORGE_SERVER_NAME` | `QAForge` | MCP server display name |
| `QAFORGE_API_URL` | `http://backend:8000` | Backend API URL (Docker internal) |
| `QAFORGE_AGENT_KEY` | *(empty)* | Agent API key for the target project |

---

## 6. Reltio MCP Server — Setup & Deploy

### 6.1 First-Time Setup

```bash
ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18

# Clone or copy MCP server code
cd /opt
git clone <reltio-mcp-server-repo-url> reltio-mcp-server
cd reltio-mcp-server
```

### 6.2 Configure Reltio Credentials

```bash
cat > .env << 'EOF'
RELTIO_SERVER_NAME=FGServer
RELTIO_ENVIRONMENT=dev
RELTIO_CLIENT_ID=FG_CLIENT
RELTIO_CLIENT_SECRET='3mS1af$UJsPFVEd?#DfG5abMauu81q7j'
RELTIO_TENANT=lKF8afvLiCCRsS6
RELTIO_AUTH_SERVER=https://auth.reltio.com
EOF
```

> **CRITICAL:** If `RELTIO_CLIENT_SECRET` contains `$`, wrap the value in **single quotes**. Otherwise Docker strips `$VAR` as shell interpolation.

### 6.3 Build & Start

```bash
docker compose up -d --build

# Connect to QAForge network (required for Nginx proxy)
docker network connect qaforge_default reltio_mcp_server
```

### 6.4 Verify

```bash
# Check it's running
docker logs reltio_mcp_server --tail 5

# Test SSE endpoint
curl -sk -N --max-time 3 https://localhost:8080/mcp/sse
# Should return: event: endpoint\ndata: /messages/?session_id=...
```

---

## 7. Claude Code — QA User Setup (Step-by-Step)

This is for **QA users who don't need the QAForge codebase**. They connect Claude Code to remote MCP servers and use natural language to manage tests.

### Prerequisites

- macOS, Linux, or Windows with Node.js 18+
- An Anthropic API key (for Claude Code itself)

### Step 1: Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

### Step 2: Add QAForge MCP Server

```bash
claude mcp add qaforge --transport sse \
  --url "https://13.233.36.18:8080/qaforge-mcp/sse"
```

This gives Claude Code access to 17 QAForge tools: test case management, AI generation, execution results, KB, and summaries.

### Step 3: Add Reltio MCP Server (Optional)

```bash
claude mcp add reltio --transport sse \
  --url "https://13.233.36.18:8080/mcp/sse"
```

This adds 45 Reltio MDM tools: entity search, match, merge, data model, workflows.

### Step 4: Start Claude Code

```bash
# From any directory — no repo needed
mkdir -p ~/qa-workspace && cd ~/qa-workspace
claude
```

### Step 5: Start Working

Talk naturally to Claude:

| What you say | What happens |
|-------------|-------------|
| *"Show me all test cases"* | Calls `list_test_cases` tool |
| *"Generate 10 security test cases"* | Calls `generate_test_cases` tool |
| *"Create a smoke test plan"* | Calls `create_test_plan` tool |
| *"What's our test coverage?"* | Calls `get_summary` tool |
| *"Search Reltio for entities where FirstName is John"* | Calls Reltio `search_entities_tool` |
| *"Upload this BRD and extract requirements"* | Calls `extract_requirements` tool |

### Verify Connection

Inside Claude Code, type:

```
/mcp
```

You should see `qaforge` and `reltio` listed with their tools.

---

## 8. Claude Code — Developer Setup

Developers get **everything QA users have** plus full codebase access.

### Step 1: Clone the Repo

```bash
git clone git@bitbucket.org:lifio/qaforge.git
cd qaforge
```

### Step 2: Add MCP Servers

```bash
# QAForge MCP (test management via MCP)
claude mcp add qaforge --transport sse \
  --url "https://13.233.36.18:8080/qaforge-mcp/sse"

# Reltio MCP (MDM operations via MCP)
claude mcp add reltio --transport sse \
  --url "https://13.233.36.18:8080/mcp/sse"
```

### Step 3: Start Claude Code from the Repo

```bash
cd ~/Downloads/qaforge   # or wherever you cloned
claude
```

Claude Code will read `CLAUDE.md` automatically and have both:
- **MCP tools** — for test management operations
- **Codebase access** — for modifying QAForge code, adding features, fixing bugs

### Developer Workflow Examples

| What you say | What happens |
|-------------|-------------|
| *"Add a new MCP tool for test case duplication"* | Edits code in `mcp-server/src/tools/` |
| *"Generate 5 test cases and submit them"* | Uses MCP tools (no code changes) |
| *"Fix the bug where requirements don't expand"* | Edits frontend code |
| *"Deploy the latest changes to the VM"* | Runs git push + SSH deploy |

---

## 9. Daily Operations — Start / Stop / Restart

### 9.1 SSH to VM

```bash
ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18
```

### 9.2 Start Everything

```bash
# Start QAForge (6 containers including MCP server)
cd /opt/qaforge && docker compose up -d

# Start Reltio MCP server (separate compose)
cd /opt/reltio-mcp-server && docker compose up -d

# Re-connect Reltio MCP to QAForge network (required after recreate)
docker network connect qaforge_default reltio_mcp_server
```

### 9.3 Stop Everything

```bash
cd /opt/qaforge && docker compose down
cd /opt/reltio-mcp-server && docker compose down
```

### 9.4 Restart Individual Services

```bash
# Backend only
cd /opt/qaforge && docker compose restart backend

# QAForge MCP server only
cd /opt/qaforge && docker compose restart qaforge_mcp

# Frontend only
cd /opt/qaforge && docker compose restart frontend

# Reltio MCP server
cd /opt/reltio-mcp-server && docker compose restart reltio_mcp_server
docker network connect qaforge_default reltio_mcp_server
```

### 9.5 Check Status

```bash
# All containers
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# QAForge backend logs
docker logs qaforge_backend --tail 30

# QAForge MCP server logs
docker logs qaforge_mcp --tail 30

# Reltio MCP server logs
docker logs reltio_mcp_server --tail 30

# Health check — backend
curl -k https://localhost:8080/api/health

# Health check — QAForge MCP SSE
curl -sk -N --max-time 3 https://localhost:8080/qaforge-mcp/sse

# Health check — Reltio MCP SSE
curl -sk -N --max-time 3 https://localhost:8080/mcp/sse
```

---

## 10. Environment Variables Reference

### 10.1 QAForge (`/opt/qaforge/.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key (64+ chars) | `<random string>` |
| `DB_PASSWORD` | PostgreSQL password | `qaforge_pass` |
| `DATABASE_URL` | Full DB connection string | `postgresql://qaforge:pass@db:5432/qaforge` |
| `REDIS_URL` | Redis connection | `redis://redis:6379/0` |
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-api03-...` |
| `GROQ_API_KEY` | Groq API key | `gsk_...` |
| `LLM_PROVIDER` | Default LLM | `anthropic` |
| `LLM_MODEL` | Model name | `claude-sonnet-4-20250514` |
| `FRONTEND_PORT` | HTTPS port | `8080` |
| `QAFORGE_BOOTSTRAP_TOKEN` | Agent key bootstrap | `qRIBLa84c3R...` |
| `QAFORGE_MCP_AGENT_KEY` | Agent key for QAForge MCP server | `qf_MAIZ9ep...` |

### 10.2 QAForge MCP Server (in `docker-compose.yml`)

| Variable | Description | Default |
|----------|-------------|---------|
| `QAFORGE_SERVER_NAME` | MCP server display name | `QAForge` |
| `QAFORGE_API_URL` | Backend API URL (Docker internal) | `http://backend:8000` |
| `QAFORGE_AGENT_KEY` | Set from `${QAFORGE_MCP_AGENT_KEY}` | *(from .env)* |

### 10.3 Reltio MCP Server (`/opt/reltio-mcp-server/.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `RELTIO_SERVER_NAME` | MCP server name | `FGServer` |
| `RELTIO_CLIENT_ID` | Reltio OAuth client ID | `FG_CLIENT` |
| `RELTIO_CLIENT_SECRET` | OAuth secret (**single-quote if has `$`**) | `'3mS1af$UJs...'` |
| `RELTIO_TENANT` | Reltio tenant ID | `lKF8afvLiCCRsS6` |
| `RELTIO_AUTH_SERVER` | Reltio auth endpoint | `https://auth.reltio.com` |

---

## 11. Database Operations

### 11.1 Direct SQL Access

```bash
docker exec -it qaforge_db psql -U qaforge -d qaforge
```

### 11.2 Run Migrations

```bash
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

### 11.3 Useful Queries

```sql
-- List all projects with agent key status
SELECT id, name, created_at,
       CASE WHEN agent_api_key_hash IS NOT NULL THEN 'yes' ELSE 'no' END as has_key
FROM projects;

-- List test cases for a project
SELECT id, title, execution_type, status
FROM test_cases WHERE project_id = '<uuid>';

-- Recent execution runs
SELECT id, status, results->'summary' as summary, created_at
FROM execution_runs WHERE project_id = '<uuid>'
ORDER BY created_at DESC LIMIT 5;

-- Check MCP connection config
SELECT id, name, config FROM connections WHERE project_id = '<uuid>';
```

### 11.4 Backup & Restore

```bash
# Backup
docker exec qaforge_db pg_dump -U qaforge qaforge > /opt/qaforge/backup_$(date +%Y%m%d).sql

# Restore
docker exec -i qaforge_db psql -U qaforge -d qaforge < /opt/qaforge/backup_20260304.sql
```

---

## 12. Updating & Redeployment

### 12.1 Standard Deploy (Code Changes)

```bash
# From local machine
cd ~/Downloads/qaforge
git add <files> && git commit -m "description" && git push bitbucket main

# On VM
ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18
cd /opt/qaforge && git pull && bash scripts/vm-deploy.sh
```

### 12.2 MCP Server Only

```bash
cd /opt/qaforge && git pull
docker compose build qaforge_mcp && docker compose up -d qaforge_mcp
docker logs qaforge_mcp --tail 10
```

### 12.3 Backend Only

```bash
cd /opt/qaforge && git pull
docker compose build backend && docker compose up -d backend
```

### 12.4 Frontend Only

```bash
cd /opt/qaforge && git pull
docker compose build frontend && docker compose up -d frontend
```

### 12.5 Full Rebuild (After Dockerfile or requirements changes)

```bash
cd /opt/qaforge && git pull
docker compose build --no-cache && docker compose up -d
```

### 12.6 Reltio MCP Server Update

```bash
cd /opt/reltio-mcp-server
# git pull or scp new code
docker compose down && docker compose up -d --build
docker network connect qaforge_default reltio_mcp_server
```

---

## 13. Troubleshooting

### 13.1 QAForge MCP — 502 Bad Gateway

**Symptom:** `curl https://host:8080/qaforge-mcp/sse` returns 502.

**Check:**
```bash
docker logs qaforge_mcp --tail 20
```

**Common causes:**
- Container crashed (check logs for Python errors)
- Server binding to `127.0.0.1` instead of `0.0.0.0` — verify the `Uvicorn running on` line
- Agent key not set (empty `QAFORGE_AGENT_KEY` env var)

**Fix:**
```bash
docker compose restart qaforge_mcp
docker logs qaforge_mcp --tail 10
# Verify: Uvicorn running on http://0.0.0.0:8000
```

### 13.2 Reltio MCP — Authentication Failed (401)

**Symptom:** MCP tools return `{"error": {"code": 401}}`.

**Check:**
```bash
docker exec reltio_mcp_server python3 -c "
from src.env import RELTIO_CLIENT_ID, RELTIO_CLIENT_SECRET
print(f'ID: {RELTIO_CLIENT_ID}')
print(f'Secret length: {len(RELTIO_CLIENT_SECRET)}')
"
```

**Fix:** If secret is shorter than expected, `$` was interpolated. Wrap in single quotes in `.env` then restart.

### 13.3 Claude Code — MCP Tools Not Showing

**Symptom:** `/mcp` in Claude Code doesn't list qaforge tools.

**Check:**
1. Is the MCP server running? `curl -sk -N --max-time 3 https://13.233.36.18:8080/qaforge-mcp/sse`
2. Was the MCP added correctly? `claude mcp list`

**Fix:**
```bash
claude mcp remove qaforge
claude mcp add qaforge --transport sse \
  --url "https://13.233.36.18:8080/qaforge-mcp/sse"
# Restart Claude Code
```

### 13.4 Backend Cannot Reach Reltio MCP Server

**Symptom:** Execution logs show "Connection refused".

**Fix:**
```bash
docker network inspect qaforge_default --format '{{range .Containers}}{{.Name}} {{end}}'
# If reltio_mcp_server is missing:
docker network connect qaforge_default reltio_mcp_server
```

### 13.5 Agent API Returns 401

**Symptom:** MCP tools fail with "Unauthorized".

**Fix:** Regenerate the key in QAForge UI > Projects > Agent API Key > Regenerate. Then update `.env` and restart:
```bash
sed -i 's/QAFORGE_MCP_AGENT_KEY=.*/QAFORGE_MCP_AGENT_KEY=qf_NEW_KEY/' /opt/qaforge/.env
docker compose restart qaforge_mcp
```

---

## 14. Key IDs & URLs

### Current Projects

| Project | ID |
|---------|-----|
| Abhishek Testing | `8a1ca135-4c1c-4a97-9834-6e86f92e59cd` |
| Reltio MDM E2E Demo | `a8cd771e-07fa-4585-886b-0ff69d655f64` |

### SSE Endpoints

| Endpoint | URL | Tools |
|----------|-----|-------|
| QAForge MCP (via Nginx) | `https://13.233.36.18:8080/qaforge-mcp/sse` | 17 |
| Reltio MCP (via Nginx) | `https://13.233.36.18:8080/mcp/sse` | 45 |
| QAForge MCP (direct) | `http://13.233.36.18:8090/sse` | 17 |
| Reltio MCP (direct) | `http://13.233.36.18:8002/sse` | 45 |

### API Endpoints (Quick Reference)

```
# Auth
POST   /api/auth/login                              # Get JWT token

# Agent API (X-Agent-Key header)
GET    /api/agent/project                            # Project metadata
PUT    /api/agent/project                            # Update project
GET    /api/agent/requirements                       # List requirements
POST   /api/agent/requirements/extract               # AI extract from BRD
POST   /api/agent/requirements                       # Submit requirements
GET    /api/agent/test-cases                         # List test cases
POST   /api/agent/test-cases                         # Submit test cases
POST   /api/agent/generate-from-brd                  # AI generate test cases
GET    /api/agent/test-plans                         # List test plans
POST   /api/agent/test-plans                         # Create test plan
GET    /api/agent/test-plans/{id}/test-cases         # Plan's test cases
POST   /api/agent/executions                         # Submit results
POST   /api/agent/executions/{id}/proof              # Add proof
GET    /api/agent/summary                            # Quality summary
GET    /api/agent/kb-stats                           # KB statistics
POST   /api/agent/upload-reference                   # Upload KB samples
```

---

## Quick Reference Card

```
+─────────────────────────────+──────────────────────────────────────+
│ TASK                        │ COMMAND                              │
+─────────────────────────────+──────────────────────────────────────+
│ SSH to VM                   │ ssh -i ~/Desktop/innovation-lab.pem  │
│                             │   ubuntu@13.233.36.18                │
+─────────────────────────────+──────────────────────────────────────+
│ Start all QAForge           │ cd /opt/qaforge &&                   │
│                             │   docker compose up -d               │
+─────────────────────────────+──────────────────────────────────────+
│ Start Reltio MCP            │ cd /opt/reltio-mcp-server &&         │
│                             │   docker compose up -d &&            │
│                             │   docker network connect             │
│                             │     qaforge_default reltio_mcp_server│
+─────────────────────────────+──────────────────────────────────────+
│ Check containers            │ docker ps --format                   │
│                             │   'table {{.Names}}\t{{.Status}}'    │
+─────────────────────────────+──────────────────────────────────────+
│ Test QAForge MCP            │ curl -sk -N --max-time 3             │
│                             │   https://localhost:8080/             │
│                             │   qaforge-mcp/sse                    │
+─────────────────────────────+──────────────────────────────────────+
│ QA User: add MCP            │ claude mcp add qaforge               │
│                             │   --transport sse                    │
│                             │   --url "https://13.233.36.18:8080/  │
│                             │   qaforge-mcp/sse"                   │
+─────────────────────────────+──────────────────────────────────────+
│ Backend logs                │ docker logs qaforge_backend --tail 30│
+─────────────────────────────+──────────────────────────────────────+
│ MCP logs                    │ docker logs qaforge_mcp --tail 30    │
+─────────────────────────────+──────────────────────────────────────+
│ DB shell                    │ docker exec -it qaforge_db           │
│                             │   psql -U qaforge -d qaforge         │
+─────────────────────────────+──────────────────────────────────────+
│ Deploy                      │ git push && ssh VM                   │
│                             │   'cd /opt/qaforge && git pull &&    │
│                             │   bash scripts/vm-deploy.sh'         │
+─────────────────────────────+──────────────────────────────────────+
│ QAForge UI                  │ https://13.233.36.18:8080            │
│ Login                       │ admin@freshgravity.com / admin123    │
+─────────────────────────────+──────────────────────────────────────+
```
