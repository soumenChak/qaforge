# QAForge Testing Guide & Runbook

**How to use QAForge while vibe coding or testing any application**

*Built by FreshGravity — Where Quality Is Engineered*

---

## Table of Contents

1. [What Is QAForge?](#1-what-is-qaforge)
2. [The Big Picture — How It Works](#2-the-big-picture--how-it-works)
3. [Prerequisites](#3-prerequisites)
4. [Step 1: Set Up Your Project in QAForge](#4-step-1-set-up-your-project-in-qaforge)
5. [Step 2: Configure Your App](#5-step-2-configure-your-app)
6. [Step 3: Add QAForge to Your CLAUDE.md](#6-step-3-add-qaforge-to-your-claudemd)
7. [Step 4: Run Tests & Submit to QAForge](#7-step-4-run-tests--submit-to-qaforge)
8. [Step 5: View Results in QAForge UI](#8-step-5-view-results-in-qaforge-ui)
9. [Step 6: Human QA Review](#9-step-6-human-qa-review)
10. [Complete Walkthrough — Real Example](#10-complete-walkthrough--real-example)
11. [CLI Reference — qaforge.py](#11-cli-reference--qaforge-py)
12. [Custom Test Submissions](#12-custom-test-submissions)
13. [Proof Artifact Types](#13-proof-artifact-types)
14. [Agent API Quick Reference](#14-agent-api-quick-reference)
15. [Integration Patterns by Project Type](#15-integration-patterns-by-project-type)
16. [Troubleshooting](#16-troubleshooting)
17. [FAQ](#17-faq)
18. [Testing the QAForge Platform Itself](#18-testing-the-qaforge-platform-itself)

---

## 1. What Is QAForge?

QAForge is an **Enterprise Test Documentation Platform**. When you vibe code with AI agents (Claude Code, Codex, Gemini CLI), every test your agent runs produces results — but those results disappear into terminal output. QAForge captures, structures, and tracks that evidence so human QA can validate it.

**The problem QAForge solves:**
- ❌ Test results disappear in terminal output
- ❌ No structured format for AI-generated test evidence
- ❌ No human QA checkpoint before sign-off
- ❌ No traceability from requirement → test case → result

**What QAForge provides:**
- ✅ Agents test, QAForge records — structured test cases with proof
- ✅ Human QA reviews AI-generated evidence at checkpoints
- ✅ Full audit trail — who tested what, when, with what result
- ✅ Pass/fail dashboards, coverage analysis, traceability matrix

---

## 2. The Big Picture — How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                        YOUR VIBE CODING SESSION                     │
│                                                                     │
│  You + AI Agent (Claude Code)                                       │
│    │                                                                │
│    ├─ Build features                                                │
│    ├─ Write tests                                                   │
│    ├─ Run tests ← results captured by qaforge.py                    │
│    │                                                                │
│    └─ "use QAForge to document testing"                             │
│         │                                                           │
│         ▼                                                           │
│    qaforge.py CLI                                                   │
│         │                                                           │
│         ├─ init         → Creates session + test plan               │
│         ├─ run-smoke    → Runs smoke tests, auto-submits results    │
│         ├─ run-pytest   → Runs pytest, auto-submits results         │
│         └─ summary      → Shows pass rate + stats                   │
│                                                                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS (X-Agent-Key)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         QAFORGE PLATFORM                            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐    │
│  │ Test Cases   │  │ Executions   │  │ Proof Artifacts        │    │
│  │ TC-AUTH-001  │  │ passed/failed│  │ API responses, logs,   │    │
│  │ TC-RBAC-002  │  │ + duration   │  │ screenshots, SQL       │    │
│  └──────────────┘  └──────────────┘  └────────────────────────┘    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │ Human QA Review                                          │      │
│  │ → Review test cases → Validate evidence → Sign off       │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

**Key concept:** You don't change how you test. You just add QAForge as a documentation layer. Your tests run exactly as before — QAForge captures the evidence.

---

## 3. Prerequisites

### Two Ways to Use QAForge

| Method | Best For | What You Need |
|--------|----------|---------------|
| **Claude Code + MCP** (Recommended) | QA users, no codebase needed | Node.js 18+, Anthropic API key |
| **CLI Script (`qaforge.py`)** | Developers with codebase access | Python 3.8+, `requests` package |

### Option A: Claude Code + MCP (QA Users — No Code Needed)

This is the **recommended** approach for QA users. You talk naturally to Claude, and it uses QAForge MCP tools behind the scenes.

**Claude Code CLI:**

```bash
# 1. Install Claude Code
npm install -g @anthropic-ai/claude-code

# 2. Add QAForge MCP server
claude mcp add qaforge --transport sse \
  --url "https://qaforge.freshgravity.net/qaforge-mcp/sse"

# 3. (Optional) Add Reltio MCP server for MDM testing
claude mcp add reltio --transport sse \
  --url "https://qaforge.freshgravity.net/mcp/sse"

# 4. Start Claude Code from any directory
mkdir -p ~/qa-workspace && cd ~/qa-workspace
claude
```

**Claude Desktop App:**

Add MCP servers to your config file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

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

Restart Claude Desktop — tools are available immediately.

**Then just talk:**
- *"Show me all test cases"*
- *"Generate 10 security test cases from the requirements"*
- *"Create a smoke test plan and add all P1 test cases"*
- *"What's our current test coverage?"*
- *"Search Reltio for entities where FirstName starts with John"*

See [MCP Operations Guide](MCP_OPERATIONS_GUIDE.md) for full setup details.

### Option B: CLI Script (Developers with Codebase)

| Requirement | Details |
|-------------|---------|
| **QAForge instance** | Running at `https://qaforge.freshgravity.net` (e.g., `https://qaforge.freshgravity.net`) |
| **Login credentials** | Default: `admin@freshgravity.com` / `admin123` |
| **Python 3.8+** | For the `qaforge.py` CLI helper |
| **`requests` package** | `pip install requests` |
| **Your project** | Any app with tests (smoke tests, pytest, or custom) |

### QAForge Instance Access

If QAForge is already deployed (e.g., on your team's VM), you just need:
1. The URL: `https://qaforge.freshgravity.net`
2. Login credentials
3. A project + agent key (created in Step 1)

If you need to deploy QAForge itself, see the [QAForge Runbook](RUNBOOK.md).

---

## 4. Step 1: Set Up Your Project in QAForge

### 4.1 Log In to QAForge UI

1. Open `https://qaforge.freshgravity.net` in your browser
2. Log in with your credentials (valid Let's Encrypt SSL — no certificate warnings)

### 4.2 Create a Project

1. Click **Projects** in the sidebar
2. Click **New Project**
3. Fill in:
   - **Name:** Your project name (e.g., "Pulse", "Orbit", "MyApp")
   - **Domain:** Select the closest match (e.g., "AI", "Data Engineering", "MDM")
   - **Sub-domain:** More specific (e.g., "GenAI", "Databricks", "Reltio")
   - **Description:** Brief description of what's being tested
4. Click **Create**

### 4.3 Generate an Agent API Key

This is the key your AI agent uses to submit test results.

1. On the project page, find **Agent API Key** section
2. Click **Generate**
3. **⚠️ IMPORTANT:** Copy the key immediately — it's shown **only once**
   - Format: `qf_<random_string>`
   - Example: `qf_a1b2c3d4e5f6...`
4. Store it securely (you'll add it to your project's `.env` file)

**Key facts:**
- One key per project
- Key is SHA-256 hashed before storage (never stored in plaintext)
- Key is project-scoped — can only access its own project's data
- Rotate via: **Agent API Key → Regenerate** (old key stops working immediately)

---

## 5. Step 2: Configure Your App

### 5.1 Add Environment Variables

Add these two lines to your project's `.env` file:

```bash
# QAForge Integration
QAFORGE_API_URL=https://qaforge.freshgravity.net/api
QAFORGE_AGENT_KEY=qf_your_key_here
```

Replace `13.233.36.18` with your QAForge host, and `qf_your_key_here` with the key from Step 1.

### 5.2 Copy the Helper Script

The `qaforge.py` CLI helper wraps all QAForge API calls into simple commands.

**Option A — If using FreshGravity Framework:**

The script is already at `scripts/qaforge.py` in your scaffolded project. Nothing to copy.

**Option B — If adding QAForge to an existing project:**

```bash
# Create scripts directory if it doesn't exist
mkdir -p scripts

# Copy from QAForge installation
cp /path/to/qaforge/scripts/qaforge_client.py scripts/qaforge.py

# Or from the FreshGravity Framework
cp /path/to/freshgravity-framework/templates/app/scripts/qaforge.py scripts/qaforge.py
```

**Option C — Download from QAForge docs:**

The script is self-contained (~637 lines). It requires only Python 3.8+ and the `requests` package.

### 5.3 Verify Setup

```bash
# Test the connection
python scripts/qaforge.py summary
```

If configured correctly, you'll see project stats (or an empty summary for new projects). If you get an error, check:
- `QAFORGE_API_URL` is reachable
- `QAFORGE_AGENT_KEY` is correct
- `requests` is installed: `pip install requests`

---

## 6. Step 3: Add QAForge to Your CLAUDE.md

This is what makes the magic happen. When your AI agent reads `CLAUDE.md`, it knows how to use QAForge automatically.

Add this section to your project's `CLAUDE.md`:

```markdown
## QAForge Integration (Test Documentation)

QAForge is our test documentation platform. When asked to "document testing",
"use QAForge", or "track test results", use the QAForge helper.

**Setup:** `QAFORGE_API_URL` and `QAFORGE_AGENT_KEY` are in `.env`.

**Workflow:**
```bash
# 1. Initialize (creates session + plan + populates app profile)
python scripts/qaforge.py init --plan "Feature Name Tests"

# 2. Run smoke tests and auto-submit
python scripts/qaforge.py run-smoke

# 3. Run pytest and auto-submit
python scripts/qaforge.py run-pytest backend/tests/

# 4. Check summary
python scripts/qaforge.py summary
```

**For custom test submissions:**
```bash
python scripts/qaforge.py submit-cases <<'EOF'
[{"test_case_id": "TC-FEAT-001", "title": "...", "category": "functional",
  "priority": "P1", "execution_type": "api", "expected_result": "200 OK"}]
EOF
```

**Proof Artifact Types:**
- `api_response` — HTTP request/response
- `test_output` — stdout/stderr
- `screenshot` — Base64 image
- `log` — Application logs
- `query_result` — SQL results
- `data_comparison` — Source vs target
```

Now when you tell your AI agent *"use QAForge to document testing"*, it will follow this workflow automatically.

---

## 7. Step 4: Run Tests & Submit to QAForge

### The Core Workflow (3 commands)

```bash
# 1. Initialize — creates a QAForge session and test plan
python scripts/qaforge.py init --plan "My Feature Tests"

# 2. Run your tests — picks up test results and submits them
python scripts/qaforge.py run-smoke          # For smoke tests
# OR
python scripts/qaforge.py run-pytest backend/tests/  # For pytest

# 3. Check how you did
python scripts/qaforge.py summary
```

That's it. Three commands. Everything else is automatic.

### What Happens Under the Hood

**`init`** does three things:
1. Scans your project structure and populates the QAForge app profile (tech stack, routes, test infrastructure)
2. Creates an **agent session** (tracks who submitted what)
3. Creates a **test plan** (groups your test cases and results)
4. Saves session state to `.qaforge_session.json`

**`run-smoke`** does:
1. Runs `tests/smoke_test.py` against your app
2. Parses every `✅` and `❌` line from stdout
3. Converts each into a structured test case + execution result
4. Attaches proof artifacts (test output with section/status/detail)
5. Submits everything to QAForge in batch
6. Prints a summary: total / passed / failed / pass rate

**`run-pytest`** does:
1. Runs pytest with `--json-report`
2. Parses the JSON report into test cases + execution results
3. Submits with proof artifacts
4. Prints summary

**`summary`** fetches:
- Total test cases and executions
- Pass/fail breakdown
- Pass rate percentage
- Pending review count

---

## 8. Step 5: View Results in QAForge UI

After submitting test results, open the QAForge UI to see everything.

### Dashboard

The dashboard shows:
- Total projects with test activity
- Overall pass rate across projects
- Recent test submissions
- Pending reviews count

### Project View

1. Click **Projects** → select your project
2. You'll see:
   - **Test Cases** tab — all submitted test cases with status
   - **Requirements** tab — linked requirements (if any)
   - **Test Plans** tab — your test plans with execution stats

### Test Plan Detail

1. Click on a test plan (e.g., "Sprint 1 Auth Tests")
2. Tabs available:
   - **Test Cases** — list of test cases in this plan
   - **Executions** — execution results with pass/fail + duration
   - **Checkpoints** — human QA review gates
   - **Traceability** — requirement → test case matrix
   - **Summary** — executive stats (pass rate, coverage score)

### Viewing Proof Artifacts

1. Go to **Executions** tab in a test plan
2. Click on any execution result
3. Expand **Proof Artifacts** — you'll see:
   - API responses (status codes, headers, body)
   - Test output (stdout with pass/fail)
   - Screenshots (if UI tests)
   - Query results (if SQL tests)

---

## 9. Step 6: Human QA Review

QAForge is designed for **human-in-the-loop quality assurance**. AI agents submit evidence; humans validate it.

### Review Workflow

1. **Navigate** to the test plan's **Executions** tab
2. Each execution has a **Review Status**: `pending` / `approved` / `rejected`
3. Click on an execution to review:
   - Read the test case description
   - Check the actual result vs expected result
   - Examine proof artifacts
   - Click **Approve** or **Reject** (with comments)

### Creating Checkpoints

Checkpoints are formal QA gates:

1. Go to test plan → **Checkpoints** tab
2. Click **Create Checkpoint**
3. Select type:
   - `test_case_review` — Review quality of test cases themselves
   - `execution_review` — Review test execution results
   - `sign_off` — Final approval for release
4. Assign a reviewer
5. Status tracks: `pending` → `approved` / `rejected` / `needs_rework`

### Sign-Off Flow

```
Agent submits test cases + results
    ↓
QA Lead reviews executions (execution_review checkpoint)
    ↓
QA Lead reviews test case quality (test_case_review checkpoint)
    ↓
QA Manager signs off (sign_off checkpoint)
    ↓
Release approved ✅
```

---

## 10. Complete Walkthrough — Real Example

Here's the exact workflow demonstrated with the FreshGravity Framework, testing a freshly scaffolded app called "fgtest" on a VM.

### Step 1: Scaffold the App

```bash
# On VM (13.233.36.18)
cd /opt/freshgravity-framework
bash init.sh fgtest app
cd /home/ubuntu/fgtest
```

### Step 2: Start the App

```bash
docker compose up -d
# Wait for all 4 containers: db, redis, backend, frontend
docker compose ps   # all should show "healthy"
```

### Step 3: Set Up QAForge Integration

```bash
# .env already has QAFORGE_API_URL and QAFORGE_AGENT_KEY
# (added during scaffold or manually)
cat .env | grep QAFORGE
# QAFORGE_API_URL=https://qaforge.freshgravity.net/api
# QAFORGE_AGENT_KEY=qf_abc123...
```

### Step 4: Initialize QAForge Session

```bash
python scripts/qaforge.py init --plan "fgtest Framework Validation"
```

Output:
```
Initializing QAForge session...
  Populating app profile...
  Plan: <plan-uuid> (fgtest Framework Validation)
  Session: <session-uuid>
  Project: <project-uuid>
  Saved to .qaforge_session.json
```

### Step 5: Run Smoke Tests & Submit

```bash
APP_BASE_URL=http://localhost:8000 python scripts/qaforge.py run-smoke
```

Output:
```
Running smoke tests against http://localhost:8000...

── Section 1: Health Check ──
  ✅ /api/health returns JSON with status ok
  ✅ /health returns 200

── Section 2: Auth ──
  ✅ POST /api/auth/login with valid creds returns JWT
  ✅ POST /api/auth/login with bad password returns 401
  ✅ GET /api/auth/me returns current user
  ...

── Section 6: Validation ──
  ✅ Login with empty email returns 422
  ✅ Login with empty password returns 422

Submitting 29 test cases to QAForge...
  OK: 29 test cases submitted
Submitting 29 execution results...
  OK: 29 results submitted

  Total: 29  |  Passed: 29  |  Failed: 0  |  Rate: 100.0%
```

### Step 6: Check Summary

```bash
python scripts/qaforge.py summary
```

Output:
```json
{
  "project_name": "fgtest",
  "total_test_cases": 29,
  "by_status": {"passed": 29, "failed": 0},
  "total_executions": 29,
  "passed": 29,
  "failed": 0,
  "pending_review": 29,
  "pass_rate": 100.0
}
```

### Step 7: Review in QAForge UI

1. Open `https://qaforge.freshgravity.net`
2. Login → Projects → "fgtest"
3. Test Plans → "fgtest Framework Validation"
4. Executions tab → 29 results, all green ✅
5. Click any result → see proof artifacts with test output

**Done.** 29 test cases documented with proof, ready for human QA review.

---

## 11. CLI Reference — qaforge.py

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `init` | Create session + test plan | `python scripts/qaforge.py init --plan "Auth Tests"` |
| `run-smoke` | Run smoke tests, auto-submit | `python scripts/qaforge.py run-smoke` |
| `run-pytest` | Run pytest, auto-submit | `python scripts/qaforge.py run-pytest backend/tests/` |
| `submit-cases` | Submit test cases (JSON) | `python scripts/qaforge.py submit-cases < cases.json` |
| `submit-results` | Submit execution results (JSON) | `python scripts/qaforge.py submit-results < results.json` |
| `summary` | Get pass/fail summary | `python scripts/qaforge.py summary` |

### `init` Options

| Flag | Description | Default |
|------|-------------|---------|
| `--plan "name"` | Test plan name | `Test Run <timestamp>` |
| `--type type` | Plan type: `sit`, `uat`, `regression`, `smoke`, `migration`, `custom` | `sit` |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `QAFORGE_API_URL` | ✅ | QAForge API URL (e.g., `https://qaforge.freshgravity.net/api`) |
| `QAFORGE_AGENT_KEY` | ✅ | Agent API key (e.g., `qf_abc123...`) |
| `APP_BASE_URL` | For `run-smoke` | App URL to test against (default: `http://localhost:8000`) |

### Session File

After `init`, the CLI saves state to `.qaforge_session.json`:

```json
{
  "session_id": "uuid",
  "project_id": "uuid",
  "plan_name": "Auth Tests",
  "plan_type": "sit",
  "plan_id": "uuid",
  "created_at": "2026-03-02T10:00:00Z"
}
```

All subsequent commands (`run-smoke`, `submit-cases`, etc.) read from this file. Add `.qaforge_session.json` to your `.gitignore`.

### Smoke Test Output Format

The `run-smoke` command parses test output that follows this format:

```
── Section 1: Health Check ──
  ✅ Test name here
  ❌ Test name here — error detail

── Section 2: Auth ──
  ✅ Another test
```

Each `✅`/`❌` line becomes a test case + execution result. Section headers become categories.

---

## 12. Custom Test Submissions

For tests that aren't smoke tests or pytest, you can submit structured JSON directly.

### Submit Test Cases

```bash
python scripts/qaforge.py submit-cases <<'EOF'
[
  {
    "test_case_id": "TC-AUTH-001",
    "title": "Login with valid credentials returns JWT",
    "description": "Verify POST /api/auth/login with valid email+password returns 200 with access_token",
    "preconditions": "Admin user exists: admin@company.com / admin123",
    "test_steps": [
      {"step_number": 1, "action": "POST /api/auth/login with {email, password}", "expected_result": "200 OK"},
      {"step_number": 2, "action": "Check response body", "expected_result": "Contains access_token and token_type=bearer"}
    ],
    "expected_result": "200 OK with valid JWT token",
    "priority": "P1",
    "category": "functional",
    "execution_type": "api",
    "domain_tags": ["auth", "jwt", "login"]
  }
]
EOF
```

### Submit Execution Results

After submitting test cases, use the returned UUIDs to submit execution results:

```bash
python scripts/qaforge.py submit-results <<'EOF'
[
  {
    "test_case_id": "<uuid-from-submit-cases>",
    "status": "passed",
    "actual_result": "200 OK — JWT token returned with correct claims",
    "duration_ms": 45,
    "environment": {"url": "http://localhost:8000", "method": "POST /api/auth/login"},
    "proof_artifacts": [
      {
        "proof_type": "api_response",
        "title": "Login response",
        "content": {
          "status_code": 200,
          "body": {"access_token": "eyJ...", "token_type": "bearer"}
        }
      }
    ]
  }
]
EOF
```

### Test Case Fields

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
| `domain_tags` | array | ❌ | `["auth", "rbac", "rest"]` |

### Execution Result Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `test_case_id` | UUID | ✅ | Internal UUID of the test case |
| `status` | string | ✅ | `passed` / `failed` / `error` / `skipped` / `blocked` |
| `actual_result` | string | ❌ | What actually happened |
| `duration_ms` | integer | ❌ | Execution time in milliseconds |
| `error_message` | string | ❌ | Error details (if failed) |
| `environment` | object | ❌ | `{url, method, headers, ...}` |
| `proof_artifacts` | array | ❌ | Evidence (see below) |

---

## 13. Proof Artifact Types

Every execution result can have proof artifacts — evidence that the test was actually run.

| Type | When to Use | Content Example |
|------|-------------|-----------------|
| `api_response` | HTTP request/response | `{status_code, headers, body}` |
| `test_output` | stdout/stderr from test run | Plain text or structured output |
| `screenshot` | Visual evidence (UI tests) | Base64-encoded image |
| `log` | Application or console logs | Log text |
| `query_result` | SQL query results | `{query, rows, columns}` |
| `data_comparison` | Source vs target comparison | `{source, target, diffs}` |
| `dq_scorecard` | Data quality scorecard | `{rules, scores, overall}` |
| `code_diff` | Code changes related to test | Diff text |
| `manual_note` | Human observation | Free-form text |

### Example: API Response Proof

```json
{
  "proof_type": "api_response",
  "title": "POST /api/auth/login",
  "content": {
    "request": {
      "method": "POST",
      "url": "http://localhost:8000/api/auth/login",
      "body": {"email": "admin@freshgravity.com", "password": "admin123"}
    },
    "response": {
      "status_code": 200,
      "body": {"access_token": "eyJ...", "token_type": "bearer"}
    }
  }
}
```

### Example: SQL Query Proof

```json
{
  "proof_type": "query_result",
  "title": "User count after registration",
  "content": {
    "query": "SELECT COUNT(*) FROM users WHERE is_active = true",
    "result": [{"count": 5}],
    "database": "myapp"
  }
}
```

### Example: Data Comparison Proof

```json
{
  "proof_type": "data_comparison",
  "title": "ETL row count validation",
  "content": {
    "source": {"table": "raw_orders", "count": 10000},
    "target": {"table": "clean_orders", "count": 9987},
    "diffs": {"dropped": 13, "reason": "null primary key"}
  }
}
```

---

## 14. Agent API Quick Reference

Base URL: `https://qaforge.freshgravity.net/api/agent`

All requests require: `X-Agent-Key: qf_...` header

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/agent/project` | Update project metadata / app profile |
| `POST` | `/agent/sessions` | Create agent session |
| `POST` | `/agent/test-plans` | Create test plan |
| `POST` | `/agent/test-cases` | Submit test cases (batch, up to 100) |
| `POST` | `/agent/executions?session_id=<uuid>` | Submit execution results with proof |
| `POST` | `/agent/executions/<id>/proof` | Add proof to existing execution |
| `GET` | `/agent/summary` | Get pass/fail summary |
| `GET` | `/agent/test-cases` | List test cases |

### Authentication

All agent API calls use a single header — no JWT, no login, no session:

```bash
curl -k https://qaforge:8080/api/agent/summary \
  -H "X-Agent-Key: qf_your_key_here"
```

### Complete cURL Example

```bash
# 1. Create session
curl -k -X POST https://qaforge:8080/api/agent/sessions \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "claude-code", "agent_version": "1.0"}'

# 2. Create plan
curl -k -X POST https://qaforge:8080/api/agent/test-plans \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{"name": "My Test Plan", "plan_type": "smoke"}'

# 3. Submit test cases
curl -k -X POST https://qaforge:8080/api/agent/test-cases \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{"test_plan_id": "<plan-uuid>", "test_cases": [{"test_case_id": "TC-001", "title": "Test", "expected_result": "Pass"}]}'

# 4. Submit execution results
curl -k -X POST "https://qaforge:8080/api/agent/executions?session_id=<session-uuid>" \
  -H "X-Agent-Key: qf_..." \
  -H "Content-Type: application/json" \
  -d '{"executions": [{"test_case_id": "<tc-uuid>", "status": "passed", "actual_result": "Passed"}]}'

# 5. Check summary
curl -k https://qaforge:8080/api/agent/summary \
  -H "X-Agent-Key: qf_..."
```

---

## 15. Integration Patterns by Project Type

### Web App (FastAPI + React, Next.js, etc.)

This is the primary pattern — smoke tests + pytest.

```bash
python scripts/qaforge.py init --plan "Sprint 1 Tests"
python scripts/qaforge.py run-smoke
python scripts/qaforge.py run-pytest backend/tests/
python scripts/qaforge.py summary
```

**Typical test cases:** API endpoints, auth flows, RBAC, CRUD, validation, health checks.
**Typical proof types:** `api_response`, `test_output`

### MDM Pipeline (Reltio, Semarchy)

For master data management, focus on match rules, survivorship, and data quality.

```bash
python scripts/qaforge.py init --plan "Reltio Match Rule Validation"
python scripts/qaforge.py submit-cases <<'EOF'
[
  {
    "test_case_id": "TC-MDM-001",
    "title": "Exact match on SSN + DOB merges entities",
    "category": "functional",
    "priority": "P1",
    "execution_type": "api",
    "domain_tags": ["mdm", "match-rules", "reltio"],
    "expected_result": "Entities merged with survivorship applied"
  }
]
EOF
```

**Typical proof types:** `data_comparison`, `dq_scorecard`, `query_result`

### Data Engineering (Databricks, Snowflake)

For ETL pipelines, validate transformations, row counts, and data quality.

```bash
python scripts/qaforge.py init --plan "ETL Pipeline Validation"
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

**Typical proof types:** `query_result`, `data_comparison`, `log`

### RAG / GenAI Pipeline

For AI/ML projects, validate retrieval quality, response accuracy, and guardrails.

```bash
python scripts/qaforge.py init --plan "RAG Pipeline QA"
python scripts/qaforge.py submit-cases <<'EOF'
[
  {
    "test_case_id": "TC-RAG-001",
    "title": "Retrieval returns relevant chunks for domain query",
    "category": "functional",
    "priority": "P1",
    "execution_type": "api",
    "domain_tags": ["rag", "retrieval", "embeddings"],
    "expected_result": "Top-3 chunks contain answer with >0.8 similarity"
  }
]
EOF
```

**Typical proof types:** `api_response`, `data_comparison`, `log`

### Agent Workflow (Agentic AI)

For multi-step agent workflows, validate tool usage, decision-making, and outcomes.

```bash
python scripts/qaforge.py init --plan "Agent Workflow Validation"
```

**Typical proof types:** `api_response`, `log`, `code_diff`

---

## 16. Troubleshooting

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `ERROR: Set QAFORGE_API_URL` | Missing env var | Add `QAFORGE_API_URL` to `.env` |
| `ERROR: Set QAFORGE_AGENT_KEY` | Missing env var | Add `QAFORGE_AGENT_KEY` to `.env` |
| `ERROR 401: Unauthorized` | Invalid agent key | Regenerate key in QAForge UI |
| `ERROR 409: Conflict` | Duplicate `test_case_id` | Use unique IDs or run a new `init` |
| `ERROR: No session. Run 'qaforge.py init' first` | Missing `.qaforge_session.json` | Run `python scripts/qaforge.py init` |
| `ConnectionError` | QAForge unreachable | Check URL, network, firewall |
| `SSLError` | Certificate issue | The CLI uses `verify=False` by default; ensure URL is correct |
| `ERROR: 'requests' package required` | Missing dependency | `pip install requests` |

### QAForge-Specific Issues

**Agent API returns 401:**
```bash
# Verify your key works
curl -k https://your-qaforge:8080/api/agent/summary \
  -H "X-Agent-Key: $QAFORGE_AGENT_KEY"
```
If 401: key is invalid or expired. Regenerate in QAForge UI: **Projects → Agent API Key → Regenerate**

**Test cases submitted but not visible in UI:**
- Check the correct project is selected
- Test cases are submitted under a test plan — check the plan, not just the project
- Try: QAForge UI → Projects → Your Project → Test Plans → Your Plan → Test Cases tab

**Smoke tests fail to parse:**
- Ensure your `smoke_test.py` uses the `✅`/`❌` output format
- Section headers must match: `── Section N: Name ──`
- The CLI falls back to raw output submission if parsing fails

**`run-pytest` shows "Could not parse JSON report":**
- Install pytest-json-report: `pip install pytest-json-report`
- The CLI falls back to raw output if JSON report isn't available

### Rate Limiting

QAForge has a 200 req/min rate limit. If you hit it:
- Wait 60 seconds and retry
- The `qaforge.py` CLI submits in batches, so this is rare
- For very large test suites (500+ tests), split into multiple runs

---

## 17. FAQ

**Q: Does QAForge replace my existing test framework?**
No. QAForge is a documentation layer. Your tests (pytest, smoke tests, Playwright, etc.) run exactly as before. QAForge captures and structures the evidence.

**Q: Can I use QAForge without an AI agent?**
Yes. Humans can submit test cases and results directly via the UI or API. The agent CLI is just a convenience.

**Q: Does QAForge run my tests?**
The `qaforge.py` CLI can run your smoke tests and pytest for you (`run-smoke`, `run-pytest`). But QAForge itself is a documentation platform — it stores results, not runs them.

**Q: How do I test multiple features in one session?**
Run `init` with a different `--plan` name for each feature:
```bash
python scripts/qaforge.py init --plan "Auth Feature Tests"
python scripts/qaforge.py run-smoke
python scripts/qaforge.py init --plan "Dashboard Feature Tests"
python scripts/qaforge.py run-smoke
```

**Q: Can multiple agents submit to the same project?**
Yes. Each agent creates its own session. All submissions are tagged with the agent name and session.

**Q: What if I regenerate the agent key?**
The old key stops working immediately. Update `QAFORGE_AGENT_KEY` in your `.env` file.

**Q: Does QAForge require special SSL handling?**
No. Production uses valid Let's Encrypt certificates at `qaforge.freshgravity.net`. For local development with self-signed certs, the `qaforge.py` CLI uses `verify=False` automatically.

**Q: Can I use QAForge with Codex or Gemini instead of Claude Code?**
Yes. QAForge is agent-agnostic. Add the CLAUDE.md section (adapted for your agent's instruction format) and use the same CLI.

**Q: Where should I put `qaforge.py`?**
Convention: `scripts/qaforge.py` in your project root. The CLI reads `.env` from the parent directory.

**Q: How do I export test results?**
QAForge UI has export functionality. Go to a test plan → use export options for Excel/Word/JSON formats.

---

## 18. Testing the QAForge Platform Itself

This section is for **admins deploying or maintaining QAForge** — it covers how to verify the platform is working correctly after deployment or updates.

### Post-Deploy Verification (`verify-mcp.sh`)

The verification script runs 6 automated checks and reports pass/fail with color-coded output:

```bash
cd /opt/qaforge
bash scripts/verify-mcp.sh
```

| Check | What it verifies |
|-------|-----------------|
| **1. Container health** | All 7 containers running (6 QAForge + Reltio MCP) |
| **2. Backend health** | `/api/health` returns 200 |
| **3. QAForge MCP SSE** | SSE path includes `/qaforge-mcp/messages/` prefix |
| **4. Reltio MCP SSE** | SSE path includes `/mcp/messages/` prefix (sub_filter working) |
| **5. Agent key** | `QAFORGE_MCP_AGENT_KEY` set and valid (API returns 200) |
| **6. Docker network** | Reltio MCP container on `qaforge_default` network |

Exit code = number of failures. If any check fails, the script shows the fix command.

### Full Stack Deployment Test (`full-deploy.sh`)

Orchestrates a complete deployment including Reltio MCP and runs `verify-mcp.sh` automatically:

```bash
bash scripts/full-deploy.sh                  # Full stack: QAForge + Reltio + verify
bash scripts/full-deploy.sh --qaforge-only   # Skip Reltio MCP
bash scripts/full-deploy.sh --skip-build     # Restart without rebuilding images
bash scripts/full-deploy.sh --skip-verify    # Skip post-deploy verification
```

### E2E Agent Workflow Test (`e2e_agent_test.sh`)

End-to-end test that exercises the complete agent workflow in 9 steps:

```bash
bash e2e_agent_test.sh
```

| Step | What it does |
|------|-------------|
| 1 | Login as admin, get JWT |
| 2 | Create a test project |
| 3 | Generate agent API key |
| 4 | Create a test plan |
| 5 | Start an agent session |
| 6 | Submit 3 test cases |
| 7 | Fetch test case UUIDs |
| 8 | Submit 2 execution results with proof artifacts |
| 9 | Check summary — verify counts and pass rates |

This creates real data in the database. Run it after a fresh deploy to confirm the full API pipeline works.

### MCP Test Execution (`mcp_executor.py`)

The MCP executor connects to MCP servers via SSE and runs structured test steps with assertions:

```bash
# Discover available tools from an MCP server
python scripts/qaforge.py discover --mcp-url https://host:8080/mcp/sse --save

# Execute a test plan (calls MCP tools, validates assertions, submits results)
python scripts/qaforge.py execute --plan "Smoke Test" --mcp-url https://host:8080/mcp/sse
```

Features:
- Connects to any MCP server over SSE transport
- Calls tools with specified parameters
- Validates assertions: `json_path`, `contains`, `not_empty`, `response_time_ms`
- Supports variable binding between steps: `{{step_1.parsed.field}}`
- Records results + proof artifacts back to QAForge — **zero LLM tokens**

### Health Check Quick Reference

| Service | Command | Expected |
|---------|---------|----------|
| Backend | `curl -k https://localhost:8080/api/health` | `{"status": "ok"}` |
| QAForge MCP | `curl -sk -N --max-time 3 https://localhost:8080/qaforge-mcp/sse` | `data: /qaforge-mcp/messages/...` |
| Reltio MCP | `curl -sk -N --max-time 3 https://localhost:8080/mcp/sse` | `data: /mcp/messages/...` |
| PostgreSQL | `docker compose exec db pg_isready -U qaforge` | `accepting connections` |
| Redis | `docker compose exec redis redis-cli ping` | `PONG` |
| ChromaDB | `curl http://localhost:8001/api/v1/heartbeat` | `{"nanosecond heartbeat": ...}` |
| All containers | `docker compose ps` | All show "healthy" |
| Full verification | `bash scripts/verify-mcp.sh` | `0 failed` |

---

## Quick Start Checklist

- [ ] QAForge instance running and accessible
- [ ] Project created in QAForge UI
- [ ] Agent key generated and copied
- [ ] `QAFORGE_API_URL` added to `.env`
- [ ] `QAFORGE_AGENT_KEY` added to `.env`
- [ ] `qaforge.py` copied to `scripts/`
- [ ] QAForge section added to `CLAUDE.md`
- [ ] `pip install requests` done
- [ ] Test with: `python scripts/qaforge.py summary`
- [ ] Run first test: `python scripts/qaforge.py init --plan "First Test" && python scripts/qaforge.py run-smoke`
- [ ] Verify in QAForge UI: results visible with proof artifacts
- [ ] Human QA: review and approve test results

---

*QAForge — Enterprise Test Documentation Platform*
*Built by FreshGravity — Where Quality Is Engineered*
