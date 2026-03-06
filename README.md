# QAForge

**Enterprise Test Documentation Platform — Where Quality Is Engineered**

QAForge is a test documentation and tracking platform designed for AI-assisted development. When AI agents (Claude Code, Codex, Gemini CLI) build and test applications, QAForge captures, structures, and tracks the evidence. Human QA validates at defined checkpoints.

## Why QAForge?

AI coding agents already perform extensive testing while building apps. But this testing is **undocumented** (results disappear in terminal output), **unstructured** (no standard format), **unvalidated** (no human QA checkpoint), and **untraceable** (no link from requirement to test case to result).

QAForge solves this by being the **documentation layer** — agents test, QAForge records.

## Key Features

| Feature | Description |
|---------|-------------|
| **Agent API** | Any AI agent submits test cases + execution results via `X-Agent-Key` header |
| **Test Plans** | Group test cases into plans (SIT, UAT, Regression, Smoke) with pass/fail tracking |
| **Proof Artifacts** | Attach evidence: API responses, screenshots, logs, data comparisons |
| **Validation Checkpoints** | Human QA gates — review and approve before sign-off |
| **AI Test Generation** | Domain-specific agents generate test cases from requirements + BRD/PRD |
| **Coverage Analysis** | Priority-weighted scoring with Requirements Traceability Matrix |
| **Testing Frameworks** | Domain-specific quality standards (AI, MDM, Data Eng, Integration, App) with versioning |
| **Knowledge Base** | RAG-powered semantic search for test patterns and best practices |

## Architecture

```
  ┌──────────────────────┐              ┌──────────────────────┐
  │   QA User            │              │   Developer          │
  │   (Claude Code)      │              │   (Claude Code)      │
  └──────────┬───────────┘              └──────────┬───────────┘
             │ SSE                                  │ SSE + Git
             │                                      │
  ┌──────────▼──────────────────────────────────────▼──────────┐
  │          Nginx (HTTPS — qaforge.freshgravity.net)           │
  │   /qaforge-mcp/* → QAForge MCP Server                      │
  │   /mcp/*         → Reltio MCP Server                       │
  │   /api/*         → QAForge Backend                         │
  │   /*             → React SPA                               │
  └────┬─────────────────┬─────────────────┬───────────────────┘
       │                 │                 │
  ┌────▼────┐     ┌──────▼──────┐   ┌─────▼─────┐
  │ QAForge │     │ QAForge MCP │   │ Reltio MCP│
  │ Backend │◄────│ Server      │   │ Server    │
  │ FastAPI │     │ 31 tools    │   │ 45 tools  │
  └──┬──┬──┬┘     └─────────────┘   └─────┬─────┘
     │  │  │                               │
  ┌──▼┐┌▼─┐┌▼──────┐┌────────┐     ┌──────▼──────┐
  │ PG ││Rs││Chroma ││ LLM   │     │ Reltio API  │
  │5434││63││ 8001  ││ APIs  │     │ (cloud)     │
  └────┘└──┘└───────┘└───────┘     └─────────────┘
```

## Quick Start

### Deploy QAForge (Admin / Developer)

```bash
# 1. Clone and configure
git clone git@bitbucket.org:lifio/qaforge.git
cd qaforge
cp .env.example .env
# Edit .env: set SECRET_KEY and at least one LLM API key

# 2. Launch all services (backend, frontend, MCP server, DB, Redis, ChromaDB)
docker compose up -d

# 3. Login
# Open https://qaforge.freshgravity.net
# Credentials: admin@freshgravity.com / admin123

# 4. Create a project and generate an agent key
# Projects > New Project > Agent API Key > Generate
```

### Connect as QA User (Claude Code / Claude Desktop — No Codebase Needed)

QA users don't need the QAForge source code. They connect to remote MCP servers.

#### Option A: Claude Code (CLI)

```bash
# 1. Install Claude Code
npm install -g @anthropic-ai/claude-code

# 2. Add QAForge MCP server (test management, generation, frameworks, execution)
claude mcp add qaforge --transport sse \
  --url "https://qaforge.freshgravity.net/qaforge-mcp/sse"

# 3. Add Reltio MCP server (entity search, match, merge — optional)
claude mcp add reltio --transport sse \
  --url "https://qaforge.freshgravity.net/mcp/sse"

# 4. Start Claude Code from any directory
cd ~/qa-workspace && claude
```

#### Option B: Claude Desktop App

