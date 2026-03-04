# QAForge Architecture

**Enterprise Test Documentation Platform — System Design & Data Model**

---

## High-Level Architecture

```
  ┌──────────────────┐       ┌──────────────────┐
  │   QA User        │       │   Developer      │
  │   (Claude Code)  │       │   (Claude Code)  │
  │   MCP only       │       │   MCP + Git      │
  └────────┬─────────┘       └────────┬─────────┘
           │ SSE                       │ SSE + local
           │                           │
  ┌────────▼───────────────────────────▼─────────┐
  │              nginx (HTTPS :8080)               │
  │         TLS 1.2/1.3 + Security Headers         │
  ├────────────┬────────────┬──────────┬──────────┤
  │/qaforge-mcp│  /mcp/*    │ /api/*   │  /*      │
  │ QAForge MCP│  Reltio MCP│ Backend  │ React SPA│
  └────┬───────┴────┬───────┴────┬─────┴──────────┘
       │            │            │
  ┌────▼─────┐ ┌───▼──────┐ ┌──▼──────────────────┐
  │ QAForge  │ │ Reltio   │ │  FastAPI Backend     │
  │ MCP Srv  │ │ MCP Srv  │ │  Port 8000 (internal)│
  │ FastMCP  │ │ FastMCP  │ │                      │
  │ 16 tools │ │ 45 tools │ │ JWT + Agent Key Auth │
  │ :8090    │ │ :8002    │ │ 11 Route Modules     │
  │──────────│ │──────────│ │ Domain Agents (4)    │
  │ Calls    │ │ Calls    │ │ Execution Engine     │
  │ Agent API│─►          │ │ (11 templates)       │
  └──────────┘ └────┬─────┘ └──┬──┬──┬──┬─────────┘
                    │          │  │  │  │
                    │    ┌─────┘  │  │  └─────┐
                    │    │        │  │        │
               ┌────▼┐ ┌▼────┐ ┌─▼──▼─┐ ┌───▼───┐
               │Relt.│ │Post-│ │Redis │ │Chroma │
               │API  │ │gres │ │  7   │ │  DB   │
               │cloud│ │ 16  │ │:6381 │ │:8001  │
               └─────┘ │:5434│ └──────┘ └───────┘
                        └─────┘
```

## Container Stack

| Container | Image | Internal Port | External Port | Purpose |
|-----------|-------|:---:|:---:|---------|
| `qaforge_frontend` | React 18 + nginx | 443 | `${FRONTEND_PORT:-8080}` | SPA + HTTPS reverse proxy |
| `qaforge_backend` | FastAPI (Python 3.11) | 8000 | *internal only* | REST API + execution engine |
| `qaforge_mcp` | FastMCP (Python 3.11) | 8000 | `${MCP_PORT:-8090}` | QAForge MCP Server (16 tools, SSE) |
| `qaforge_db` | PostgreSQL 16 Alpine | 5432 | `${DB_PORT:-5434}` | Primary data store |
| `qaforge_redis` | Redis 7 Alpine | 6379 | `${REDIS_PORT:-6381}` | Rate limiting, caching |
| `qaforge_chromadb` | ChromaDB 0.4.24 | 8000 | `${CHROMADB_PORT:-8001}` | Vector embeddings (RAG) |
| `reltio_mcp_server` | FastMCP (Python 3.13) | 8000 | 8002 | Reltio MCP Server (45 tools, SSE) |

All QAForge services include health checks. Backend depends on db + redis + chromadb (healthy). Frontend depends on backend (healthy). MCP server depends on backend (healthy).

---

## Data Model

### Entity Relationship Diagram

