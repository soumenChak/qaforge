# What is QAForge?

**QAForge is an AI-native quality engineering platform where the AI _is_ the interface.**

Unlike traditional QA tools where humans click through UIs to manage tests, QAForge is built from the ground up for AI agents. QA engineers, developers, and AI assistants all interact with the same platform — through natural language, MCP tools, or REST APIs — to manage the entire testing lifecycle.

---

## The Problem

Enterprise QA today is broken:

- **Manual test management** — Teams spend more time writing test documentation than actually testing
- **Tool fatigue** — Jira for tracking, TestRail for cases, Postman for APIs, Selenium for UI, custom scripts for everything else
- **No intelligence** — Test tools store data but don't learn. The 100th project starts from scratch, just like the first
- **Disconnected systems** — Test results live in spreadsheets, proof artifacts in screenshots folders, coverage gaps in someone's head
- **No AI integration** — Existing tools bolt on "AI features" as afterthoughts. Copilot-style autocomplete for test steps isn't transformation — it's decoration

## What Makes QAForge Different

### 1. AI-First Architecture

QAForge isn't a traditional tool with AI bolted on. It's a **data platform designed for AI agents to orchestrate**.

The AI reads requirements, generates enterprise-grade test cases using domain knowledge, executes tests against live systems, records results with proof artifacts, identifies coverage gaps, and fills them — all through natural language.

```
Human: "Generate regression tests for entity merge scenarios
        covering survivorship rules and conflict resolution"

QAForge: Reads MDM framework standards
       + Fetches 43 reference patterns from Knowledge Base
       + Analyzes 27 BRD requirements
       + Generates 5 enterprise-grade test cases
       + Each with structured steps, assertions, and traceability
```

No other QA tool does this.

### 2. MCP-Powered Tool Orchestration

QAForge exposes **69 tools across 2 MCP servers** that any AI assistant can use:

- **QAForge MCP (24 tools)** — Test management: projects, requirements, test cases, plans, executions, knowledge base, frameworks
- **Reltio MCP (45 tools)** — Live MDM system access: entity CRUD, search, match/merge, data model, workflows, analytics

One natural language command can trigger 5+ tool calls across both servers. The AI decides which tools to call, in what order, and how to combine the results.

### 3. Two Personas, One Platform

QAForge supports role-based AI access without any special configuration:

| Persona | Access | How |
|---------|--------|-----|
| **QA Engineer** | MCP tools only — no source code | Launch Claude from a workspace with just `.mcp.json` |
| **Developer** | Full codebase + MCP tools | Launch Claude from the project repo |

Same AI. Same platform. Different capabilities. Just `cd` to switch roles.

The QA engineer can manage the entire testing lifecycle — generate tests, execute against live systems, record results, generate reports — without ever seeing a line of code. The developer gets all of that plus the ability to read, debug, and fix the codebase.

### 4. Knowledge Base That Learns

Every project makes the next one better:

- **Domain frameworks** define what MUST be tested (e.g., MDM: Entity Lifecycle, Match & Merge, Data Quality, Security)
- **Reference patterns** capture how good tests look (43 Reltio-specific patterns and growing)
- **Best practices** encode organizational standards
- **Anti-patterns** prevent common mistakes

When the AI generates test cases, it doesn't start from zero — it draws from the accumulated knowledge of every previous project in that domain.

### 5. Cross-System Live Testing

QAForge doesn't just manage test documentation — it **executes tests against live systems**:

```
Human: "Run a smoke test against Reltio — check health,
        search for HCP entities, verify merge capabilities"

AI: 1. Calls Reltio MCP health_check_tool        -> Server healthy
    2. Calls Reltio MCP search_entities_tool      -> Found 15 HCP entities
    3. Calls Reltio MCP find_potential_matches_tool -> 3 potential duplicates
    4. Calls QAForge MCP submit_results           -> Results recorded
    5. Calls QAForge MCP add_proof                -> API responses attached
```

Two MCP servers, five tool calls, complete test execution with evidence — one sentence from the human.

### 6. Framework-Driven Compliance

Enterprise testing isn't random — it follows standards. QAForge bakes this in:

- Upload domain frameworks (MDM, Data Engineering, Integration, etc.)
- AI checks what's tested vs what MUST be tested
- Identifies coverage gaps automatically
- Generates targeted test cases to fill gaps
- Tracks compliance over time

---

## How It Compares

| Capability | TestRail / Zephyr | Postman / Katalon | QAForge |
|---|---|---|---|
| Test case management | Yes | Limited | Yes |
| AI test generation | No | Basic copilot | Domain-aware, KB-powered |
| MCP tool integration | No | No | 69 tools across 2 servers |
| Cross-system execution | No | Single API | Multi-MCP orchestration |
| Knowledge base learning | No | No | Continuous domain learning |
| Framework compliance | Manual | No | Automated gap analysis |
| Role-based AI access | N/A | N/A | QA vs Dev personas |
| Natural language interface | No | No | Primary interface |
| Proof artifacts | Manual upload | Manual | Auto-captured from execution |
| Multi-project switching | Separate logins | Separate workspaces | One command: `connect` |

---

## Architecture at a Glance

```
                          Natural Language
                               |
                    +----------+----------+
                    |                     |
              QA Engineer            Developer
              (MCP only)          (Code + MCP)
                    |                     |
                    v                     v
            +-------------+     +------------------+
            | QAForge MCP |     | Codebase Access  |
            | (24 tools)  |     | + QAForge MCP    |
            +------+------+     | + Reltio MCP     |
                   |            +--------+---------+
                   v                     |
            +-------------+              |
            | QAForge API |<-------------+
            | (FastAPI)   |
            +------+------+
                   |
        +----------+----------+----------+
        |          |          |          |
    PostgreSQL   Redis    ChromaDB   Reltio MCP
    (17 tables)  (cache)  (vectors)  (45 tools)
                                        |
                                        v
                                  Reltio MDM
                                  (Live API)
```

---

## Numbers

| Metric | Value |
|---|---|
| QAForge MCP tools | 24 |
| Reltio MCP tools | 45 |
| Total orchestrated tools | 69 |
| Domain frameworks | 5 (MDM, Data Eng, AI, Integration, Digital) |
| Knowledge base entries | 91 (and growing) |
| Backend routes | 11 modules |
| Database tables | 17 |
| LLM providers supported | 5 (Anthropic, OpenAI, Groq, Ollama, Mock) |
| Deployment | Docker Compose (6 containers) |
| SSL | Let's Encrypt auto-renewal |

---

## Built By

**FreshGravity** — Built with FastAPI, React, PostgreSQL, ChromaDB, and Claude.

QAForge is not another test management tool with AI sprinkled on top. It's a fundamentally new approach where AI agents are first-class citizens of the quality engineering process.

The question isn't "how do we add AI to our QA tools?" — it's "what does QA look like when AI is the starting point?"

QAForge is that answer.
