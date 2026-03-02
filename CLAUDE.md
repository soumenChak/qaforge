# QAForge — Development Guide

## Project
- **Stack:** FastAPI + React + PostgreSQL + Redis + ChromaDB (Docker Compose)
- **Backend:** `backend/main.py` entry point, 11 route modules in `backend/routes/`
- **Frontend:** React 18 + Tailwind CSS in `frontend/src/`
- **Production:** `https://13.233.36.18:8080` (VM)
- **Company:** FreshGravity

## Quick Start

```bash
cp .env.example .env        # Configure SECRET_KEY + LLM keys
docker compose up -d         # Start all 5 services
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
  frontend/
    src/
      pages/             # 11 React pages
      components/        # 10 reusable components
      services/api.js    # Modular API client
      contexts/          # AuthContext
    nginx.conf           # HTTPS + reverse proxy config
  docker-compose.yml     # 5-service stack
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

### Testing
```bash
# Backend tests (if any)
docker compose exec backend python -m pytest tests/ -v

# Manual API test
curl -k https://localhost:8080/api/health

# Agent API test
curl -k https://localhost:8080/api/agent/summary -H "X-Agent-Key: qf_..."
```

### Deploy
```bash
# VM deployment
git push && ssh VM 'cd /opt/qaforge && git pull && bash scripts/vm-deploy.sh'

# Local rebuild
docker compose build --parallel && docker compose up -d
```

## Key Files by Size (Most Complex)

| File | Lines | Purpose |
|------|-------|---------|
| `routes/test_cases.py` | ~2,200 | AI generation, CRUD, export, chat |
| `routes/projects.py` | ~1,400 | Projects, discovery, coverage |
| `routes/test_plans.py` | ~900 | Plans, checkpoints, traceability |
| `models.py` | ~900 | All Pydantic schemas |
| `db_models.py` | ~750 | All SQLAlchemy models |

## Ports (Avoid Conflicts)

| QAForge | Orbit | AgentForge |
|---------|-------|------------|
| 8080 | 80 | 8080 |
| 5434 | 5432 | 5433 |
| 6381 | 6379 | 6380 |
| 8001 | — | — |
