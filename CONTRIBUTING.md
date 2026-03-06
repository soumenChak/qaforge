# Contributing to QAForge

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git

### Local Development Setup

```bash
# Clone the repo
git clone git@bitbucket.org:lifio/qaforge.git
cd qaforge

# Configure environment
cp .env.example .env
# Edit .env: set SECRET_KEY, at least one LLM API key

# Start infrastructure (DB, Redis, ChromaDB)
docker compose up -d db redis chromadb

# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm start   # Opens http://localhost:3000

# MCP Server (separate terminal)
cd mcp-server
pip install -r requirements.txt
python main.py   # Runs on http://localhost:8000
```

### Full Stack via Docker

```bash
docker compose up -d
# Frontend: http://localhost:8080
# Backend API: http://localhost:8080/api/
# MCP SSE: http://localhost:8080/qaforge-mcp/sse
```

## Code Structure

| Directory | Language | Purpose |
|-----------|----------|---------|
| `backend/` | Python (FastAPI) | REST API, execution engine, AI agents |
| `backend/routes/` | Python | API route handlers (11 modules) |
| `backend/execution/` | Python | Test execution engine + templates |
| `frontend/src/pages/` | React (JS) | Page components |
| `frontend/src/components/` | React (JS) | Reusable UI components |
| `mcp-server/src/tools/` | Python | MCP tool implementations |
| `mcp-server/src/server.py` | Python | MCP tool registrations |
| `scripts/` | Python/JS | Utility scripts |

## Making Changes

### Backend (FastAPI)

Routes are in `backend/routes/`. The agent API (used by MCP tools) is in `agent_api.py`. Auth uses JWT tokens for the web UI and `X-Agent-Key` headers for AI agents.

Key files:
- `db_models.py` — SQLAlchemy models (source of truth for DB schema)
- `models.py` — Pydantic request/response schemas
- `dependencies.py` — Auth middleware, rate limiting, audit logging

### Frontend (React)

Pages are in `frontend/src/pages/`. Uses Tailwind CSS for styling. API calls go through `frontend/src/services/api.js`.

### MCP Server

Adding a new MCP tool:

1. **Add the backend endpoint** in `backend/routes/agent_api.py`
2. **Add the implementation** in `mcp-server/src/tools/<module>.py`:
   ```python
   async def my_new_tool_impl(param: str) -> dict:
       return await agent_get(f"/my-endpoint/{param}")
   ```
3. **Register the tool** in `mcp-server/src/server.py`:
   ```python
   from src.tools.module import my_new_tool_impl

   @mcp.tool()
   async def my_new_tool(param: str) -> dict:
       """Tool description for Claude to read."""
       return await my_new_tool_impl(param=param)
   ```
4. Rebuild: `docker compose build qaforge_mcp && docker compose up -d qaforge_mcp`

### Database Migrations

QAForge uses auto-migration via SQLAlchemy `create_all()`. For schema changes:

1. Update `backend/db_models.py`
2. Update `backend/models.py` (Pydantic schemas)
3. Restart backend — new columns are added automatically
4. For column renames or drops, use manual SQL via `docker exec -i qaforge_db psql -U qaforge -d qaforge`

## Coding Standards

- **Python**: Follow PEP 8. Use type hints for function signatures. Use `async/await` for all API handlers.
- **JavaScript**: Use functional components with hooks. Tailwind for all styling (no custom CSS unless necessary).
- **Naming**: snake_case for Python, camelCase for JavaScript. MCP tool names use snake_case.
- **Error handling**: Backend returns structured JSON errors. Frontend shows toast notifications.

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/my-change`
2. Make changes and test locally
3. Verify Docker build: `docker compose build`
4. Push and create PR against `main`
5. Include in PR description:
   - What changed and why
   - How to test it
   - Screenshots for UI changes

## Deployment

Production deploys to `13.233.36.18` (AWS EC2):

```bash
ssh -i innovation-lab.pem ubuntu@13.233.36.18
cd /opt/qaforge
git pull origin main
sudo docker compose build backend qaforge_mcp frontend  # whichever changed
sudo docker compose up -d backend qaforge_mcp frontend
```

Service names in docker-compose.yml: `db`, `redis`, `chromadb`, `backend`, `qaforge_mcp`, `frontend`.

### Checking Logs

```bash
sudo docker logs qaforge_backend --tail 50
sudo docker logs qaforge_mcp --tail 50
sudo docker logs qaforge_frontend --tail 50
```

## Security Notes

- Never commit `.env` files or API keys
- Agent keys (`qf_*`) are project-scoped — they can only access their own project's data
- The `QAFORGE_BOOTSTRAP_TOKEN` allows creating new projects — treat it like an admin password
- All user input is sanitized via `bleach` in `dependencies.py`
