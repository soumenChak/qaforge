# QAForge — Live Demo Script

> **"What does QA look like when AI is the starting point?"**

**Duration:** 15-20 min | **Format:** Two terminals, two personas, one platform

---

## Before You Start

### Pre-Flight Check (run 2 min before demo)
```bash
# Verify both MCP servers are up
curl -s --max-time 3 https://qaforge.freshgravity.net/qaforge-mcp/sse | head -2
curl -s --max-time 3 https://qaforge.freshgravity.net/mcp/sse | head -2

# Verify API is healthy
curl -s https://qaforge.freshgravity.net/api/health
```

### Open Two Terminals Side by Side

| Terminal | Label | Command | What They See |
|----------|-------|---------|---------------|
| Left | **QA Engineer** | `cd ~/qa-workspace && claude` | MCP tools only. Zero code. |
| Right | **Developer** | `cd ~/Downloads/qaforge && claude` | Full codebase + MCP tools. |

### Keys (copy ready)
```
Reltio MDM:  qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG
Orbit App:   qf_nUMyzZ6Q6zF1OyG7nXGxKz9zPQQIecmWp1ro2_dN_qCjHG3KM3AbSeM_4LGtZK19
```

### QAForge UI (keep a browser tab ready)
- **URL:** https://qaforge.freshgravity.net
- **Login:** admin@freshgravity.com / admin123

---

## Opening — AI Does the Talking

Instead of you presenting slides, **let Claude open the demo**. Type `run the demo` in the QA terminal and Claude will:

1. Ask who the audience is
2. Deliver a tailored, hype-building intro (professional but with personality)
3. Explain what QAForge is and what it can do
4. Jump straight into the live demo

This is built into the QA persona's `CLAUDE.md`. The audience sees AI presenting itself — that's already a demo of what it can do.

For the developer terminal, Claude delivers a short transition ("You saw the QA side, now watch the dev side") and immediately starts building.

---

## Act 1: The QA Engineer (Left Terminal)

**Type:** `run the demo`

Claude will ask who the audience is, deliver a tailored intro, then proceed through all scenes automatically.

### Scene 1: One Sentence, Full Dashboard (2 min)

**Type in left terminal:**
```
Connect to the Reltio MDM E2E Demo project with key qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG and give me a complete quality report — project summary, all test plans with pass rates, framework coverage for MDM, and KB stats
```

**What happens:** Claude fires 4-5 MCP tool calls in parallel — `connect`, `get_summary`, `list_test_plans`, `check_framework_coverage`, `kb_stats` — and returns a formatted quality dashboard.

> **Say:** "One natural language sentence. Five tool calls. A complete quality dashboard with pass rates, compliance gaps, and knowledge base coverage. No API calls, no SQL queries, no UI clicks."

---

### Scene 2: Instant Project Switching (1 min)

**Type:**
```
Now switch to the Orbit Recruitment App with key qf_nUMyzZ6Q6zF1OyG7nXGxKz9zPQQIecmWp1ro2_dN_qCjHG3KM3AbSeM_4LGtZK19 and show me the summary
```

**What happens:** Instant switch. Different project, different stats.

**Type:**
```
Switch back to Reltio MDM E2E Demo with key qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG
```

> **Say:** "One MCP server. Unlimited projects. Switch with a sentence. No logout, no workspace change, no config files."

---

### Scene 3: Live Cross-System Testing (3 min) — THE WOW MOMENT

**Type:**
```
Run a live smoke test: use Reltio MCP to check the server health, then search for Organization entities, then check for potential duplicate matches. Record all results in QAForge with the API responses as proof artifacts.
```

**What happens:**
1. `health_check_tool` — Reltio server status
2. `search_entities_tool` — Returns live Organization entities with URIs
3. `find_potential_matches_tool` — Finds real duplicates in the MDM system
4. `submit_results` — Records pass/fail in QAForge
5. `add_proof` — Attaches raw API responses as evidence

> **Say:** "That was TWO MCP servers working together. Reltio MCP tested the live MDM system. QAForge MCP documented the results with proof artifacts. The AI orchestrated everything. No scripts. No Postman. No manual screenshots."

**Optional — show in UI:** Open browser, navigate to the project's executions tab. The results just submitted are there with proof artifacts attached.

---

### Scene 4: AI Test Generation from Domain Knowledge (2 min)

**Type:**
```
Generate 3 test cases for Reltio entity merge scenarios — cover happy path merge, survivorship conflict resolution, and cross-source merge with different trust scores
```

**What happens:** Claude calls `generate_test_cases` which uses:
- MDM framework standards (mandatory test areas)
- 43 Reltio-specific KB reference patterns
- 27 BRD requirements for context

