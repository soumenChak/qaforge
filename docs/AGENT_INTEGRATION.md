# QAForge Agent Integration Guide

**How any AI agent integrates with QAForge during vibe coding**

---

## Overview

QAForge is the **documentation layer** for AI-assisted development. When AI agents (Claude Code, Codex, Gemini CLI) build and test applications, QAForge captures, structures, and tracks the evidence. Human QA validates at defined checkpoints.

This guide covers everything an AI agent needs to:
1. Authenticate with QAForge
2. Submit test cases and execution results
3. Attach proof artifacts
4. Track testing progress

---

## Quick Start (2 Minutes)

### 1. Get Your Agent Key

```
QAForge UI → Projects → Your Project → Agent API Key → Generate
```

Key is shown **once** — store it securely. Format: `qf_<random_string>`

### 2. Add to Your Project

```bash
# .env
QAFORGE_API_URL=https://your-qaforge-host:8080/api
QAFORGE_AGENT_KEY=qf_your_key_here
```

### 3. Copy the Helper Script

```bash
cp qaforge/scripts/qaforge_client.py your-project/scripts/qaforge.py
```

### 4. Add to Your CLAUDE.md

See the [CLAUDE.md Template](#claudemd-template) section below.

### 5. Start Using

During vibe coding, just say: *"use QAForge to document testing"*

---

## Authentication

All agent API calls use the `X-Agent-Key` header. No JWT, no login, no session cookies.

```bash
curl -k https://your-qaforge:8080/api/agent/summary \
  -H "X-Agent-Key: qf_your_key_here"
```

The key is project-scoped — all data submitted is automatically associated with the correct project.

**Key Security:**
- Keys are SHA-256 hashed before storage (never stored in plaintext)
- One key per project (rotate via UI: Agent API Key → Regenerate)
- Keys cannot access other projects' data

---

## Complete API Reference

Base URL: `https://your-qaforge:8080/api/agent`

All requests require: `X-Agent-Key: qf_...` header and `Content-Type: application/json`

### 1. Update Project Metadata

Populate the project's app profile so QAForge understands what's being tested.

```bash
curl -k -X PUT https://qaforge:8080/api/agent/project \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{
    "app_profile": {
      "tech_stack": ["FastAPI", "React", "PostgreSQL"],
      "api_modules": ["auth", "users", "candidates"],
      "test_infrastructure": ["pytest", "smoke_test.py", "playwright"]
    },
    "description": "Orbit — AI-powered recruitment platform",
    "brd_prd_text": "Business requirements text here..."
  }'
```

**Response:**
```json
{
  "project_id": "uuid",
  "project_name": "Orbit",
  "updated_fields": ["app_profile", "description"]
}
```

**Allowed fields:** `app_profile` (JSONB), `description` (text), `brd_prd_text` (text)

---

### 2. Create Agent Session

Track which agent submitted what. Sessions group submissions for audit.

```bash
curl -k -X POST https://qaforge:8080/api/agent/sessions \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "claude-code",
    "agent_version": "1.0.0",
    "submission_mode": "batch",
    "session_meta": {
      "project_path": "/path/to/project",
      "trigger": "smoke-test-run"
    }
  }'
```

**Response:**
```json
{
  "id": "session-uuid",
  "project_id": "project-uuid",
  "agent_name": "claude-code",
  "agent_version": "1.0.0",
  "submission_mode": "batch",
  "started_at": "2026-03-02T10:00:00Z"
}
```

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_name` | string | ✅ | Agent identifier (e.g., `claude-code`, `codex`, `gemini-cli`) |
| `agent_version` | string | ❌ | Agent version |
| `submission_mode` | string | ❌ | `realtime` or `batch` (default: `realtime`) |
| `session_meta` | object | ❌ | Free-form metadata |

---

### 3. Create Test Plan

Group test cases and execution results under a named plan.

```bash
curl -k -X POST https://qaforge:8080/api/agent/test-plans \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Orbit Production Smoke Test",
    "description": "140-test smoke suite covering all 17 API sections",
    "plan_type": "smoke"
  }'
