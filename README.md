# QAForge

**AI-Native Quality Engineering — Powered by Quinn & Forge**

QAForge is the first test management platform built for the AI era. No click-through UIs. No 2005-era workflows. Just two AI personas that handle quality engineering through conversation.

**Quinn** is your QA engineer — she tests live systems, generates domain-specific test cases, debugs failures, and documents everything with proof artifacts. No code access needed.

**Forge** is your developer — he has the full codebase, builds from live data, and shows you the engineering guardrails that make AI generation enterprise-grade.

Same platform. Two perspectives. 76 tools. Zero professional services needed.

> **[Read the full story: Meet Quinn & Forge](docs/MEET_QUINN_AND_FORGE.md)**

## Why QAForge?

The test management industry is worth $40B+ and runs on tools designed in 2005. QA engineers spend **78% of their time** on documentation, not testing (Capgemini World Quality Report). Every platform bolted on an AI copilot and called it innovation.

QAForge is different:
- **AI-native** — built from scratch for LLM orchestration, not retrofitted
- **MCP-first** — 76 tools across 2 MCP servers. Zero mainstream test platforms support MCP today
- **Two built-in personas** — Quinn (QA) and Forge (Dev) guide you through everything
- **Self-improving** — Knowledge Base compounds over time; LLM upgrades make Quinn & Forge smarter automatically
- **Self-service** — no consultants, no transformation projects. Install, connect, talk.

## Key Features

| Feature | Description |
|---------|-------------|
| **Quinn (QA Persona)** | Test through conversation — connect, test, generate, debug, fix, all via MCP |
| **Forge (Dev Persona)** | Full codebase access — build, inspect guardrails, deploy, self-test |
| **31 MCP Tools** | Connect, generate, execute, debug, fix — complete QA lifecycle via conversation |
| **AI Test Generation** | Domain-specific, backed by Knowledge Base patterns — not generic ChatGPT |
| **Live Execution** | Run tests against APIs, MCP servers, SQL databases, UIs — with proof artifacts |
| **Self-Service Debug** | Inspect failing tests, fix steps/expected results, re-execute — no developer needed |
| **Knowledge Base** | 96+ domain patterns that compound — every fix makes future generation better |
| **Testing Frameworks** | Domain-specific quality standards with gap analysis and coverage tracking |
| **Eats Its Own Dogfood** | QAForge tests itself — 18 self-test cases validated through its own agent API |

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

### 1. Deploy QAForge

```bash
git clone <repo-url> && cd qaforge
cp .env.example .env    # Set SECRET_KEY + at least one LLM API key
docker compose up -d     # Start all 6 services
```

Open the UI, create a project, and generate an agent API key (Project Settings > Agent API Key > Generate).

### 2. Meet Quinn (QA — No Code Needed)

```bash
# Set up Quinn's workspace (interactive — asks for MCP URL)
./scripts/setup-qa-workspace.sh

# Start talking to Quinn
cd ~/qa-workspace && claude
```

> "Hey Quinn, connect to my project with key qf_... and show me the dashboard"

### 3. Meet Forge (Developer — Full Codebase)

```bash
# Just open Claude Code from the QAForge repo
cd qaforge && claude
```

> "Hey Forge, build me a live dashboard and show me the guardrails"

### 4. Both at Once (The Full Experience)

Two terminals. Quinn on the left, Forge on the right. Same platform, two perspectives.

---

### Alternative: Connect Without the Setup Script

#### Claude Code (CLI)

```bash
npm install -g @anthropic-ai/claude-code

claude mcp add qaforge --transport sse \
  --url "https://your-host/qaforge-mcp/sse"

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
| [Meet Quinn & Forge](docs/MEET_QUINN_AND_FORGE.md) | **Start here** — The story, the vision, what they can do |
| [Setup Guide](docs/SETUP_GUIDE.md) | Docker deploy, HTTPS config, first-time setup |
| [Contributing](CONTRIBUTING.md) | Dev setup, code structure, PR process |
| [Open Source Checklist](docs/OPEN_SOURCE_CHECKLIST.md) | Security audit, team onboarding |
| [CLAUDE.md](CLAUDE.md) | Forge's persona — for developing QAForge with Claude Code |

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

Apache License 2.0 — see [LICENSE](LICENSE) for details.