> **Say:** "These aren't generic test cases. The AI pulled from our MDM framework, 43 reference patterns in the knowledge base, and the project's BRD requirements. The 50th project in this domain will generate better tests than the first — because the system learns."

---

### Scene 5: Guardrails in Action — Framework + KB Driving Generation (3 min)

**What it shows:** This is NOT ChatGPT generating generic tests. Frameworks and KB actively shape every test case.

**Type:**
```
Show me the MDM testing frameworks first, then show KB stats, then check framework coverage — I want to see what guardrails exist before we generate anything
```

**What happens:** Three calls — `get_frameworks`, `kb_stats`, `check_framework_coverage`. Shows the mandatory test areas, 91 KB entries, and current coverage gaps.

> **Say:** "These are the guardrails. The framework defines what MUST be tested. The knowledge base has 43 Reltio-specific patterns. Now watch what happens when we generate."

**Type:**
```
Now generate 2 test cases for MDM entity survivorship and golden record assembly — focus on cross-source conflict resolution with different trust scores
```

**What happens:** `generate_test_cases` returns test cases with:
- Reltio-specific terminology (survivorship, crosswalks, match scoring) — from the MDM framework
- Structured steps with domain assertions — from KB reference patterns
- Correct priority/category — aligned with framework standards

> **Say:** "Look at the output. Survivorship rules, trust score thresholds, cross-reference validation — this isn't generic. The AI was guided by the MDM framework AND 43 reference patterns from the knowledge base. If I asked ChatGPT to generate merge tests, I'd get basic HTTP assertions. QAForge generates tests that understand the domain. And the system gets smarter — every good test case feeds back into the KB for the next project."

---

### Scene 6: The "Aha" Moment (30 seconds)

**Type:**
```
Show me the source code of the QAForge backend — how does the execution engine work?
```

**What happens:** Claude says it has no access to any source code — only MCP tools.

> **Say:** "This QA engineer just managed 50 test cases, ran live tests against a production MDM system, generated compliance reports, and filled coverage gaps — without seeing a single line of code. That's role-based AI access. Now let me show you the other side."

---

## Act 2: The Developer (Right Terminal)

> "Same platform. Same MCP servers. But now I'm a developer with full codebase access."

### Scene 7: Code + MCP — Best of Both Worlds (2 min)

**Type in right terminal:**
```
Show me the test execution engine — how does it work? Read the main engine file.
```

**What happens:** Claude reads `backend/execution/engine.py` and explains the architecture.

> **Say:** "Same Claude. Same question the QA engineer asked. But now it can actually read the code and answer."

**Type:**
```
Connect to Reltio MDM E2E Demo with key qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG and show me the summary
```

> **Say:** "Developer sees the same quality data the QA engineer reported. Same dashboard, same pass rates. Plus the ability to dive into code and fix what's failing."

---

### Scene 8: Guardrails Under the Hood — The Code Behind the Magic (3 min)

**What it shows:** The developer can see HOW frameworks and KB shape generation — 6 layers of context injected into every AI prompt.

**Type:**
```
Show me the MDM agent domain knowledge and the prompt assembly in base_qa_agent.py — I want to see how frameworks and KB get injected into the AI prompt
```

**What happens:** Claude reads `backend/agents/mdm_agent.py` (domain knowledge block) and `backend/agents/base_qa_agent.py` (prompt template).

> **Say:** "The QA engineer just saw the OUTPUT of test generation. Now look at the INPUT. The MDM agent injects domain expertise — match rules, survivorship, data quality. The base agent assembles the prompt with domain patterns, KB context, and example test cases."

**Type:**
```
Now show me routes/test_cases.py around line 410 — where the knowledge base entries get queried and injected
```

**What happens:** Claude reads the KB injection pipeline — queries top 15 entries by usage count, formats them, injects as `=== KNOWLEDGE BASE REFERENCE ===`.

> **Say:** "Six layers of context in every prompt: system description, app profile, BRD requirements, reference test cases, top 15 KB patterns ranked by usage, and domain agent knowledge. ChatGPT gets one sentence. QAForge gets six layers of guardrails. That's why the output is enterprise-grade."

---

### Scene 9: Developer Fixes What QA Found (2 min)

**Type:**
```
Show me the cancel execution handler in TestPlanDetail.js and explain the recent bug fix where the UI wasn't updating after cancellation
```

**What happens:** Claude reads the React component, finds the fix, explains the state management issue.

> **Say:** "QA reported a bug through testing. Developer finds and fixes it in the same platform. The feedback loop is minutes, not days. No Jira ticket. No reproduction steps document. The AI has full context."

