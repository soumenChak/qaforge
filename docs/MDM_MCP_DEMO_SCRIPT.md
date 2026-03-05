# QAForge + Reltio MCP — Live Demo Script

**Duration:** ~15 minutes | **Presenter:** Run from Claude Code with both MCP servers connected

---

## Pre-Demo Setup

```bash
# Verify MCP servers are up
curl -sk -N --max-time 3 https://13.233.36.18:8080/qaforge-mcp/sse | head -2
curl -sk -N --max-time 3 https://13.233.36.18:8080/mcp/sse | head -2

# Connect Claude Code to both servers
claude mcp add qaforge "https://13.233.36.18:8080/qaforge-mcp/sse" --transport sse
claude mcp add reltio "https://13.233.36.18:8080/mcp/sse" --transport sse

# Start Claude Code (use NODE_TLS_REJECT_UNAUTHORIZED=0 for self-signed certs)
NODE_TLS_REJECT_UNAUTHORIZED=0 claude
```

### Project Keys (copy these)
| Project | Agent Key |
|---------|-----------|
| **Reltio MDM E2E Demo** | `qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG` |
| **Orbit Recruitment App** | `qf_nUMyzZ6Q6zF1OyG7nXGxKz9zPQQIecmWp1ro2_dN_qCjHG3KM3AbSeM_4LGtZK19` |

### Demo Data (pre-loaded)
| Data | Count | Source |
|------|-------|--------|
| Reltio test cases | 36 | Pre-seeded + generated |
| Reltio requirements | 27 | BRD extraction |
| Reltio test plans | 2 | Sprint 1 Regression + Sprint 2 Search & Audit |
| Reltio executions | 28 | 22 passed, 4 failed (78.6%) |
| MDM framework | 1 | 6 sections, 30+ test areas |
| MDM KB entries | 49 | 43 test cases + patterns |
| Orbit test cases | 8 | Auth, CRUD, AI Interview |
| Orbit executions | 6 | 5 passed, 1 failed (83.3%) |

---

## Demo 1: Dynamic Project Switching (2 min)

**What it shows:** One MCP server, multiple projects — switch instantly

### Prompt 1.1
```
Connect to the Reltio MDM E2E Demo project with key qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG
```

### Prompt 1.2
```
Show me the connection status — which project am I on?
```

**Expected:** Shows "Reltio MDM E2E Demo" with domain mdm/reltio

### Prompt 1.3
```
Now connect to the Orbit Recruitment App with key qf_nUMyzZ6Q6zF1OyG7nXGxKz9zPQQIecmWp1ro2_dN_qCjHG3KM3AbSeM_4LGtZK19
```

### Prompt 1.4
```
Show me the summary for this project
```

**Expected:** Shows Orbit with 8 test cases, 83.3% pass rate

**Talking point:** "Zero restart, zero config file changes — just say 'connect' and you're on a different project."

---

## Demo 2: Full Quality Dashboard (2 min)

**What it shows:** Instant project health check across all dimensions

### Prompt 2.1
```
Connect to Reltio MDM E2E Demo with key qf_pu9XD6ePDdq6-BBbfOCmPdap5yjP7zD_pJDrQUqz4eROeVP4IElBOiErfPZEwidG and then give me a complete quality report — show the project summary, list all test plans with their pass rates, check framework coverage for MDM domain, and show KB stats
```

**Expected output (4 tool calls):**
- Summary: 36 test cases, 28 executions, 78.6% pass rate
- Test Plans: 2 plans (Sprint 1 Regression @ 80%, Sprint 2 Search & Audit @ 67%)
- Framework: 6 sections covering Entity Lifecycle, Match & Merge, Crosswalks, Data Quality, Relations, Security
- KB Stats: 49 entries (43 test cases + 5 patterns + 1 framework)

**Talking point:** "One natural language sentence triggers 4+ MCP tool calls and returns a comprehensive quality dashboard."

---

## Demo 3: Framework Coverage Gap Analysis (3 min)

**What it shows:** Enterprise compliance checking

### Prompt 3.1
```
Check framework coverage for the MDM domain and tell me exactly which framework sections have no test cases — then generate test cases to fill the top 3 gaps
```

**Expected:**
- Shows 6 framework sections with coverage percentages
- Identifies gaps (Relations & Interactions @ 50%)
- Generates 3+ test cases targeting the gaps

**Talking point:** "Automated compliance — frameworks define what MUST be tested, QAForge checks what IS tested, AI fills the gaps."

---

## Demo 4: End-to-End Flow — Requirements to Execution (5 min)

**What it shows:** The complete QA lifecycle in natural language

### Prompt 4.1 — Extract requirements
```
List all requirements for this project and tell me which ones don't have test cases yet
```

**Expected:** Shows 27 requirements grouped by category (data_quality, match_merge, integration, etc.)

### Prompt 4.2 — Generate tests for gaps
```
Generate 3 test cases specifically for the uncovered requirements around search and audit trail
```

