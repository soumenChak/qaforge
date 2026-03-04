# QAForge — Development Guide

## Project
- **Stack:** FastAPI + React + PostgreSQL + Redis + ChromaDB + MCP Servers (Docker Compose)
- **Backend:** `backend/main.py` entry point, 11 route modules in `backend/routes/`
- **Frontend:** React 18 + Tailwind CSS in `frontend/src/`
- **MCP Server:** `mcp-server/` — FastMCP SSE, 20 QAForge tools for remote Claude Code/Desktop access
- **Production:** `https://13.233.36.18:8080` (VM)
- **Company:** FreshGravity

## Quick Start

```bash
cp .env.example .env        # Configure SECRET_KEY + LLM keys
docker compose up -d         # Start all 6 services (+ QAForge MCP server)
# Open https://localhost:8080 — admin@freshgravity.com / admin123
```

## Project Structure

```
qaforge/
  backend/
    main.py              # FastAPI app, middleware, route auto-discovery
    models.py            # Pydantic schemas (40+ models)
    db_models.py         # SQLAlchemy ORM (17 tables)
    dependencies.py      # JWT auth, agent key auth, RBAC, audit, sanitization
    db_session.py        # PostgreSQL connection pool
    routes/              # 11 route modules
      auth.py            # Login, register, JWT
      users.py           # User CRUD (admin)
      projects.py        # Projects, coverage, discovery, agent keys
      requirements.py    # Requirements, BRD/PRD extraction
      test_cases.py      # AI generation, CRUD, export, chat-generate
      test_plans.py      # Plans, checkpoints, traceability, summary
      templates.py       # Export templates
      knowledge.py       # RAG knowledge base (ChromaDB)
      feedback.py        # Quality feedback metrics
      settings.py        # LLM provider config
      agent_api.py       # External agent API (X-Agent-Key auth)
    agents/              # Domain-specific AI agents
      base_qa_agent.py   # Abstract base (prompt assembly, LLM call, parsing)
      api_agent.py       # REST API testing agent
      mdm_agent.py       # MDM (Reltio/Semarchy) testing agent
      ui_agent.py        # UI/Selenium testing agent
      reviewer_agent.py  # Test case quality reviewer
    core/
      llm_provider.py    # LLM abstraction (Anthropic/OpenAI/Groq/Ollama/Mock)
      prompt_guard.py    # Prompt injection detection (13 patterns)
      retry.py           # Exponential backoff retry
    execution/
      engine.py          # Test execution orchestrator
      templates/         # 10 execution templates (api_smoke, api_crud, db_query, etc.)
    alembic/             # Database migrations
  mcp-server/              # QAForge MCP Server (remote tool access for Claude Code)
    main.py                # Entry point: mcp.run(transport="sse")
    Dockerfile             # Python 3.11-slim container
    src/
      server.py            # FastMCP instance + 16 @mcp.tool() registrations
      api_client.py        # httpx async client → QAForge Agent API
      config.py            # QAFORGE_API_URL, QAFORGE_AGENT_KEY env vars
      tools/               # 7 tool modules:
        project.py         #   get_project, update_project
        requirements.py    #   list/extract/submit requirements
        test_cases.py      #   list/generate/submit test cases
        test_plans.py      #   list/create plans, get plan test cases
        executions.py      #   submit results, add proof
        knowledge.py       #   kb_stats, upload_reference
        summary.py         #   get_summary
  frontend/
    src/
      pages/             # 11 React pages
      components/        # 10 reusable components
      services/api.js    # Modular API client
      contexts/          # AuthContext
    nginx.conf           # HTTPS + reverse proxy (+ /qaforge-mcp/ + /mcp/)
  docker-compose.yml     # 6-service stack (backend, frontend, db, redis, chromadb, qaforge_mcp)
  certs/                 # SSL certificates (cert.pem, key.pem)
  scripts/
    vm-deploy.sh         # Production deployment script
  docs/                  # Architecture, integration guide, runbook
```

## Key Patterns

### Authentication (Dual Model)
- **UI users:** JWT Bearer token (`Authorization: Bearer <token>`) → `get_current_user()`
- **AI agents:** Agent API key (`X-Agent-Key: qf_...`) → `get_agent_project()`
- Agent keys are SHA-256 hashed in `projects.agent_api_key_hash`

### Route Registration
Routes auto-discovered in `main.py` — scan `routes/` for modules with `router` attribute.
Prefix mapping: `auth→/api/auth`, `projects→/api/projects`, `agent_api→/api/agent`, etc.

### Adding a New Route Module
1. Create `backend/routes/my_module.py` with `router = APIRouter()`
2. Add prefix mapping in `main.py` `ROUTE_PREFIXES` dict
3. Routes auto-register on restart