Add MCP servers to your Claude Desktop config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "qaforge": {
      "type": "sse",
      "url": "https://qaforge.freshgravity.net/qaforge-mcp/sse"
    },
    "reltio": {
      "type": "sse",
      "url": "https://qaforge.freshgravity.net/mcp/sse"
    }
  }
}
```

Restart Claude Desktop, then talk naturally.

#### Option C: Project-Level `.mcp.json`

Add a `.mcp.json` file to any project directory:

```json
{
  "mcpServers": {
    "qaforge": {
      "type": "sse",
      "url": "https://qaforge.freshgravity.net/qaforge-mcp/sse"
    },
    "reltio": {
      "type": "sse",
      "url": "https://qaforge.freshgravity.net/mcp/sse"
    }
  }
}
```

Claude Code auto-discovers `.mcp.json` when you open the project.

#### What You Can Say

- *"Show me all test cases for the project"*
- *"Generate 10 security test cases from the requirements"*
- *"Execute the smoke test plan and show me results"*
- *"What's the current test coverage?"*
- *"Check framework coverage for the AI domain"*
- *"Search Reltio for Organization entities"*

## Integrate with Any Project

Add QAForge to any vibe-coded project in 2 minutes:

```bash
# 1. Add to your project's .env
QAFORGE_API_URL=https://qaforge.freshgravity.net/api
QAFORGE_AGENT_KEY=qf_your_key_here

# 2. Copy the helper script
cp qaforge/scripts/qaforge_client.py your-project/scripts/qaforge.py

# 3. Add to your CLAUDE.md (see docs/AGENT_INTEGRATION.md for template)
```

Then during vibe coding, just say: *"use QAForge to document testing"*

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | FastAPI (Python 3.11) | REST API + WebSocket |
| Frontend | React 18 + Tailwind CSS | Web UI |
| QAForge MCP | FastMCP (SSE) | 31 MCP tools for Claude Code |
| Reltio MCP | FastMCP (SSE) | 45 MCP tools for MDM operations |
| Database | PostgreSQL 16 | Primary data store |
| Cache | Redis 7 | Rate limiting, sessions |
| Vector DB | ChromaDB 0.4 | Semantic search embeddings |
| LLM | Anthropic / OpenAI / Groq / Ollama | AI test generation |
| Deploy | Docker Compose | Container orchestration |

## Documentation

| Document | Description |
|----------|-------------|
| [Testing Guide](docs/QAFORGE_TESTING_GUIDE.md) | **Start here** — Complete guide to using QAForge while vibe coding |
| [MCP Operations Guide](docs/MCP_OPERATIONS_GUIDE.md) | QAForge MCP + Reltio MCP setup, Claude Code connection, ops |
| [Architecture](docs/ARCHITECTURE.md) | System design, data model, security |
| [Agent Integration](docs/AGENT_INTEGRATION.md) | How to integrate any AI agent with QAForge |
| [Runbook](docs/RUNBOOK.md) | Deploy, monitor, troubleshoot |
| [CLAUDE.md](CLAUDE.md) | For developing QAForge with Claude Code |

## Project Structure

```
qaforge/
  backend/
    main.py              # FastAPI entry point
    models.py            # Pydantic schemas (898 lines)
    db_models.py         # SQLAlchemy ORM (746 lines)
    dependencies.py      # Auth, audit, sanitization
    routes/              # 11 route modules (7,083 lines)
      agent_api.py       # External agent endpoints
      test_plans.py      # Plans, checkpoints, executions
      test_cases.py      # CRUD + AI generation
      projects.py        # Projects + coverage + discovery
      ...
    agents/              # Domain-specific AI agents
    core/                # LLM provider abstraction
    execution/           # Test execution engine + templates
  mcp-server/            # QAForge MCP Server (SSE transport)
    main.py              # Entry point: mcp.run(transport="sse")
    src/server.py        # FastMCP instance + 31 tool registrations
    src/api_client.py    # httpx wrapper for QAForge Agent API
    src/tools/           # 8 tool modules (project, requirements, test_cases, frameworks, etc.)
    Dockerfile           # Python 3.11-slim container
  frontend/
    src/pages/           # 12 React pages (incl. Frameworks)
    src/components/      # 10 reusable components
    src/services/api.js  # API client modules
  docker-compose.yml     # 6-service stack + MCP server
  docs/
```

## License

Proprietary - FreshGravity. All rights reserved.