```
  ┌──────────┐       ┌─────────────┐       ┌───────────────┐
  │  users   │──────<│  projects    │──────<│ requirements   │
  │          │ owns  │             │ has   │               │
  └──────────┘       └──────┬──────┘       └───────┬───────┘
                            │                      │
                     ┌──────┼──────┐        maps to│
                     │      │      │               │
              ┌──────▼──┐ ┌─▼────┐ ┌▼───────────┐  │
              │test_plans│ │agent │ │ test_cases  │◄─┘
              │         │ │sessions│             │
              └────┬────┘ └──────┘ └──────┬──────┘
                   │                      │
            ┌──────┼───────┐       ┌──────▼──────┐
            │      │       │       │ execution   │
      ┌─────▼───┐  │  ┌────▼────┐  │  _results   │
      │validation│  │  │coverage │  └──────┬──────┘
      │checkpoints│ │  │analysis │         │
      └──────────┘  │  └─────────┘  ┌──────▼──────┐
                    │               │   proof     │
                    │               │  _artifacts │
                    │               └─────────────┘
                    │
              ┌─────▼──────┐    ┌──────────────┐
              │ generation │    │  knowledge   │
              │  _runs     │    │  _entries    │
              └────────────┘    └──────────────┘
```

### Core Tables

#### `projects`
The top-level entity. Every test case, plan, and requirement belongs to a project.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `name` | String | Project name (unique) |
| `domain` | String | Domain: MDM, AI, Data Engineering, etc. |
| `sub_domain` | String | Sub-domain: Reltio, Databricks, GenAI, etc. |
| `description` | Text | Project description |
| `app_profile` | JSONB | Auto-detected app profile (tech stack, routes, test infra) |
| `brd_prd_text` | Text | Business/product requirements document text |
| `status` | String | active / archived |
| `agent_api_key_hash` | String | SHA-256 hash of agent API key |
| `template_id` | UUID (FK) | Default export template |
| `created_by` | UUID (FK) | Owner user |
| `created_at` / `updated_at` | Timestamp | Audit timestamps |

#### `test_cases`
Individual test cases — AI-generated or manual.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Internal primary key |
| `project_id` | UUID (FK) | Parent project |
| `requirement_id` | UUID (FK) | Linked requirement (traceability) |
| `test_plan_id` | UUID (FK) | Grouped under plan |
| `test_case_id` | String | Human-readable ID (e.g., TC-AUTH-001) |
| `title` | String | Concise title |
| `description` | Text | What the test validates |
| `preconditions` | Text | Prerequisites |
| `test_steps` | JSONB | `[{step_number, action, expected_result}]` |
| `expected_result` | Text | Overall expected outcome |
| `test_data` | JSONB | Input data for the test |
| `priority` | String | P1 / P2 / P3 / P4 |
| `category` | String | functional / integration / regression / smoke / e2e |
| `execution_type` | String | api / ui / sql / manual |
| `domain_tags` | JSONB | `["auth", "rbac", "rest"]` |
| `source` | String | ai_generated / manual / uploaded |
| `status` | String | draft / active / passed / failed / blocked / deprecated |
| `rating` | Integer | 1-5 quality rating |
| `generated_by_model` | String | LLM model that generated this |

#### `execution_results`
Proof that a test case was executed, with outcome.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `test_case_id` | UUID (FK) | Which test case was run |
| `test_plan_id` | UUID (FK) | Under which plan |
| `status` | String | passed / failed / error / skipped / blocked |
| `actual_result` | Text | What actually happened |
| `duration_ms` | Integer | Execution time |
| `error_message` | Text | Error details (if failed) |
| `environment` | JSONB | `{url, method, headers, ...}` |
| `executed_by` | String | Agent name or user email |
| `agent_session_id` | UUID (FK) | Agent session reference |
| `review_status` | String | pending / approved / rejected |
| `reviewed_by` | UUID (FK) | Reviewer user |
| `review_comment` | Text | Review notes |

#### `proof_artifacts`
Evidence attached to an execution result.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `execution_result_id` | UUID (FK) | Parent execution |
| `proof_type` | String | See Proof Types below |
| `title` | String | Artifact title |
| `content` | JSONB | Artifact payload |
| `file_path` | String | Path for file-based artifacts |