### Database Access
```bash
docker compose exec db psql -U qaforge                           # psql shell
docker compose exec backend sh -c "cd /app && alembic upgrade head"  # run migrations
docker compose exec backend sh -c "cd /app && alembic revision --autogenerate -m 'desc'"  # new migration
```

### LLM Provider Pattern
- Abstract base: `core/llm_provider.py` → `LLMProvider.complete()` / `.stream()`
- Singleton: `get_llm_provider()` reads `LLM_PROVIDER` env var
- 5 implementations: Anthropic, OpenAI, Groq, Ollama, Mock
- All calls wrapped in `retry_with_backoff()` (3 retries, exponential backoff)

### Domain Agent Pattern
- Extend `BaseQAAgent` in `agents/`
- Implement `generate_test_cases()` and `get_domain_patterns()`
- Agent builds prompt → calls LLM → parses JSON → normalizes fields

### Execution Template Pattern
- Templates in `execution/templates/` (e.g., `api_smoke.py`)
- Engine extracts parameters via LLM, matches to template, executes
- Each template returns: `{status, actual_result, duration_ms, error_message, proof_artifacts}`

### QAForge MCP Server (`mcp-server/`)

Exposes QAForge operations as 20 MCP tools over SSE transport (includes `connect`/`connection_status` for project switching), so any remote Claude Code/Desktop can manage tests without codebase access.

**How it works:** MCP Server → httpx calls → QAForge Agent API (`/api/agent/*`) → same auth (X-Agent-Key)

**Key files:**
- `mcp-server/src/server.py` — FastMCP instance + all `@mcp.tool()` decorators (20 tools, includes `connect`/`connection_status`)
- `mcp-server/src/api_client.py` — httpx wrapper with dynamic agent key (`set_agent_key()`/`get_active_key()` for session overrides)
- `mcp-server/src/tools/` — 7 modules (project, requirements, test_cases, test_plans, executions, knowledge, summary)

**Adding a new MCP tool:**
1. Add the implementation function in the appropriate `src/tools/*.py` module
2. Register it in `src/server.py` with `@mcp.tool()` decorator and a rich docstring
3. Rebuild: `docker compose build qaforge_mcp && docker compose up -d qaforge_mcp`

**Three setup paths:**
- **QA Users (Claude Code CLI):** `claude mcp add qaforge "https://host:8080/qaforge-mcp/sse" --transport sse` — URL is positional, NOT `--url`
- **QA Users (Claude Desktop):** Edit `~/Library/Application Support/Claude/claude_desktop_config.json` — add `mcpServers` block
- **Developers:** Full codebase access + MCP tools + `.mcp.json` in project root or `claude mcp add` globally

### MCP Client Configuration Formats

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{ "mcpServers": { "qaforge": { "url": "https://host:8080/qaforge-mcp/sse" } } }
```

**Claude Code `.mcp.json`** (project root — loads when `claude` runs from that dir):
```json
{ "mcpServers": { "qaforge": { "type": "sse", "url": "https://host:8080/qaforge-mcp/sse" } } }
```

**Claude Code CLI** (user-level, persists across sessions):
```bash
claude mcp add qaforge "https://host:8080/qaforge-mcp/sse" --transport sse
```

> **IMPORTANT:** Claude Desktop format uses just `"url"`. `.mcp.json` format requires `"type": "sse"` + `"url"`. They are different formats.

**SSE endpoints:**
- QAForge MCP: `https://13.233.36.18:8080/qaforge-mcp/sse` (20 tools)
- Reltio MCP: `https://13.233.36.18:8080/mcp/sse` (45 tools)

### Testing
```bash
# Backend tests (if any)
docker compose exec backend python -m pytest tests/ -v

# Manual API test
curl -k https://localhost:8080/api/health

# Agent API test
curl -k https://localhost:8080/api/agent/summary -H "X-Agent-Key: qf_..."

# MCP SSE test
curl -sk -N --max-time 5 https://localhost:8080/qaforge-mcp/sse
# Should return: event: endpoint\ndata: /qaforge-mcp/messages/?session_id=...
# IMPORTANT: Path MUST have /qaforge-mcp/ prefix. If it shows /messages/
# without prefix, FASTMCP_MOUNT_PATH is not set → MCP clients get 405
```

### Deploy
```bash
# VM deployment
git push && ssh VM 'cd /opt/qaforge && git pull && bash scripts/vm-deploy.sh'

# Local rebuild
docker compose build --parallel && docker compose up -d

# MCP server only
docker compose build qaforge_mcp && docker compose up -d qaforge_mcp
```

