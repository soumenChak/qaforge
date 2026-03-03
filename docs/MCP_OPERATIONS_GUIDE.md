# QAForge + Reltio MCP Server — Operations Guide

**Complete setup, deployment, restart, and troubleshooting reference.**
**Last updated: 2026-03-03**

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Server Inventory](#2-server-inventory)
3. [QAForge — Setup & Deploy](#3-qaforge--setup--deploy)
4. [Reltio MCP Server — Setup & Deploy](#4-reltio-mcp-server--setup--deploy)
5. [Connecting MCP to QAForge](#5-connecting-mcp-to-qaforge)
6. [MCP Test Execution — How It Works](#6-mcp-test-execution--how-it-works)
7. [Daily Operations — Start / Stop / Restart](#7-daily-operations--start--stop--restart)
8. [Environment Variables Reference](#8-environment-variables-reference)
9. [Database Operations](#9-database-operations)
10. [Updating & Redeployment](#10-updating--redeployment)
11. [Troubleshooting](#11-troubleshooting)
12. [Key IDs & URLs](#12-key-ids--urls)

---

## 1. Architecture Overview

```
                           +---------------------------+
                           |    Browser (User)         |
                           +----------+----------------+
                                      |
                                      | HTTPS :8080
                                      v
                           +----------+----------------+
                           |    Nginx (frontend)       |
                           |    - React SPA            |
                           |    - /api/ -> backend     |
                           |    - /mcp/ -> mcp server  |
                           +----+--+---+---------------+
                                |  |   |
               +----------------+  |   +------------------+
               |                   |                      |
               v                   v                      v
    +----------+-------+  +-------+--------+   +----------+---------+
    | FastAPI Backend   |  | Reltio MCP     |   | Static assets      |
    | - 12 route modules|  | Server         |   | (React build)      |
    | - 11 exec templates  | - 45 MCP tools |   +--------------------+
    | - LLM integration |  | - SSE transport|
    +--+---+---+--------+  +-------+--------+
       |   |   |                    |
       v   v   v                    v
    +--+---+---+--------+   +------+-------+
    | PostgreSQL | Redis |   | Reltio API   |
    | ChromaDB   |       |   | (cloud)      |
    +------------+-------+   +--------------+
```

### Docker Containers (VM: 13.233.36.18)

| Container | Image | Internal Port | External Port | Network |
|-----------|-------|--------------|---------------|---------|
| `qaforge_frontend` | qaforge-frontend | 443 | **8080** | qaforge_default |
| `qaforge_backend` | qaforge-backend | 8000 | (internal only) | qaforge_default |
| `qaforge_db` | postgres:16-alpine | 5432 | 5434 | qaforge_default |
| `qaforge_redis` | redis:7-alpine | 6379 | 6381 | qaforge_default |
| `qaforge_chromadb` | chromadb/chroma:0.4.24 | 8000 | 8001 | qaforge_default |
| `reltio_mcp_server` | reltio-mcp-server | 8000 | 8002 | qaforge_default + its own |

**Key:** The MCP server runs in its own docker-compose but is connected to `qaforge_default` network so the backend can reach it at `http://reltio_mcp_server:8000`.

---

## 2. Server Inventory

| Item | Value |
|------|-------|
| **VM IP** | 13.233.36.18 |
| **SSH key** | `~/Desktop/innovation-lab.pem` |
| **SSH command** | `ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18` |
| **QAForge code (VM)** | `/opt/qaforge` |
| **MCP server code (VM)** | `/opt/reltio-mcp-server` |
| **QAForge code (local)** | `/Users/soumenc/Downloads/qaforge` |
| **MCP server code (local)** | `/Users/soumenc/Downloads/reltio-mcp-server` |
| **QAForge UI** | `https://13.233.36.18:8080` |
| **QAForge API** | `https://13.233.36.18:8080/api/` |
| **MCP via HTTPS** | `https://13.233.36.18:8080/mcp/sse` |
| **MCP direct** | `http://13.233.36.18:8002/sse` |
| **Git remote** | `git@bitbucket.org:lifio/qaforge.git` |
| **Admin login** | `admin@freshgravity.com` / `admin123` |

---

## 3. QAForge — Setup & Deploy

### 3.1 First-Time Setup (New Server)

```bash
# SSH into the VM
ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18

# Clone the repo
cd /opt
git clone git@bitbucket.org:lifio/qaforge.git
cd qaforge

# Create env file
cp .env.example .env
# Edit .env — set SECRET_KEY, ANTHROPIC_API_KEY (or GROQ_API_KEY), DB_PASSWORD

# Generate self-signed SSL certs (or copy Let's Encrypt certs)
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=qaforge.local"

# Build and start all services
docker compose up -d --build

# Wait for health checks to pass (~30-60 seconds)
docker ps   # all should show (healthy)

# Run database migrations
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

### 3.2 Verify QAForge Is Running

```bash
# Check all containers
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# Check backend health
docker exec qaforge_backend python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"

# Check backend logs
docker logs qaforge_backend --tail 20

# Test login (from within backend container)
docker exec qaforge_backend python3 -c "
import httpx
r = httpx.post('http://localhost:8000/api/auth/login', json={'email': 'admin@freshgravity.com', 'password': 'admin123'})
print(f'Status: {r.status_code}')
print(f'Token: {r.json()[\"access_token\"][:30]}...')
"
```

---

## 4. Reltio MCP Server — Setup & Deploy

### 4.1 First-Time Setup

```bash
ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18

# Copy MCP server code to VM (from local machine)
# Option A: Git clone
cd /opt
git clone <reltio-mcp-server-repo-url> reltio-mcp-server

# Option B: Tar + SCP from local (if no git repo)
# On local machine:
cd ~/Downloads
COPYFILE_DISABLE=1 tar czf /tmp/reltio-mcp-server.tar.gz \
  --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
  reltio-mcp-server/
scp -i ~/Desktop/innovation-lab.pem /tmp/reltio-mcp-server.tar.gz ubuntu@13.233.36.18:/tmp/
# On VM:
cd /opt && tar xzf /tmp/reltio-mcp-server.tar.gz
```

### 4.2 Configure Reltio Credentials

```bash
cd /opt/reltio-mcp-server

# Edit .env with proper Reltio credentials
cat > .env << 'EOF'
RELTIO_SERVER_NAME=FGServer
RELTIO_ENVIRONMENT=dev
RELTIO_CLIENT_ID=FG_CLIENT
RELTIO_CLIENT_SECRET='3mS1af$UJsPFVEd?#DfG5abMauu81q7j'
RELTIO_TENANT=lKF8afvLiCCRsS6
RELTIO_AUTH_SERVER=https://auth.reltio.com
EOF
```

> **CRITICAL: Dollar signs in secrets!**
> If the `RELTIO_CLIENT_SECRET` contains `$` characters, you MUST wrap the value
> in **single quotes** in the `.env` file. Otherwise Docker will interpret `$XYZ`
> as a shell variable and strip it out, causing authentication failures.
>
> Wrong: `RELTIO_CLIENT_SECRET=abc$XYZdef`  (Docker reads as `abcdef`)
> Right: `RELTIO_CLIENT_SECRET='abc$XYZdef'` (Docker reads as `abc$XYZdef`)

### 4.3 Modify docker-compose for Port & Entry Point

The default `docker-compose.yaml` uses port 8000, which may conflict. Also, the default `main.py` entry point binds to `127.0.0.1` inside the container. We need to fix both.

```bash
# Edit docker-compose.yaml — change port mapping
cat > docker-compose.yaml << 'EOF'
services:
  reltio_mcp_server:
    container_name: reltio_mcp_server
    build:
      context: ./
      dockerfile: Dockerfile
    ports:
      - 8002:8000
    env_file:
      - .env
    restart: unless-stopped
EOF
```

```bash
# Edit main.py — use uvicorn with 0.0.0.0 binding
cat > main.py << 'PYEOF'
import uvicorn
from dotenv import load_dotenv
load_dotenv()

from src.server import mcp

if __name__ == "__main__":
    app = mcp.sse_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
PYEOF
```

> **Why change main.py?** The default `mcp.run(transport="sse")` binds to 127.0.0.1,
> which is unreachable from outside the container. Using `uvicorn.run()` directly
> lets us bind to `0.0.0.0`.

### 4.4 Build & Start

```bash
cd /opt/reltio-mcp-server
docker compose up -d --build
```

### 4.5 Connect to QAForge Network

The MCP server must be on the same Docker network as QAForge so the backend can reach it by container name:

```bash
docker network connect qaforge_default reltio_mcp_server
```

> **This must be re-run** every time the MCP server container is recreated
> (e.g., after `docker compose down && up`).

### 4.6 Verify MCP Server

```bash
# Check container is running
docker ps | grep reltio_mcp

# Check logs
docker logs reltio_mcp_server --tail 10

# Verify Reltio auth works
docker exec reltio_mcp_server python3 -c "
from src.util.auth import get_access_token
try:
    token = get_access_token()
    print(f'AUTH OK — Token: {token[:30]}...')
except Exception as e:
    print(f'AUTH FAILED: {e}')
"

# Verify MCP tools are accessible from QAForge backend
docker exec qaforge_backend python3 -c "
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client(url='http://reltio_mcp_server:8000/sse') as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            resp = await session.list_tools()
            print(f'Connected! {len(resp.tools)} tools available.')
            for t in resp.tools[:5]:
                print(f'  - {t.name}')
            print(f'  ... and {len(resp.tools)-5} more')

asyncio.run(main())
"
```

---

## 5. Connecting MCP to QAForge

### 5.1 Nginx Proxy (Already Configured)

The QAForge `frontend/nginx.conf` has a `/mcp/` location block that proxies to the MCP server:

```nginx
location /mcp/ {
    proxy_pass http://reltio_mcp_server:8000/;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    chunked_transfer_encoding off;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
}
```

This allows HTTPS access to MCP at `https://13.233.36.18:8080/mcp/sse`.

### 5.2 Project Connection Config

The QAForge project stores the MCP server URL in its connection config. The backend uses this when executing MCP test cases.

**Current config** (stored in `connections` table):
```json
{
  "app_url": "http://reltio_mcp_server:8000/sse",
  "base_url": "http://reltio_mcp_server:8000"
}
```

To update the connection config (if needed):
```bash
docker exec qaforge_db psql -U qaforge -d qaforge -c "
  UPDATE connections
  SET config = '{\"app_url\": \"http://reltio_mcp_server:8000/sse\", \"base_url\": \"http://reltio_mcp_server:8000\"}'::jsonb
  WHERE project_id = 'a8cd771e-07fa-4585-886b-0ff69d655f64';
"
```

### 5.3 Project App Profile

The project's `app_profile` also references the MCP URL. When a new execution is triggered without a connection, QAForge auto-creates one from the app_profile:

```bash
docker exec qaforge_db psql -U qaforge -d qaforge -c "
  SELECT app_profile->'app_url' as app_url
  FROM projects
  WHERE id = 'a8cd771e-07fa-4585-886b-0ff69d655f64';
"
```

---

## 6. MCP Test Execution — How It Works

### 6.1 Flow

```
User clicks "Execute Plan" in UI
        |
        v
POST /api/projects/{pid}/test-plans/{plan_id}/execute
        |
        v
Backend creates ExecutionRun (status=pending)
        |
        v
Background task: engine.py run_execution()
        |
        v
For each test case (execution_type=mcp):
    1. MCP Fast-Path: reads tool_name + tool_params directly from test_steps
       (skips LLM extraction — faster and more reliable)
    2. Template: mcp_tool.py
       a. Connect to MCP server via SSE (mcp.client.sse.sse_client)
       b. Initialize session
       c. list_tools() — verify tool exists
       d. call_tool(tool_name, arguments)
       e. Validate response (fields, content, timing)
    3. Results saved to ExecutionRun.results JSONB
        |
        v
Frontend polls GET /execution-runs/{run_id} every 2s
Shows real-time progress bar + pass/fail counts
```

### 6.2 Test Case Structure (MCP Type)

MCP test cases have `execution_type: mcp` and structured steps:

```json
{
  "execution_type": "mcp",
  "test_steps": [
    {
      "step_number": 1,
      "step_type": "mcp",
      "action": "Call health_check_tool on the MCP server",
      "tool_name": "health_check_tool",
      "tool_params": {},
      "assertions": [
        {"type": "has_field", "value": "status"},
        {"type": "contains", "value": "ok"},
        {"type": "response_time_ms", "value": 5000}
      ],
      "expected_result": "Server returns status ok",
      "connection_ref": "reltio_mcp"
    }
  ]
}
```

**Key fields in each step:**
- `tool_name` — exact MCP tool name (e.g., `health_check_tool`, `search_entities_tool`)
- `tool_params` — arguments passed to the tool (JSON object)
- `assertions` — validation rules:
  - `has_field` — check if field exists in JSON response
  - `contains` — check if string appears in response body
  - `response_time_ms` — max allowed response time

### 6.3 Execution Templates

The engine has 11 templates. MCP uses `mcp_tool`:

| Template | File | Execution Type |
|----------|------|---------------|
| `api_smoke` | templates/api_smoke.py | api |
| `api_crud` | templates/api_crud.py | api |
| `db_query` | templates/db_query.py | sql |
| `db_reconciliation` | templates/db_reconciliation.py | sql |
| `ui_playwright` | templates/ui_playwright.py | ui |
| `mdm_entity` | templates/mdm_entity.py | api |
| `data_quality` | templates/data_quality.py | sql |
| `etl_pipeline` | templates/etl_pipeline.py | sql |
| `llm_evaluation` | templates/llm_evaluation.py | api |
| `agent_workflow` | templates/agent_workflow.py | api |
| **`mcp_tool`** | **templates/mcp_tool.py** | **mcp** |

### 6.4 Current Test Cases (Reltio MCP Smoke Test Plan)

| ID | Title | MCP Tool | Status |
|----|-------|----------|--------|
| `861415bb-...` | MCP Server Health Check | `health_check_tool` | PASSING |
| `011ef6c2-...` | Reltio Entity Search via MCP | `search_entities_tool` | PASSING |
| `aa24c560-...` | Reltio Data Model Definition Retrieval | `get_data_model_definition_tool` | PASSING |

---

## 7. Daily Operations — Start / Stop / Restart

### 7.1 SSH to VM

```bash
ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18
```

### 7.2 Start Everything

```bash
# Start QAForge (5 containers)
cd /opt/qaforge && docker compose up -d

# Start MCP server
cd /opt/reltio-mcp-server && docker compose up -d

# Re-connect MCP to QAForge network (required after MCP container recreate)
docker network connect qaforge_default reltio_mcp_server
```

### 7.3 Stop Everything

```bash
# Stop QAForge
cd /opt/qaforge && docker compose down

# Stop MCP server
cd /opt/reltio-mcp-server && docker compose down
```

### 7.4 Restart Individual Services

```bash
# Restart just the backend (e.g., after code change)
cd /opt/qaforge && docker compose restart backend

# Restart just the frontend
cd /opt/qaforge && docker compose restart frontend

# Restart MCP server
cd /opt/reltio-mcp-server && docker compose restart reltio_mcp_server
# IMPORTANT: re-connect to qaforge network after restart
docker network connect qaforge_default reltio_mcp_server
```

### 7.5 Check Status

```bash
# All containers
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# QAForge backend logs
docker logs qaforge_backend --tail 30

# MCP server logs
docker logs reltio_mcp_server --tail 30

# QAForge backend health
docker exec qaforge_backend python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"

# MCP connectivity test (from backend)
docker exec qaforge_backend python3 -c "
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
async def test():
    async with sse_client(url='http://reltio_mcp_server:8000/sse') as s:
        async with ClientSession(*s) as session:
            await session.initialize()
            r = await session.list_tools()
            print(f'MCP OK: {len(r.tools)} tools')
asyncio.run(test())
"
```

---

## 8. Environment Variables Reference

### 8.1 QAForge (`/opt/qaforge/.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key (64+ chars) | `<random 64-char string>` |
| `DB_PASSWORD` | PostgreSQL password | `qaforge_pass` |
| `DATABASE_URL` | Full DB connection string | `postgresql://qaforge:qaforge_pass@db:5432/qaforge` |
| `REDIS_URL` | Redis connection | `redis://redis:6379/0` |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | `sk-ant-api03-...` |
| `GROQ_API_KEY` | Groq API key (faster, cheaper) | `gsk_...` |
| `LLM_PROVIDER` | Default LLM (`anthropic`, `groq`, `openai`) | `anthropic` |
| `LLM_MODEL` | Specific model name | `claude-sonnet-4-20250514` |
| `FRONTEND_PORT` | HTTPS port for UI | `8080` |
| `DB_PORT` | Exposed PostgreSQL port | `5434` |
| `REDIS_PORT` | Exposed Redis port | `6381` |
| `CHROMADB_PORT` | Exposed ChromaDB port | `8001` |
| `QAFORGE_BOOTSTRAP_TOKEN` | Agent API bootstrap token | `qRIBLa84c3R...` |

### 8.2 Reltio MCP Server (`/opt/reltio-mcp-server/.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `RELTIO_SERVER_NAME` | MCP server display name | `FGServer` |
| `RELTIO_ENVIRONMENT` | Environment label | `dev` |
| `RELTIO_CLIENT_ID` | Reltio OAuth client ID | `FG_CLIENT` |
| `RELTIO_CLIENT_SECRET` | Reltio OAuth secret (**single-quote if has `$`**) | `'3mS1af$UJs...'` |
| `RELTIO_TENANT` | Reltio tenant ID | `lKF8afvLiCCRsS6` |
| `RELTIO_AUTH_SERVER` | Reltio auth endpoint | `https://auth.reltio.com` |

---

## 9. Database Operations

### 9.1 Direct SQL Access

```bash
# From VM
docker exec -it qaforge_db psql -U qaforge -d qaforge

# From local (via exposed port)
psql -h 13.233.36.18 -p 5434 -U qaforge -d qaforge
```

### 9.2 Run Migrations

```bash
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

### 9.3 Useful Queries

```sql
-- List all projects
SELECT id, name, created_at FROM projects;

-- List test cases for a project
SELECT id, title, execution_type, status
FROM test_cases
WHERE project_id = 'a8cd771e-07fa-4585-886b-0ff69d655f64';

-- List execution runs (most recent first)
SELECT id, status, results->'summary' as summary, created_at
FROM execution_runs
WHERE project_id = 'a8cd771e-07fa-4585-886b-0ff69d655f64'
ORDER BY created_at DESC LIMIT 5;

-- Check connection config
SELECT id, name, config FROM connections
WHERE project_id = 'a8cd771e-07fa-4585-886b-0ff69d655f64';

-- Update connection URL (if MCP server moves)
UPDATE connections
SET config = jsonb_set(config, '{app_url}', '"http://reltio_mcp_server:8000/sse"')
WHERE project_id = 'a8cd771e-07fa-4585-886b-0ff69d655f64';
```

### 9.4 Backup & Restore

```bash
# Backup
docker exec qaforge_db pg_dump -U qaforge qaforge > /opt/qaforge/backup_$(date +%Y%m%d).sql

# Restore
docker exec -i qaforge_db psql -U qaforge -d qaforge < /opt/qaforge/backup_20260303.sql
```

---

## 10. Updating & Redeployment

### 10.1 Standard Deploy (Code Changes Only)

```bash
# From local machine — push your changes
cd ~/Downloads/qaforge
git add <files> && git commit -m "description" && git push bitbucket main

# On VM — pull and rebuild
ssh -i ~/Desktop/innovation-lab.pem ubuntu@13.233.36.18
cd /opt/qaforge
git pull

# Backend only (Python changes)
docker compose build backend && docker compose up -d backend

# Frontend only (React changes)
docker compose build frontend && docker compose up -d frontend

# Both
docker compose build && docker compose up -d
```

### 10.2 Full Rebuild (After requirements.txt or Dockerfile Changes)

```bash
cd /opt/qaforge
git pull

# --no-cache forces reinstall of all packages
docker compose build --no-cache backend
docker compose up -d backend

# Verify
docker logs qaforge_backend --tail 10
```

### 10.3 MCP Server Update

```bash
# If code is in git:
cd /opt/reltio-mcp-server && git pull

# If code is transferred via tar:
# (on local) scp tarball to VM, extract to /opt/reltio-mcp-server

# Rebuild and restart
cd /opt/reltio-mcp-server
docker compose down
docker compose up -d --build

# Re-connect to QAForge network
docker network connect qaforge_default reltio_mcp_server

# Verify
docker logs reltio_mcp_server --tail 10
```

---

## 11. Troubleshooting

### 11.1 MCP Server — "Failed to authenticate with Reltio API" (401)

**Symptom:** MCP tools return `{"error": {"code": 401, "code_key": "AUTHENTICATION_ERROR"}}`.
Health check passes but all other tools fail.

**Cause:** Reltio OAuth credentials are wrong or `$` signs in the secret got eaten by shell expansion.

**Fix:**
```bash
# Check what the container actually sees
docker exec reltio_mcp_server python3 -c "
from src.env import RELTIO_CLIENT_ID, RELTIO_CLIENT_SECRET
print(f'ID: {RELTIO_CLIENT_ID}')
print(f'Secret: {RELTIO_CLIENT_SECRET}')
print(f'Length: {len(RELTIO_CLIENT_SECRET)}')
"

# If the secret is shorter than expected, $ was interpolated.
# Fix: wrap in single quotes in .env file
# Wrong:  RELTIO_CLIENT_SECRET=abc$XYZdef
# Right:  RELTIO_CLIENT_SECRET='abc$XYZdef'

# Then restart:
cd /opt/reltio-mcp-server
docker compose down && docker compose up -d
docker network connect qaforge_default reltio_mcp_server
```

### 11.2 Backend Cannot Reach MCP Server

**Symptom:** Execution logs show "Connection refused" or "Name resolution failed".

**Fix:**
```bash
# Check MCP container is running
docker ps | grep reltio

# Check MCP is on the qaforge network
docker network inspect qaforge_default --format '{{range .Containers}}{{.Name}} {{end}}'

# If missing, reconnect:
docker network connect qaforge_default reltio_mcp_server

# Verify connectivity
docker exec qaforge_backend python3 -c "
import httpx
try:
    r = httpx.get('http://reltio_mcp_server:8000/sse', timeout=3)
except httpx.ReadTimeout:
    print('Connected (SSE endpoint stays open — timeout is expected)')
except Exception as e:
    print(f'FAILED: {e}')
"
```

### 11.3 Execute Plan Returns 500 Error

**Symptom:** Clicking Execute Plan in the UI shows an error.

**Check backend logs:**
```bash
docker logs qaforge_backend --tail 50 | grep -i error
```

**Common causes:**
- NOT NULL constraint violation in `connections` or `execution_runs` table
- Missing `mcp` package (check `docker exec qaforge_backend python3 -c "import mcp; print('OK')"`)
- Database connection issue

### 11.4 Test Cases Show "No Template Matched"

**Symptom:** Execution runs but all tests show `template_used: none`.

**Cause:** Test cases have wrong `execution_type`, or the template is not registered.

**Fix:**
```bash
# Check execution_type
docker exec qaforge_db psql -U qaforge -d qaforge -c "
  SELECT id, title, execution_type FROM test_cases
  WHERE project_id = 'a8cd771e-07fa-4585-886b-0ff69d655f64';
"

# Should be 'mcp' for MCP test cases. If not:
docker exec qaforge_db psql -U qaforge -d qaforge -c "
  UPDATE test_cases SET execution_type = 'mcp'
  WHERE project_id = 'a8cd771e-07fa-4585-886b-0ff69d655f64';
"

# Verify mcp_tool is in template registry
docker exec qaforge_backend python3 -c "
from execution.templates import TEMPLATE_REGISTRY
print('Templates:', list(TEMPLATE_REGISTRY.keys()))
assert 'mcp_tool' in TEMPLATE_REGISTRY, 'mcp_tool NOT registered!'
print('mcp_tool: OK')
"
```

### 11.5 Frontend Not Updating After Deploy

**Symptom:** UI looks old, Execute Plan button missing after deploy.

**Cause:** Docker layer cache served stale frontend build.

**Fix:**
```bash
cd /opt/qaforge
docker compose build --no-cache frontend
docker compose up -d frontend
```

### 11.6 SSE Connection Hangs (Execution Stuck)

**Symptom:** Execution stuck on one test, never completes.

**Cause:** SSE endpoint keeps connection open indefinitely.

**Fix:** Cancel the execution, then investigate:
```bash
# Cancel via API
docker exec qaforge_backend python3 -c "
import httpx
r = httpx.post('http://localhost:8000/api/auth/login', json={'email':'admin@freshgravity.com','password':'admin123'})
token = r.json()['access_token']
# List running executions
r = httpx.get('http://localhost:8000/api/projects/a8cd771e-07fa-4585-886b-0ff69d655f64/execution-runs?status=running',
    headers={'Authorization': f'Bearer {token}'})
for run in r.json():
    print(f'Cancelling {run[\"id\"]}')
    httpx.post(f'http://localhost:8000/api/projects/a8cd771e-07fa-4585-886b-0ff69d655f64/execution-runs/{run[\"id\"]}/cancel',
        headers={'Authorization': f'Bearer {token}'})
"
```

---

## 12. Key IDs & URLs

### Project & Plan IDs

| Item | ID |
|------|-----|
| Project: "Reltio MCP Integration" | `a8cd771e-07fa-4585-886b-0ff69d655f64` |
| Test Plan: "Reltio MCP Smoke Test" | `402eba16-2733-494a-b250-357ccba4144f` |
| Connection: "Reltio MDM E2E Demo (Auto)" | `43dbf4d7-0b90-4038-bdb7-2f80b772a1e2` |

### Test Case IDs

| ID | Title | Tool |
|----|-------|------|
| `861415bb-dfaa-48d4-9f7f-f2a0a65e724b` | MCP Server Health Check | `health_check_tool` |
| `011ef6c2-6b22-4c85-842e-4d0532a433a0` | Reltio Entity Search via MCP | `search_entities_tool` |
| `aa24c560-6662-40f6-8471-27794ac7ef53` | Reltio Data Model Definition Retrieval | `get_data_model_definition_tool` |

### Available MCP Tools (45 Total)

<details>
<summary>Click to expand full tool list</summary>

**Entity (8):** search_entities_tool, get_entity_tool, update_entity_attributes_tool, create_entity_tool, get_entity_graph_tool, get_entity_parents_tool, get_entity_with_matches_tool, get_entity_interactions_tool

**Match (6):** get_entity_match_history_tool, find_potential_matches_tool, get_potential_matches_stats_tool, merge_entities_tool, reject_entity_match_tool, export_merge_tree_tool

**Relation (5):** get_relation_details_tool, create_relationships_tool, delete_relation_tool, get_entity_relations_tool, relation_search_tool

**Config (10):** get_business_configuration_tool, get_tenant_permissions_metadata_tool, get_tenant_metadata_tool, get_data_model_definition_tool, get_entity_type_definition_tool, get_change_request_type_definition_tool, get_relation_type_definition_tool, get_interaction_type_definition_tool, get_graph_type_definition_tool, get_grouping_type_definition_tool

**Workflow (7):** get_user_workflow_tasks_tool, reassign_workflow_task_tool, get_possible_assignees_tool, retrieve_tasks_tool, get_task_details_tool, start_process_instance_tool, execute_task_action_tool

**User (2):** get_users_by_role_and_tenant_tool, get_users_by_group_and_tenant_tool

**Other (7):** get_merge_activities_tool, check_user_activity_tool, create_interaction_tool, rdm_lookups_list_tool, unmerge_entity_tool, health_check_tool, capabilities_tool

</details>

### API Endpoints (Quick Reference)

```
# Auth
POST   /api/auth/login                          # Get JWT token
POST   /api/auth/register                       # Create user

# Execute Test Plan
POST   /api/projects/{pid}/test-plans/{tpid}/execute   # Trigger execution
GET    /api/projects/{pid}/execution-runs/{rid}         # Poll progress
GET    /api/projects/{pid}/execution-runs               # List all runs
POST   /api/projects/{pid}/execution-runs/{rid}/cancel  # Cancel run

# Review
POST   /api/reviews/{execution_id}              # Submit review (approve/reject)

# Connections
GET    /api/projects/{pid}/connections           # List connections
POST   /api/projects/{pid}/connections           # Create connection
```

---

## Quick Reference Card

```
+-------------------------------+----------------------------------------------+
| TASK                          | COMMAND                                      |
+-------------------------------+----------------------------------------------+
| SSH to VM                     | ssh -i ~/Desktop/innovation-lab.pem          |
|                               |   ubuntu@13.233.36.18                        |
+-------------------------------+----------------------------------------------+
| Start all QAForge             | cd /opt/qaforge &&                           |
|                               |   docker compose up -d                       |
+-------------------------------+----------------------------------------------+
| Start MCP server              | cd /opt/reltio-mcp-server &&                 |
|                               |   docker compose up -d &&                    |
|                               |   docker network connect                     |
|                               |     qaforge_default reltio_mcp_server        |
+-------------------------------+----------------------------------------------+
| Rebuild backend               | cd /opt/qaforge &&                           |
|                               |   docker compose build backend &&            |
|                               |   docker compose up -d backend               |
+-------------------------------+----------------------------------------------+
| Rebuild backend (full)        | docker compose build --no-cache backend      |
+-------------------------------+----------------------------------------------+
| Check all containers          | docker ps --format                           |
|                               |   'table {{.Names}}\t{{.Status}}'            |
+-------------------------------+----------------------------------------------+
| Backend logs                  | docker logs qaforge_backend --tail 30        |
+-------------------------------+----------------------------------------------+
| MCP logs                      | docker logs reltio_mcp_server --tail 30      |
+-------------------------------+----------------------------------------------+
| DB shell                      | docker exec -it qaforge_db                   |
|                               |   psql -U qaforge -d qaforge                 |
+-------------------------------+----------------------------------------------+
| Run migrations                | docker compose exec backend                  |
|                               |   sh -c "cd /app && alembic upgrade head"    |
+-------------------------------+----------------------------------------------+
| Open QAForge UI               | https://13.233.36.18:8080                    |
+-------------------------------+----------------------------------------------+
| Login                         | admin@freshgravity.com / admin123            |
+-------------------------------+----------------------------------------------+
```
