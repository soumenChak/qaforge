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
| **Knowledge Base** | RAG-powered semantic search for test patterns and best practices |

## Architecture

```
                          +------------------+
                          |   QAForge UI     |
                          |   (React/nginx)  |
                          |   Port 8080      |
                          +--------+---------+
                                   |
                          +--------+---------+
                          |  QAForge Backend |
                          |  (FastAPI/Python) |
                          |  Port 8000       |
                          +--+-----+-----+--+
                             |     |     |
                    +--------+  +--+--+  +--------+
                    |           |     |           |
              +-----+----+ +---+---+ +----+----+ +--------+
              | PostgreSQL | | Redis | | ChromaDB | | LLM    |
              | Port 5434  | | 6381  | | 8001     | | APIs   |
              +------------+ +-------+ +----------+ +--------+
```

## Quick Start

```bash
# 1. Clone and configure
git clone git@bitbucket.org:lifio/qaforge.git
cd qaforge
cp .env.example .env
# Edit .env: set SECRET_KEY and at least one LLM API key

# 2. Launch
docker compose up -d

# 3. Login
# Open https://localhost:8080
# Credentials: admin@freshgravity.com / admin123

# 4. Create a project and generate an agent key
# Projects > New Project > Agent API Key > Generate
```

## Integrate with Any Project

Add QAForge to any vibe-coded project in 2 minutes:

```bash
# 1. Add to your project's .env
QAFORGE_API_URL=https://your-qaforge-host:8080/api
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
| Database | PostgreSQL 16 | Primary data store |
| Cache | Redis 7 | Rate limiting, sessions |
| Vector DB | ChromaDB 0.4 | Semantic search embeddings |
| LLM | Anthropic / OpenAI / Groq / Ollama | AI test generation |
| Deploy | Docker Compose | Container orchestration |

## Documentation

| Document | Description |
|----------|-------------|
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
  frontend/
    src/pages/           # 11 React pages
    src/components/      # 10 reusable components
    src/services/api.js  # API client modules
  docker-compose.yml
  docs/
```

## License

Proprietary - FreshGravity. All rights reserved.