**Proof Types:** `api_response`, `screenshot`, `test_output`, `query_result`, `data_comparison`, `dq_scorecard`, `log`, `code_diff`, `manual_note`

#### `test_plans`
Named grouping of test cases with lifecycle tracking.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `project_id` | UUID (FK) | Parent project |
| `name` | String | Plan name |
| `description` | Text | What this plan covers |
| `plan_type` | String | sit / uat / regression / smoke / migration / custom |
| `status` | String | active / completed / archived |

#### `validation_checkpoints`
Human QA gates — review and approve before sign-off.

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Primary key |
| `test_plan_id` | UUID (FK) | Parent plan |
| `checkpoint_type` | String | test_case_review / execution_review / sign_off |
| `status` | String | pending / approved / rejected / needs_rework |
| `reviewer_id` | UUID (FK) | Who reviewed |
| `comments` | Text | Review comments |

### Supporting Tables

| Table | Purpose |
|-------|---------|
| `users` | Platform users with roles: admin, lead, tester |
| `requirements` | Business/functional requirements (BRD/PRD extraction) |
| `agent_sessions` | Track AI agent submissions (name, version, mode) |
| `knowledge_entries` | RAG knowledge base (patterns, defects, best practices) |
| `feedback_entries` | Quality feedback on AI-generated test cases |
| `generation_runs` | LLM usage tracking (tokens, cost, duration) |
| `cost_tracking` | Per-operation cost (LLM, Snowflake, Databricks) |
| `test_templates` | Export templates (Excel/Word/JSON formatting) |
| `audit_log` | Immutable audit trail (who did what, when) |
| `app_settings` | Key-value configuration store |

---

## Authentication & Authorization

### Dual Auth Model

QAForge uses two independent auth mechanisms:

```
  Human Users (UI)              AI Agents (API)
  ─────────────────             ─────────────────
  POST /api/auth/login          X-Agent-Key header
  → JWT Bearer token            → SHA-256 hash match
  → 24h expiry                  → Project-scoped
  → roles: admin/lead/tester    → No user identity
  → Full UI + API access        → Agent endpoints only
```

**JWT Token Payload:**
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "roles": ["admin"],
  "iat": 1709337600,
  "exp": 1709424000
}
```

**Agent Key Flow:**
1. Admin generates key via UI: `Projects → Agent API Key → Generate`
2. Key shown once (e.g., `qf_abc123...`), stored as SHA-256 hash in `projects.agent_api_key_hash`
3. Agent sends `X-Agent-Key: qf_abc123...` header with every request
4. Backend hashes received key, matches against project hash
5. Returns `Project` model (agent operates within project scope)

### RBAC Matrix

| Action | Admin | Lead | Tester | Agent |
|--------|-------|------|--------|-------|
| Create project | ✅ | ✅ | ❌ | ❌ |
| Generate test cases | ✅ | ✅ | ✅ | ✅ |
| Submit execution results | ✅ | ✅ | ✅ | ✅ |
| Review checkpoints | ✅ | ✅ | ❌ | ❌ |
| Manage users | ✅ | ❌ | ❌ | ❌ |
| Configure LLM settings | ✅ | ❌ | ❌ | ❌ |
| Generate/rotate agent keys | ✅ | ✅ | ❌ | ❌ |

---

## Agent API Flow

The primary integration path for AI agents during vibe coding:

```
  Agent (Claude Code / Codex / Gemini CLI)
    │
    │  1. PUT /api/agent/project
    │     → Populate app_profile, description
    │
    │  2. POST /api/agent/sessions
    │     → {agent_name, agent_version, submission_mode}
    │     ← {session_id}
    │
    │  3. POST /api/agent/test-plans
    │     → {name, plan_type: "smoke"}
    │     ← {plan_id}
    │
    │  4. POST /api/agent/test-cases
    │     → {test_cases: [...], test_plan_id}
    │     ← [{id, test_case_id, ...}]
    │
    │  5. POST /api/agent/executions
    │     → {executions: [{test_case_id, status, proof_artifacts}]}
    │     ← [{id, status, ...}]
    │
    │  6. GET /api/agent/summary
    │     ← {total: 82, passed: 80, failed: 2, pass_rate: 97.6}
    │
    ▼
  QAForge UI (human QA reviews at checkpoints)