---

## Act 3: The Full Loop (Optional, 2 min)

> "Let me show you the complete cycle."

### Back to QA terminal (left):
```
List all test cases that failed in the last execution run and tell me what went wrong
```

### Switch to Dev terminal (right):
```
Look at the test case that failed and check if there's a code issue in the execution engine that could cause this
```

### Back to QA terminal (left):
```
Re-run the smoke test and verify the results
```

> **Say:** "QA finds the issue. Dev diagnoses and fixes. QA verifies. All through natural language. All in the same platform. All powered by the same AI."

---

## Closing (30 seconds — you talk)

> "QAForge isn't another test management tool with an AI chatbot bolted on. It's a platform where AI agents are first-class citizens. 69 tools across 2 MCP servers. Domain knowledge that compounds over time. Role-based access that just works. And the question we started with — 'what does QA look like when AI is the starting point?' — you just saw the answer."

---

## Quick Reference

### Timing Guide

| Scene | Duration | Persona | Impact Level |
|-------|----------|---------|-------------|
| Opening | 0:30 | You | Sets the frame |
| 1. Dashboard | 2:00 | QA | Breadth |
| 2. Project Switch | 1:00 | QA | Speed |
| 3. Live Testing | 3:00 | QA | **Peak wow** |
| 4. AI Generation | 2:00 | QA | Intelligence |
| 5. Guardrails | 3:00 | QA | **Not ChatGPT moment** |
| 6. No Code | 0:30 | QA | **Aha moment** |
| 7. Code + MCP | 2:00 | Dev | Contrast |
| 8. Guardrails Code | 3:00 | Dev | **Deep differentiator** |
| 9. Bug Fix | 2:00 | Dev | Full picture |
| 10. Full Loop | 2:00 | Both | Closure |
| Closing | 0:30 | You | Land the message |
| **Total** | **~21 min** | | |

### If Short on Time (10 min version)

Do scenes 1, 3, 5, 6, 7 only. Dashboard, live testing, guardrails, aha moment, developer contrast.

### If Medium (15 min version)

Do scenes 1, 3, 5, 6, 7, 8. Adds the code-level guardrails view for developers.

### If Very Short (2 min version)

```bash
# Left terminal — QA can test, can't code
cd ~/qa-workspace && claude -p "Connect to Reltio MDM E2E Demo with key qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG, give me a quality summary, then try to show me the source code of the backend"

# Right terminal — Dev can test AND code
cd ~/Downloads/qaforge && claude -p "Connect to Reltio MDM E2E Demo with key qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG, give me a quality summary, then show me the first 20 lines of backend/main.py"
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| MCP won't connect | `ssh ubuntu@13.233.36.18 'cd /opt/qaforge && docker compose ps'` — restart if down |
| "Connection refused" | Check: `curl -s https://qaforge.freshgravity.net/api/health` |
| Agent key rejected | Regenerate in UI: Project > Settings > Agent API Key |
| Reltio MCP 502 | `ssh ubuntu@13.233.36.18 'docker network connect qaforge_default reltio_mcp_server'` |
| Slow AI response | LLM latency — pause and say "the AI is analyzing..." (10-15s is normal) |
| Tool call fails | Say "let me retry that" — transient network issues resolve on retry |

---

## QA Workspace Setup (fresh machine)

```bash
mkdir -p ~/qa-workspace

cat > ~/qa-workspace/.mcp.json << 'EOF'
{
  "mcpServers": {
    "qaforge": { "type": "sse", "url": "https://qaforge.freshgravity.net/qaforge-mcp/sse" },
    "reltio": { "type": "sse", "url": "https://qaforge.freshgravity.net/mcp/sse" }
  }
}
EOF

cat > ~/qa-workspace/CLAUDE.md << 'EOF'
# QA Engineer Workspace — QAForge

You are a QA Engineer using QAForge and Reltio MCP to manage testing.
You do NOT have access to any source code. You work entirely through MCP tools.

## Available MCP Servers
- **QAForge MCP** (24 tools) — test management: connect, generate, execute, report
- **Reltio MCP** (45 tools) — live Reltio MDM: search, CRUD, merge, match, analytics

## Workflow
1. `connect` to a project with an agent key (ALWAYS first)
2. `get_summary` / `list_test_plans` / `list_test_cases` — explore
3. `generate_test_cases` — AI-powered test generation
4. Use Reltio MCP tools to run live tests
5. `submit_results` + `add_proof` — record results with evidence
6. `get_summary` / `kb_stats` — report
EOF
```