## Key Files by Size (Most Complex)

| File | Lines | Purpose |
|------|-------|---------|
| `routes/test_cases.py` | ~2,200 | AI generation, CRUD, export, chat |
| `routes/projects.py` | ~1,400 | Projects, discovery, coverage |
| `routes/test_plans.py` | ~900 | Plans, checkpoints, traceability |
| `models.py` | ~900 | All Pydantic schemas |
| `db_models.py` | ~750 | All SQLAlchemy models |
| `frontend/src/pages/Guide.js` | ~1,400 | 40 scenarios across 9 categories (getting-started, mcp, agents, test-cases, execution, frameworks, knowledge, admin, cli) |

## LLM-Driven Testing Workflow

QAForge is designed as a data platform that LLMs (Claude, Codex, etc.) orchestrate via CLI.
The LLM acts as the user interface. QAForge stores everything; the LLM executes the flow.

### CLI Tool: `qaforge.py`

Located at `scripts/qaforge.py` (in client project repos like Orbit). 16 commands:

```bash
# Setup & Status
qaforge.py setup --project "Name" --domain mdm --token $TOKEN
qaforge.py status

# MCP Discovery & Execution
qaforge.py discover --mcp-url http://localhost:8000/sse [--save]
qaforge.py execute --plan "Smoke Test" [--mcp-url http://...]

# Test Management
qaforge.py init --plan "Sprint 1 Tests"
qaforge.py submit-cases '[{...}]'
qaforge.py submit-results '[{...}]'
qaforge.py summary

# Test Runners (auto-submit results)
qaforge.py run-smoke
qaforge.py run-pytest backend/tests/
qaforge.py run-playwright --spec e2e/test.spec.js

# BRD/PRD Generation
qaforge.py generate-from-brd --brd file.xlsx --domain mdm --sub-domain reltio
qaforge.py upload-reference --file samples.xlsx --domain mdm
qaforge.py kb-stats --domain mdm
```

### Flow 1: Fresh Project Setup

When user says "set up testing for [project]":

1. **Ask for:** project name, domain (mdm/ai/data_eng/integration/digital), MCP server URL, BRD/PRD docs
2. **Bootstrap:** `qaforge.py setup --project "Name" --domain mdm --token $QAFORGE_BOOTSTRAP_TOKEN`
3. **Discover tools:** `qaforge.py discover --mcp-url http://localhost:8000/sse --save`
4. **Sanity check:** Submit a health_check_tool test case and execute to verify connectivity
5. **Report:** "Project ready, X tools discovered. Share BRD/PRD or describe what to test."

### Flow 2: Test Case Generation

When user provides BRD/PRD or testing requirements:

1. **Check KB:** `qaforge.py kb-stats --domain mdm` — see if reference samples exist
2. **Upload reference** (if provided): `qaforge.py upload-reference --file ref.xlsx --domain mdm`
3. **Generate:** `qaforge.py generate-from-brd --brd file.xlsx --reference ref.xlsx --domain mdm --count 10`
   - KB + reference framework ensures enterprise quality standards
   - Auto-saves best samples to KB for continuous learning
4. **PAUSE** — show user the generated test case summary, ask for review
5. **If changes needed:** fix and resubmit via `qaforge.py submit-cases`
6. **Duplicate:** users can duplicate good test cases via UI or API for quick variants

### Flow 3: Test Plan & Execution

1. **Create plan:** via agent API `POST /agent/test-plans`
2. **Assign test cases** to the plan
3. **PAUSE** — ask user to review plan
4. **Execute:** `qaforge.py execute --plan "Plan Name"`
5. **Review results:** show pass/fail per test case
6. **Fix failures:** if user asks, read the test case, identify issue, resubmit fix via API

### MCP Execution Engine

`scripts/mcp_executor.py` handles mechanical test execution:
- Connects to MCP servers via SSE transport
- Calls tools with specified params from structured test steps
- Validates assertions (json_path, contains, not_empty, response_time_ms, etc.)
- Supports variable binding between steps: `{{step_1.parsed.field}}`
- Records results + proof artifacts back to QAForge
- **Zero LLM tokens** — pure automation

### Multi-Tool Test Cases

Each test step specifies its own `tool_name` and `connection_ref`:
- Step 1: `search_entities_tool` → find entities
- Step 2: `merge_entities_tool` → merge using `{{step_1.parsed.objects.0.uri}}`
- Steps can reference different MCP servers via `connection_ref`

### Agent API Endpoints (X-Agent-Key auth)