```

**Response:**
```json
{
  "id": "plan-uuid",
  "project_id": "project-uuid",
  "name": "Orbit Production Smoke Test",
  "plan_type": "smoke",
  "status": "active",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Plan Types:** `sit`, `uat`, `regression`, `smoke`, `migration`, `custom`

---

### 4. Submit Test Cases

Submit one or more test cases. Stored as `status=draft`, `source=ai_generated`.

```bash
curl -k -X POST https://qaforge:8080/api/agent/test-cases \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{
    "test_plan_id": "plan-uuid",
    "test_cases": [
      {
        "test_case_id": "TC-AUTH-001",
        "title": "Login with valid credentials returns JWT",
        "description": "Verify POST /api/auth/login with valid email+password returns 200 with access_token",
        "preconditions": "Admin user exists: admin@company.com / admin123",
        "test_steps": [
          {
            "step_number": 1,
            "action": "POST /api/auth/login with {email, password}",
            "expected_result": "200 OK"
          },
          {
            "step_number": 2,
            "action": "Check response body",
            "expected_result": "Contains access_token and token_type=bearer"
          }
        ],
        "expected_result": "200 OK with valid JWT token",
        "priority": "P1",
        "category": "functional",
        "execution_type": "api",
        "domain_tags": ["auth", "jwt", "login"]
      }
    ]
  }'
```

**Response:** Array of created test cases with `id` (UUID) for each.

**Test Case Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `test_case_id` | string | ✅ | Human-readable ID (unique within project) |
| `title` | string | ✅ | Concise test title |
| `description` | string | ❌ | What the test validates |
| `preconditions` | string | ❌ | Prerequisites |
| `test_steps` | array | ❌ | `[{step_number, action, expected_result}]` |
| `expected_result` | string | ❌ | Overall expected outcome |
| `test_data` | object | ❌ | Input data (JSON) |
| `priority` | string | ❌ | `P1` / `P2` / `P3` / `P4` (default: P2) |
| `category` | string | ❌ | `functional` / `integration` / `regression` / `smoke` / `e2e` |
| `execution_type` | string | ❌ | `api` / `ui` / `sql` / `manual` (default: api) |
| `domain_tags` | array | ❌ | `["auth", "rbac"]` |
| `requirement_id` | UUID | ❌ | Link to requirement (traceability) |
| `test_plan_id` | UUID | ❌ | Override batch-level plan |

---

### 5. Submit Execution Results

Submit results with proof artifacts. Each result links to a test case.

```bash
curl -k -X POST https://qaforge:8080/api/agent/executions?session_id=session-uuid \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{
    "executions": [
      {
        "test_case_id": "tc-internal-uuid",
        "status": "passed",
        "actual_result": "200 OK — JWT token returned with correct claims",
        "duration_ms": 45,
        "environment": {
          "url": "http://localhost:8000",
          "method": "POST /api/auth/login"
        },
        "proof_artifacts": [
          {
            "proof_type": "api_response",
            "title": "Login response",
            "content": {
              "status_code": 200,
              "body": {
                "access_token": "eyJ...",
                "token_type": "bearer"
              }
            }
          }
        ]
      }
    ]
  }'
```

**Response:** Array of created execution results with proof artifacts.

**Execution Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `test_case_id` | UUID | ✅ | Internal UUID of the test case |
| `status` | string | ✅ | `passed` / `failed` / `error` / `skipped` / `blocked` |
| `actual_result` | string | ❌ | What actually happened |
| `duration_ms` | integer | ❌ | Execution time in milliseconds |
| `error_message` | string | ❌ | Error details (if failed) |
| `environment` | object | ❌ | `{url, method, headers, ...}` |
| `test_plan_id` | UUID | ❌ | Override test case's plan |
| `proof_artifacts` | array | ❌ | Evidence (see below) |

---

### 6. Add Proof Artifact (to existing execution)

```bash
curl -k -X POST https://qaforge:8080/api/agent/executions/{execution_id}/proof \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{
    "proof_type": "test_output",
    "title": "pytest stdout",
    "content": "PASSED test_auth.py::test_login_valid (0.045s)"
  }'
```

### Proof Artifact Types

| Type | When to Use | Content Example |
|------|-------------|-----------------|
| `api_response` | HTTP request/response | `{status_code, headers, body}` |
| `test_output` | stdout/stderr from test run | Plain text output |
| `screenshot` | Visual evidence | Base64-encoded image |
| `log` | Application or console logs | Log text |
| `query_result` | SQL query results | `{query, rows, columns}` |
| `data_comparison` | Source vs target comparison | `{source, target, diffs}` |
| `dq_scorecard` | Data quality scorecard | `{rules, scores, overall}` |
| `code_diff` | Code changes related to test | Diff text |
| `manual_note` | Human observation | Free-form text |

---

### 7. Get Summary

```bash
curl -k https://qaforge:8080/api/agent/summary \
  -H "X-Agent-Key: qf_..."
```

**Response:**
```json
{
  "project_name": "Orbit",
  "total_test_cases": 82,
  "by_status": {"passed": 80, "failed": 2},
  "total_executions": 82,
  "passed": 80,
  "failed": 2,
  "pending_review": 82,
  "pass_rate": 97.6
}
```

Optional: `?test_plan_id=uuid` to filter by plan.

---

### 8. Get Test Cases

```bash
curl -k https://qaforge:8080/api/agent/test-cases \
  -H "X-Agent-Key: qf_..."
```

Optional filters: `?status=passed&test_plan_id=uuid`

---

## Complete Workflow

Here's the recommended end-to-end flow for any AI agent:

```
Step 1: Initialize
  PUT  /api/agent/project         ← populate app profile
  POST /api/agent/sessions        ← start session
  POST /api/agent/test-plans      ← create plan

Step 2: Submit Test Cases
  POST /api/agent/test-cases      ← batch submit (up to 100)

Step 3: Submit Execution Results
  POST /api/agent/executions      ← batch submit with proof
  (repeat for each test run)

Step 4: Check Progress
  GET  /api/agent/summary         ← pass rate, pending reviews

Step 5: Human Review (in QAForge UI)
  → Test Plan → Executions tab → Review each result
  → Checkpoints → Create sign-off checkpoint
```

---

## Helper CLI (qaforge.py)

The `scripts/qaforge_client.py` helper wraps all API calls into simple CLI commands:

```bash
# Initialize session + plan + app profile
python scripts/qaforge.py init --plan "Feature Tests"

# Run smoke tests and auto-submit
python scripts/qaforge.py run-smoke

# Run pytest and auto-submit
python scripts/qaforge.py run-pytest backend/tests/

# Submit test cases manually
python scripts/qaforge.py submit-cases < test_cases.json

# Submit execution results manually
python scripts/qaforge.py submit-results < results.json

# Check summary
python scripts/qaforge.py summary
```

The helper:
- Reads `QAFORGE_API_URL` and `QAFORGE_AGENT_KEY` from `.env`
- Auto-detects app profile from project structure
- Parses test output (smoke tests, pytest JSON) into QAForge format
- Saves session state to `.qaforge_session.json`

---

## CLAUDE.md Template

Add this to any project's `CLAUDE.md` to enable QAForge integration:

```markdown
## QAForge Integration (Test Documentation)

QAForge is our test documentation platform. When asked to "document testing",
"use QAForge", or "track test results", use the QAForge helper.

**Setup:** `QAFORGE_API_URL` and `QAFORGE_AGENT_KEY` are in `.env`.

**Workflow:**
\```bash
# 1. Initialize (creates session + plan + populates app profile)
python scripts/qaforge.py init --plan "Feature Name Tests"

# 2. Run smoke tests and auto-submit
python scripts/qaforge.py run-smoke

# 3. Run pytest and auto-submit
python scripts/qaforge.py run-pytest backend/tests/

# 4. Check summary
python scripts/qaforge.py summary
\```

**For custom test submissions:**
\```bash
python scripts/qaforge.py submit-cases <<'EOF'
[{"test_case_id": "TC-FEAT-001", "title": "...", "category": "functional",
  "priority": "P1", "execution_type": "api", "expected_result": "200 OK"}]
EOF
\```

**Test Case Fields:**
- `test_case_id`: Human-readable (TC-AUTH-001)
- `category`: functional | integration | regression | smoke | e2e
- `priority`: P1 | P2 | P3 | P4
- `execution_type`: api | ui | sql | manual

**Proof Artifact Types:**
- `api_response` — HTTP request/response
- `test_output` — stdout/stderr
- `screenshot` — Base64 image
- `log` — Application logs
- `query_result` — SQL results
- `data_comparison` — Source vs target
```

---

## Integration Examples

### Example 1: Orbit (Full-Stack Web App)

Orbit is a FastAPI + React recruitment platform with 140+ smoke tests.

**Integration steps:**
1. Created project in QAForge, generated agent key
2. Added `QAFORGE_API_URL` and `QAFORGE_AGENT_KEY` to `.env`
3. Copied `qaforge.py` helper to `scripts/`
4. Added QAForge section to `CLAUDE.md`

**Typical usage during vibe coding:**
```bash
# After building a feature
python scripts/qaforge.py init --plan "Auth Enhancement Tests"
python scripts/qaforge.py run-smoke     # 82 test cases + results auto-submitted
python scripts/qaforge.py summary       # 97.6% pass rate
```

**Result:** 82 test cases with proof artifacts visible in QAForge UI, ready for human QA review.

### Example 2: Reltio MDM Pipeline (Future Pattern)

For master data management projects, test cases focus on match rules, survivorship, and data quality.

```bash
python scripts/qaforge.py init --plan "Reltio Match Rule Validation"
python scripts/qaforge.py submit-cases <<'EOF'
[
  {
    "test_case_id": "TC-MDM-001",
    "title": "Exact match on SSN + DOB",
    "category": "functional",
    "priority": "P1",
    "execution_type": "api",
    "domain_tags": ["mdm", "match-rules", "reltio"],
    "expected_result": "Entities merged with survivorship applied"
  }
]
EOF
```

**Proof artifacts for MDM:**
- `data_comparison` — source vs merged entity
- `dq_scorecard` — data quality scores
- `query_result` — match/merge audit trail

### Example 3: Databricks Pipeline (Future Pattern)

For data engineering projects, test cases validate ETL transformations and data quality.

```bash
python scripts/qaforge.py init --plan "Databricks ETL Validation"
python scripts/qaforge.py submit-cases <<'EOF'
[
  {
    "test_case_id": "TC-ETL-001",
    "title": "Bronze to Silver dedup removes exact duplicates",
    "category": "integration",
    "priority": "P1",
    "execution_type": "sql",
    "domain_tags": ["databricks", "etl", "dedup"],
    "expected_result": "Row count reduced by duplicate count, no data loss"
  }
]
EOF
```

**Proof artifacts for Databricks:**
- `query_result` — row counts before/after
- `data_comparison` — sample data comparison
- `log` — Spark job execution logs

### Example 4: RAG / GenAI Pipeline (Future Pattern)

For AI/GenAI projects, test cases validate retrieval quality, response accuracy, and guardrails.

```bash
python scripts/qaforge.py init --plan "RAG Pipeline Validation"
python scripts/qaforge.py submit-cases <<'EOF'
[
  {
    "test_case_id": "TC-RAG-001",
    "title": "Retrieval returns relevant chunks for domain query",
    "category": "functional",
    "priority": "P1",
    "execution_type": "api",
    "domain_tags": ["rag", "retrieval", "embeddings"],
    "expected_result": "Top-3 chunks contain answer to query with >0.8 similarity"
  }
]
EOF
```

---

## Project Types & Framework Provisions

QAForge is designed to support multiple project types. Each type has different testing patterns:

| Project Type | Key Test Patterns | Primary Proof Types |
|-------------|-------------------|---------------------|
| **Web App** (Orbit, Pulse) | API smoke, CRUD, auth, UI flows | api_response, test_output, screenshot |
| **MDM Pipeline** (Reltio, Semarchy) | Match rules, survivorship, DQ | data_comparison, dq_scorecard, query_result |
| **Data Engineering** (Databricks, Snowflake) | ETL validation, row counts, transforms | query_result, data_comparison, log |
| **RAG / GenAI** | Retrieval quality, response accuracy, guardrails | api_response, data_comparison, log |
| **Agent Workflow** | Multi-step agent execution, tool usage | api_response, log, code_diff |

The `domain` and `sub_domain` fields on projects, plus `domain_tags` on test cases, enable domain-specific AI generation and knowledge base patterns.

---

## Error Handling

| Status | Meaning | Resolution |
|--------|---------|------------|
| 401 | Invalid or missing `X-Agent-Key` | Check key in `.env`, regenerate if needed |
| 400 | Invalid request body | Check required fields, validate UUIDs |
| 409 | Duplicate `test_case_id` | Each test_case_id must be unique within project |
| 404 | Resource not found | Check test_case_id, plan_id, session_id |
| 429 | Rate limited | Wait and retry (200 req/min limit) |

---

## Self-Signed Certificate Note

If QAForge uses self-signed certificates (default for Docker), use `-k` with curl or `verify=False` in Python requests. The helper script handles this automatically.