**Expected:** Generates TC-SEARCH-*, TC-AUDIT-* with MDM-specific assertions

### Prompt 4.3 — Create test plan
```
Create a test plan called "Sprint 3 - Relations & Audit" of type smoke and add the newly generated test cases to it
```

**Expected:** Plan created with test cases assigned

### Prompt 4.4 — Submit results (simulate execution)
```
Submit execution results for the test cases in the Sprint 3 plan — mark the first 2 as passed with 150ms duration and the last one as failed with actual result "Graph traversal timeout on 4-hop query". Add proof artifacts for each.
```

**Expected:** 3 execution results submitted with proof artifacts

### Prompt 4.5 — Check outcome
```
Show me the summary for the project now — what changed?
```

**Expected:** Updated pass rate, new test cases visible, execution count increased

**Talking point:** "Complete QA lifecycle from requirements to evidence — all through natural language, zero UI clicks needed."

---

## Demo 5: Cross-MCP — Reltio + QAForge Together (3 min)

**What it shows:** Test a LIVE Reltio MDM system and auto-document results in QAForge

### Prompt 5.1
```
Execute a live smoke test: use Reltio MCP to check the health status of the Reltio server, then search for entities of type Organization. Take the results and submit them to QAForge as a test execution with the API response as proof artifacts.
```

**Expected:**
1. Calls Reltio MCP `health_check_tool` → returns server status
2. Calls Reltio MCP `search_entities_tool` → returns Organization entities with URIs
3. Calls QAForge MCP `submit_results` → documents the execution with proof

**Talking point:** "TWO MCP servers working together — Reltio for live testing, QAForge for documentation. The AI is the test engineer."

---

## Demo 6: AI Test Generation from Frameworks (optional, 2 min)

**What it shows:** Domain-specific enterprise test generation powered by frameworks + KB

### Prompt 6.1
```
Show me the MDM testing framework first, then generate 5 test cases for the MDM domain focusing on data quality and match/merge validation
```

**Expected:**
- Shows framework with 6 mandatory test areas
- Generates 5 enterprise-grade test cases using:
  - Framework standards (mandatory areas)
  - KB reference patterns (40+ existing test cases)
  - Project requirements (27 BRD requirements)

**Talking point:** "The AI reads the framework standards, fetches KB reference patterns, and generates enterprise-grade test cases — not generic ones."

---

## Demo 7: Knowledge Base Learning Loop (optional, 2 min)

**What it shows:** The system gets smarter over time

### Prompt 7.1
```
Show me KB stats for MDM domain, then upload the best 3 test cases from this project as reference samples so future test generation is even better
```

**Expected:**
- Shows: 49 KB entries (43 test cases, 5 patterns, 1 framework)
- Uploads 3 high-quality test cases as reference samples
- Stats increase to 52 entries

**Talking point:** "Continuous learning — good test cases feed back into the KB, improving quality for every future project."

---

## Key Talking Points

| Point | Detail |
|-------|--------|
| **No codebase needed** | QA users connect Claude Code to MCP servers and work entirely in natural language |
| **65 tools orchestrated** | 20 QAForge tools + 45 Reltio tools, all orchestrated by one AI |
| **Framework-driven** | Not random test generation — enterprise standards baked in |
| **Evidence-based** | Every test has proof artifacts, every result is reviewable |
| **Multi-project** | One server, unlimited projects, switch with a single command |
| **Cross-MCP** | Test live systems + document results in one flow |
| **Learning system** | Good test cases feed back into KB, improving future generation |

---

## Suggested Demo Order (15-min version)

| # | Demo | Duration | Impact |
|---|------|----------|--------|
| 1 | Dynamic Project Switching | 2 min | Shows new feature, instant switching |
| 2 | Full Quality Dashboard | 2 min | Shows breadth — one command, full visibility |
| 3 | Framework Coverage Gap Analysis | 3 min | Shows enterprise value — compliance |
| 4 | End-to-End Flow | 5 min | Shows depth — complete lifecycle |
| 5 | Cross-MCP Live Testing | 3 min | Shows the "wow" — live Reltio + QAForge |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| MCP connection refused | `ssh VM 'cd /opt/qaforge && docker compose ps'` — restart if needed |
| SSL cert error | Add `NODE_TLS_REJECT_UNAUTHORIZED=0` before `claude` command |
| Agent key invalid | Regenerate in QAForge UI → Project → Agent API Key → Generate |
| Reltio MCP 502 | `ssh VM 'docker network connect qaforge_default reltio_mcp_server'` |
| Slow generation | LLM API latency — wait ~10-15 seconds for test generation |

---

## QAForge UI (for showing results after demo)

- **URL:** https://13.233.36.18:8080
- **Login:** admin@freshgravity.com / admin123
- **Navigate:** Projects → Reltio MDM E2E Demo → Test Plans / Test Cases / Executions