```
POST /api/agent/bootstrap          — Create project + get API key
GET  /api/agent/project            — Get project metadata + app_profile
PUT  /api/agent/project            — Update app_profile, description
GET  /api/agent/test-plans         — List test plans (with stats)
POST /api/agent/test-plans         — Create test plan
GET  /api/agent/test-plans/{id}/test-cases — Get plan's test cases
POST /api/agent/test-cases         — Submit test cases (batch)
POST /api/agent/test-cases/{id}/duplicate — Duplicate a test case
POST /api/agent/executions         — Submit execution results
GET  /api/agent/summary            — Progress summary
POST /api/agent/generate-from-brd  — AI test case generation
POST /api/agent/upload-reference   — Upload KB reference samples
GET  /api/agent/kb-stats           — Knowledge base coverage
```

## New Environment Setup

### Prerequisites
- Docker 24+ and Docker Compose v2
- Python 3.10+ with `mcp` and `pyyaml` packages (for executor)
- At least one LLM API key (Anthropic, OpenAI, or Groq)
- MCP server running (e.g., Reltio MCP on port 8000)

### Step-by-Step

```bash
# 1. Deploy QAForge (VM or local)
cp .env.example .env        # Set SECRET_KEY + LLM keys
docker compose up -d         # Start 5 services (backend, frontend, db, redis, chromadb)
# Verify: curl -k https://localhost:8080/api/health

# 2. Copy qaforge.py + mcp_executor.py to your project repo
cp scripts/qaforge.py /path/to/your-project/scripts/
cp scripts/mcp_executor.py /path/to/your-project/scripts/

# 3. Set environment in your project's .env
QAFORGE_API_URL=https://<qaforge-host>:8080/api
QAFORGE_BOOTSTRAP_TOKEN=<get-from-admin>

# 4. Bootstrap project (creates project + saves agent key to .env)
python scripts/qaforge.py setup \
  --project "My Project" \
  --domain mdm --sub-domain reltio \
  --token $QAFORGE_BOOTSTRAP_TOKEN

# 5. Start MCP server (separate terminal or Docker)
cd /path/to/reltio-mcp-server
# If Docker: FASTMCP_HOST=0.0.0.0 docker compose up -d
# If local: source venv/bin/activate && python main.py

# 6. Discover MCP tools
python scripts/qaforge.py discover --mcp-url http://localhost:8000/sse --save

# 7. Run sanity test
python scripts/qaforge.py execute --plan "Smoke Test" --mcp-url http://localhost:8000/sse
```

### Port Map

| Service | Port | Container | Access |
|---------|------|-----------|--------|
| QAForge HTTPS (Nginx) | 8080 | `qaforge_frontend` | Public — UI, API, MCP proxy |
| QAForge Backend | 8000 | `qaforge_backend` | Internal only (behind Nginx) |
| QAForge MCP Server | 8090 | `qaforge_mcp` | Direct: `http://host:8090/sse`, via Nginx: `/qaforge-mcp/sse` |
| Reltio MCP Server | 8002 | `reltio_mcp_server` | Direct: `http://host:8002/sse`, via Nginx: `/mcp/sse` |
| PostgreSQL | 5434 | `qaforge_db` | Direct DB access |
| Redis | 6381 | `qaforge_redis` | Direct cache access |
| ChromaDB | 8001 | `qaforge_chromadb` | Vector DB |

### Nginx Proxy Routes

| Path | Proxied To | Strategy | Purpose |
|------|-----------|----------|---------|
| `/qaforge-mcp/*` | `http://qaforge_mcp:8000` (no trailing `/`) | Path preserved — FastMCP uses `sse_path`/`message_path` from `FASTMCP_MOUNT_PATH` | QAForge MCP Server (SSE) |
| `/mcp/*` | `http://reltio_mcp_server:8000/` (trailing `/`) | Prefix stripped + `sub_filter` rewrites `/messages/` → `/mcp/messages/` | Reltio MCP Server (SSE) |
| `/api/*` | `http://backend:8000/api/` | Prefix preserved | QAForge Backend API |
| `/*` | Static files | — | React SPA |

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `QAFORGE_API_URL` | Yes | QAForge API base URL (e.g., `https://host:8080/api`) |
| `QAFORGE_AGENT_KEY` | Yes* | Agent API key (auto-set by `setup` command) |
| `QAFORGE_BOOTSTRAP_TOKEN` | Once | Bootstrap token for first-time project creation |
| `QAFORGE_EXECUTOR` | No | Path to `mcp_executor.py` if not alongside `qaforge.py` |

### Python Dependencies for Executor
```bash
pip install mcp pyyaml   # Required for discover/execute commands
# OR use a venv that already has them (e.g., Reltio MCP server venv)
```