```

---

## AI Generation Pipeline

### Test Case Generation

```
  User/Agent Request
    │
    ├─ description (what to test)
    ├─ domain + sub_domain
    ├─ requirements (optional)
    ├─ app_profile (optional)
    │
    ▼
  Domain Agent Selection
    │
    ├─ API Agent      → REST API testing patterns
    ├─ MDM Agent      → Master Data Management (Reltio/Semarchy)
    ├─ UI Agent       → Browser/Selenium testing patterns
    └─ Reviewer Agent → Quality review of generated tests
    │
    ▼
  Prompt Assembly
    │
    ├─ System prompt (role + output format)
    ├─ Domain patterns (from knowledge base)
    ├─ Requirements context
    ├─ App profile context
    ├─ Prompt injection guard (13 patterns)
    │
    ▼
  LLM Provider (pluggable)
    │
    ├─ Anthropic (Claude)     ─┐
    ├─ OpenAI (GPT)           ─┤ Exponential backoff
    ├─ Groq (Llama on LPU)   ─┤ retry (3 attempts)
    ├─ Ollama (local)         ─┤ Fast-fail on 4xx
    └─ Mock (testing)         ─┘
    │
    ▼
  Response Parsing
    │
    ├─ Extract JSON from markdown
    ├─ Handle trailing commas, partial JSON
    ├─ Normalize fields (priority, steps)
    ├─ Assign test_case_id (TC-001, TC-002, ...)
    │
    ▼
  Test Cases (status: draft, source: ai_generated)
    │
    ▼
  Human Review → Approve / Reject / Rework
```

### Knowledge Base (RAG)

```
  Knowledge Entry
    │
    ├─ Type: pattern / defect / best_practice / test_case
    ├─ Domain: MDM / AI / Data Engineering
    ├─ Content: text description
    │
    ▼
  ChromaDB
    │
    ├─ Embedding: sentence-transformers (via ChromaDB default)
    ├─ Collection: qaforge_knowledge
    ├─ Persistent storage (Docker volume)
    │
    ▼
  Semantic Search
    │
    ├─ Query: natural language
    ├─ Filter: domain, entry_type
    ├─ Returns: top-K relevant entries
    │
    ▼
  Injected into LLM Prompt
    └─ "Here are relevant patterns from the knowledge base: ..."
```

---

## Execution Engine

The execution engine can auto-execute test cases using pluggable templates:

### Template Types

| Template | What It Tests | Key Parameters |
|----------|--------------|----------------|
| `api_smoke` | Single HTTP request | method, endpoint, expected_status, expected_fields |
| `api_crud` | Full CRUD lifecycle | base_url, resource, create_body, update_body |
| `db_query` | SQL query validation | query, expected_rows, column_checks, value_assertions |
| `db_reconciliation` | Source-to-target comparison | source_query, target_query, match_columns |
| `mdm_entity` | MDM entity validation | entity_type, match_rules, survivorship |
| `data_quality` | DQ rule validation | rules, thresholds, data_source |
| `etl_pipeline` | ETL job execution | pipeline_name, input, expected_output |
| `llm_evaluation` | LLM response quality | prompt, expected_patterns, quality_thresholds |
| `agent_workflow` | Agentic AI workflow | workflow_steps, expected_outcomes |
| `ui_playwright` | Browser UI automation | url, actions, assertions |

### Execution Flow

```
  Test Case
    │
    ▼
  Parameter Extraction (LLM)
    │  "Given these test steps, extract template parameters"
    ▼
  Template Matching
    │  Best match by execution_type + domain
    ▼
  Template Execution
    │  HTTP call / SQL query / browser action
    ▼
  Result Capture
    │  status, actual_result, duration_ms, error_message
    ▼
  Proof Artifact Generation
    │  api_response, query_result, screenshot, etc.
    ▼
  ExecutionResult + ProofArtifact (saved to DB)
```

---

## Security Model

### Defense Layers

| Layer | Mechanism | Details |
|-------|-----------|---------|
| **Transport** | TLS 1.2/1.3 | nginx terminates HTTPS, self-signed or Let's Encrypt |
| **Auth** | JWT + Agent Keys | Dual auth model (see above) |
| **RBAC** | Role-based access | admin / lead / tester permissions |
| **Rate Limiting** | slowapi + Redis | 200 req/min default, per-IP |
| **Input Sanitization** | Regex stripping | 13 patterns: script tags, event handlers, iframes |
| **Prompt Guard** | Injection detection | 13 patterns: role hijack, jailbreak, encoding bypass |
| **Audit** | Immutable log | All significant actions logged with user, IP, timestamp |
| **CORS** | Origin allowlist | Configurable via `CORS_ORIGINS` env var |
| **Headers** | Security headers | X-Frame-Options, HSTS, CSP, XSS-Protection |
| **DB** | Connection pool | pool_size=10, max_overflow=20, statement_timeout=30s |

### Prompt Injection Guard (13 Patterns)

Applied to all user-supplied text before LLM prompt injection:
`system_override`, `role_hijack`, `prompt_leak`, `jailbreak_dan`, `token_smuggle`, `base64_inject`, `markdown_inject`, `context_reset`, `sudo_mode`, `instruction_inject`, `delimiter_attack`, `persona_switch`, `encoding_bypass`

---

## Cost Tracking

Every LLM call and external service usage is tracked:

```json
{
  "user_id": "uuid",
  "project_id": "uuid",
  "operation_type": "llm",
  "provider": "anthropic",
  "model": "claude-sonnet-4-5-20250929",
  "tokens_in": 1500,
  "tokens_out": 4000,
  "estimated_cost_usd": 0.045,
  "created_at": "2026-03-02T10:00:00Z"
}
```

Supported operation types: `llm`, `snowflake`, `databricks`, `api`

---

## Frontend Architecture

### React Application

```
  App.js (Router)
    │
    ├─ AuthContext (global auth state)
    │
    ├─ /login              → Login.js
    │
    └─ ProtectedRoute (JWT required)
        ├─ Layout.js (sidebar + header)
        │
        ├─ /                → Dashboard.js
        ├─ /projects        → Projects.js
        ├─ /projects/:id    → ProjectDetail.js
        │   ├─ Test Cases tab
        │   ├─ Requirements tab
        │   └─ Test Plans tab
        │
        ├─ /projects/:id/test-plans/:planId → TestPlanDetail.js
        │   ├─ Test Cases tab
        │   ├─ Executions tab (with ProofViewer)
        │   ├─ Checkpoints tab
        │   ├─ Traceability tab (RTM matrix)
        │   └─ Summary tab (executive stats)
        │
        ├─ /projects/:id/test-cases/:tcId → TestCaseEditor.js
        ├─ /templates       → TemplateManager.js
        ├─ /knowledge       → KnowledgeBase.js
        ├─ /settings        → Settings.js
        └─ /users           → Users.js (admin only)
```

### API Client (`services/api.js`)

Modular API clients with JWT auto-injection:
`authAPI`, `usersAPI`, `projectsAPI`, `requirementsAPI`, `testCasesAPI`, `templatesAPI`, `feedbackAPI`, `knowledgeAPI`, `settingsAPI`, `testPlansAPI`, `executionsAPI`, `agentKeyAPI`

---

## Port Allocation

Chosen to avoid conflicts with co-located services:

| Service | QAForge | Orbit | AgentForge |
|---------|---------|-------|------------|
| Frontend | 8080 | 80 | 8080 |
| Database | 5434 | 5432 | 5433 |
| Redis | 6381 | 6379 | 6380 |
| Vector DB | 8001 | — | — |
