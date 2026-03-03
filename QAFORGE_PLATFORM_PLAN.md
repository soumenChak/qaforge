# QAForge Platform Redesign — The Agent Orchestration Hub
## Strategic Plan + Competitive Research | March 2026

---

# PART 1: COMPETITIVE LANDSCAPE RESEARCH

## The Market ($1B → $3.8B by 2032)

| Category | Key Players | What They Do | Pricing |
|----------|-------------|--------------|---------|
| **AI Test Generation** | TestSprite ($8.1M raised, 35K users), ACCELQ Autopilot, Virtuoso QA | Generate tests from requirements, self-healing, MCP IDE integration | TestSprite: credit-based; ACCELQ: enterprise |
| **Test Management** | Testomat.io (MCP-native), TestRail, qTest, Zephyr | Organize cases/plans/executions, traceability, CI/CD | Testomat: from $30/mo; TestRail: $40+/user/mo |
| **Code Quality Gates** | Qodo ($60.1% F1 on benchmarks), SonarQube, DeepSource | Enforce coding standards on PRs, auto-discover rules, quality gates | Qodo: enterprise; SonarQube: free + paid |
| **MCP Orchestration** | TestSprite MCP, Playwright MCP, Workato Enterprise MCP | Connect AI agents to testing infrastructure from IDE | Various |
| **No-Code Automation** | Katalon (Gartner Visionary), TestRigor, BlinqIO | Plain English test creation, cross-platform | Katalon: free + $208/mo |

## What Competitors Do Well

- **TestSprite**: IDE-native MCP integration (Cursor/Windsurf → test engine). Boosted AI code pass rates from 42% → 93%. Strong developer experience.
- **ACCELQ Autopilot**: True agentic automation — discovers scenarios, generates executable tests, self-heals. 65% reduction in test creation time reported.
- **Qodo**: Rules System auto-discovers coding standards from codebases. Their CEO's thesis aligns with ours: "Engineering standards shouldn't be scattered across docs."
- **Testomat.io**: MCP-native Jira AI agent. Good for agile teams. Multi-framework support (Playwright, Cypress, Jest, etc.).

## What NO ONE Does — QAForge's 5 Unique Differentiators

**No competitor combines all five of these:**

### 1. Domain-Specific Enterprise Test Generation
- Competitors generate generic API/UI tests
- QAForge generates multi-step MDM tests (Snowflake SQL + Reltio UI + count reconciliation) and DE tests (Oracle→Databricks migration with embedded SQL)
- This is deep domain knowledge, not generic "write a test for this endpoint"

### 2. Framework-as-Knowledge Encoding
- Qodo discovers rules from CODE (syntax, patterns in PRs)
- QAForge encodes ARCHITECTURAL standards from FRAMEWORKS (CLAUDE.md anti-patterns, build patterns, compliance rules)
- Different level: Qodo validates code quality, QAForge validates that the APP follows the FRAMEWORK

### 3. Agent → QAForge → MCP Server Orchestration
- TestSprite: IDE → own test engine (closed loop)
- QAForge: ANY agent (Claude/Codex) → QAForge hub → ANY MCP server (Reltio, Snowflake, Databricks, Salesforce)
- Open orchestration vs closed ecosystem

### 4. Multi-Framework Scaffolding + Test Intelligence
- FG Framework templates (app, DE, MDM, RAG, agent) each come with CLAUDE.md + qaforge.py
- When you scaffold a new app, you get both the framework AND pre-loaded domain test patterns in KB
- No one bundles app scaffolding with test intelligence

### 5. Senior Engineer Knowledge → Platform → Juniors Guided
- The explicit goal: "My knowledge is not staying in my head"
- Anti-patterns, build patterns, compliance rules — encoded once, enforced by agents forever
- Closest: Qodo's Rules System, but QAForge does it at the ARCHITECTURE level, not just code syntax

## Honest Gaps vs Competitors

| Gap | Competitor Advantage | QAForge Mitigation |
|-----|---------------------|-------------------|
| UI test execution | ACCELQ self-healing, TestSprite cloud sandbox | Defer to MCP servers (Playwright MCP) — orchestrate, don't compete |
| Scale/maturity | TestSprite: 35K users, $8.1M | FreshGravity internal first, then open |
| IDE integration | TestSprite MCP in Cursor/Windsurf | Claude Code CLI is the IDE — qaforge.py IS the integration |
| Self-healing tests | ACCELQ, Katalon | Not in scope — QAForge is the brain, MCP servers are the hands |

## Market Position Statement

> **QAForge is NOT another test automation tool.** It's the **knowledge-encoded orchestration hub** where:
> - Engineering judgment is encoded (frameworks → KB → agents)
> - AI agents generate domain-specific enterprise tests (not generic API tests)
> - Humans review (not write) test cases
> - Execution flows through MCP servers to any platform (Reltio, Snowflake, Salesforce)
> - Every FreshGravity app is born with test intelligence built-in

**Tagline options:**
- "Where Engineering Judgment Is Tested"
- "The Brain Behind Your Testing Agents"
- "Enterprise QA Intelligence — Agent-Executed, Human-Reviewed"

---

# PART 2: PLATFORM VISION

## Three Pillars

```
+-------------------------------------------------------------+
|                    QAForge Platform                          |
|                                                             |
|  +--------------+  +--------------+  +------------------+   |
|  |  1. TESTING   |  | 2. FRAMEWORK |  | 3. AGENT         |  |
|  |  ENGINE       |  |    VALIDATOR  |  |    ORCHESTRATOR  |  |
|  |              |  |              |  |                  |   |
|  | Agent creates |  | App follows  |  | QAForge sends    |  |
|  | test cases,  |  | FG Framework |  | test execution   |  |
|  | human reviews|  | patterns?    |  | to MCP servers:  |  |
|  |              |  | Anti-patterns|  | Reltio, Snowflake|  |
|  |              |  | detected?    |  | Databricks, etc. |  |
|  +--------------+  +--------------+  +------------------+   |
|                                                             |
|  Knowledge Base: Engineering judgment encoded — not in      |
|  anyone's head, but in the platform. Juniors guided by      |
|  frameworks + QAForge without senior handholding.           |
+-------------------------------------------------------------+
```

**Core principle:** Agent = executor. Human = reviewer. QAForge = the orchestration hub.

## Agent Mesh Flow

```
Claude Code / Codex / Any AI Agent
    | (generates tests, submits results)
    v
  QAForge (Knowledge Hub + Review Platform)
    | (orchestrates execution via MCP)
    v
  +---------+----------+-----------+------------+
  | Reltio  |Snowflake |Databricks | Salesforce | ... any SaaS with MCP
  | MCP     | MCP      | MCP       | MCP        |
  +---------+----------+-----------+------------+
```

## Multiple Frameworks, One QAForge

```
FG Framework Templates
|-- app/       [READY]   FastAPI + React + PostgreSQL
|-- de/        [PLANNED] Data Engineering (Databricks/Snowflake/Airflow)
|-- mdm/       [PLANNED] Master Data Management (Reltio/Semarchy)
|-- rag/       [PLANNED] RAG Pipeline (vector DB + retrieval)
+-- agent/     [PLANNED] Agent Workflow (multi-step, tools, memory)

Each framework template encodes:
- CLAUDE.md with anti-patterns + build patterns
- qaforge.py for testing integration
- Domain-specific knowledge that QAForge KB stores + validates against
```

---

# PART 3: SPRINT 1 — IMPLEMENTATION PLAN

## What This Sprint Delivers

1. Role system (admin + engineer)
2. Feature audit (deprecate templates, simplify checkpoints)
3. Missing CRUD (delete everywhere)
4. UI cleanup (sidebar, dashboard, KB, users)
5. Review Queue (new page — the core human reviewer workflow)
6. Admin Project Wizard (admin creates project → gives agent key to engineer)
7. Framework compliance vision (KB structure to encode framework patterns)
8. qaforge.py as universal companion (portable, self-bootstrapping)

## Feature Audit

### KEEP & ENHANCE

| Feature | Why | Changes |
|---------|-----|---------|
| **Projects** | Core entity | Admin creates, assigns engineers. Agent keys auto-generated. |
| **Test Cases** | Agent generates, human reviews | Bulk approve/reject. Show generation source. |
| **Test Plans** | Organizes execution rounds | Add delete. Simplify — lightweight grouping. |
| **Executions + Proofs** | Agent submits, human reviews | Review queue. Batch approve/reject. |
| **Knowledge Base** | Encodes engineering judgment | Framework patterns stored here. Auto-learn. Usage tracking. |
| **Agent API** | Primary interface for all agents | Already comprehensive. No changes. |
| **Settings** | Admin controls LLM + system | Keep as-is. |
| **Users** | Admin manages reviewers | Expand roles: admin + engineer. |
| **Dashboard** | Overview | Redesign for reviewer workflow. |

### DEPRECATE

| Feature | Why | Action |
|---------|-----|--------|
| **Templates** (export format config) | Agent-driven generation + KB makes manual templates redundant | Remove from sidebar. Keep API for backward compat. |
| **Formal Checkpoints** | Overly bureaucratic. Review Queue replaces this. | Remove Checkpoints tab. Keep DB table. |
| **App Profile auto-discovery** | Premature. Focus on agent flow. | Hide from UI. Keep endpoints for future. |

### ADD (NEW)

| Feature | Why | Description |
|---------|-----|-------------|
| **Review Queue** | Core reviewer workflow | Pending TCs + execution results. Bulk approve/reject. Filter by project/priority. |
| **Admin Project Wizard** | Admin-driven project creation | Create project → auto-generate agent key → copy instructions for engineer's Claude. |
| **Agent Activity Feed** | What are agents doing? | Dashboard widget: recent agent actions with timestamps. |
| **Framework Pattern KB entries** | Encode framework standards | KB entry_type: framework_pattern, anti_pattern, compliance_rule. |

## Part 1: Role System — Admin + Engineer

**Current roles:** admin, lead, tester
**New roles:** admin, engineer

**Access matrix:**

| Resource | Admin | Engineer |
|----------|-------|----------|
| Create projects | Yes | No |
| View projects | All | Assigned only |
| Manage users | Yes | No |
| LLM settings | Yes | No |
| Review test cases | All | Own projects |
| Review executions | All | Own projects |
| Manage KB | All | Own domain |
| Generate agent keys | Yes | No |

## Part 2: Missing CRUD — Delete Everywhere

- Test Plans: Add delete button + ConfirmModal in frontend
- Execution Results: Add DELETE endpoint + frontend button
- Verify existing deletes: Projects, Requirements, Knowledge entries, Test cases

## Part 3: UI Cleanup

**New Sidebar:**
```
Dashboard              (HomeIcon)
Projects               (FolderIcon)
Review Queue           (ClipboardDocumentCheckIcon) -- NEW
Knowledge Base         (BookOpenIcon)
--- Admin Only ---
Settings               (CogIcon)
Users                  (UsersIcon)
```

**Dashboard Redesign:**
- 4 stat cards: Pending Reviews | Active Projects | Pass Rate | KB Entries
- Agent Activity Feed (last 10 agent actions)
- Pending Reviews summary with "Go to Review Queue" link
- My Projects grid

## Part 4: Review Queue (New Page)

Two tabs:

**Tab 1: Test Case Reviews**
- Table: Project | TC ID | Title | Priority | Category | Source Agent | Generated At
- Bulk select → Approve / Reject / Request Changes
- Expandable rows with full test case details
- "Approve All" quick action

**Tab 2: Execution Reviews**
- Table: Project | TC | Status | Actual Result | Duration | Agent | Executed At
- Bulk select → Approve / Reject with comment
- Expandable rows with ProofViewer inline
- "Approve All Passed" quick action

## Part 5: Admin Project Wizard

Wizard steps:
1. Name, Domain, Sub-domain, Description
2. Assign Engineer(s) — multi-select from users list
3. Auto-generate agent key → show onboarding instructions with copy-to-clipboard

## Part 6: Knowledge Base — Framework Pattern Encoding

**Expanded KB entry_type enum:**

| entry_type | Example | Purpose |
|------------|---------|---------|
| framework_pattern | "All DB access goes through database_pg.py" | Encodes FG Framework standards |
| anti_pattern | "NEVER use html.escape()" | What NOT to do (from CLAUDE.md) |
| compliance_rule | "Every route must call audit_log()" | Checkable rules for validation |
| pattern | "Reltio entity load: Snowflake → Reltio API → reconciliation" | Domain testing patterns (existing) |
| defect | "ZeroDivision on gravity score" | Known defects (existing) |
| best_practice | "Use flag_modified() for JSONB updates" | Best practices (existing) |
| test_case | Reference test cases from Excel imports | Sample TCs (existing) |

**15 seed entries** from FG Framework's CLAUDE.md anti-patterns and build patterns.

## Part 7: qaforge.py — Universal Companion

- Copy latest qaforge.py to FG Framework templates
- Update FG Framework CLAUDE.md with QAForge Integration section
- Auto-install openpyxl, self-contained, clear error messages

---

# PART 4: FILES CHANGED

| # | File | Action | Change |
|---|------|--------|--------|
| 1 | backend/dependencies.py | Modify | VALID_ROLES, is_admin/is_engineer helpers |
| 2 | backend/routes/auth.py | Modify | Default role → engineer |
| 3 | backend/routes/users.py | Modify | Role validation |
| 4 | backend/routes/projects.py | Modify | Auto-generate key, assigned_users, engineer scoping |
| 5 | backend/routes/test_plans.py | Modify | Add execution delete endpoint |
| 6 | backend/routes/knowledge.py | Modify | New entry_types, framework pattern seeds |
| 7 | backend/db_models.py | Modify | assigned_users on Project, entry_type expansion |
| 8 | backend/models.py | Modify | Role validation, assigned_users, new entry_types |
| 9 | backend/migrations/versions/ | Create | Migration: assigned_users + role update |
| 10 | backend/routes/reviews.py | Create | GET /reviews/pending aggregation endpoint |
| 11 | frontend/src/App.js | Modify | Remove templates route, add review queue route |
| 12 | frontend/src/components/Layout.js | Modify | New sidebar, admin section |
| 13 | frontend/src/contexts/AuthContext.js | Modify | isEngineer |
| 14 | frontend/src/pages/Dashboard.js | Modify | Reviewer-focused redesign |
| 15 | frontend/src/pages/ReviewQueue.js | Create | New review queue page |
| 16 | frontend/src/pages/Projects.js | Modify | Wizard modal with agent key |
| 17 | frontend/src/pages/TestPlans.js | Modify | Delete button |
| 18 | frontend/src/pages/TestPlanDetail.js | Modify | Remove checkpoints tab, add delete |
| 19 | frontend/src/pages/KnowledgeBase.js | Modify | Cleanup, new entry_type badges |
| 20 | frontend/src/pages/Users.js | Modify | Admin/engineer roles |
| 21 | frontend/src/services/api.js | Modify | Review queue API, project wizard |
| 22 | FG Framework templates/app/scripts/qaforge.py | Update | Latest CLI |
| 23 | FG Framework templates/app/CLAUDE.md | Modify | QAForge integration docs |

---

# PART 5: FUTURE ROADMAP

## Sprint 2: MCP Execution Orchestration
- QAForge as MCP client — connect to Reltio MCP, Snowflake, Databricks
- Test execution engine sends steps to appropriate MCP server based on step_type
- Flow: Agent generates TC → QAForge stores → Human approves → QAForge executes via MCP → Results + proofs auto-captured

## Sprint 3: Framework Compliance Engine
- QAForge scans project code against compliance_rule KB entries
- Generates "Framework Compliance Score" (0-100)
- Flags violations: "Route X uses raw SQL — should use database_pg.py"
- New agent: ComplianceAgent — reviews code against framework patterns

## Sprint 4: New Framework Templates
- DE template (Databricks/Snowflake/Airflow scaffold + CLAUDE.md)
- MDM template (Reltio/Semarchy scaffold + CLAUDE.md)
- RAG template (vector DB + retrieval + CLAUDE.md)
- Each template auto-seeds QAForge KB with domain-specific patterns

## Sprint 5: Multi-Tenant & Team
- Organizations / teams
- Shared KB across team
- Cross-project analytics
- Agent performance metrics (which agents generate better TCs?)

---

# PART 6: VERIFICATION CHECKLIST

1. **Role system:** Engineer login → sees only assigned projects, no Settings/Users in sidebar
2. **Delete:** Delete test plan from UI → confirm modal → plan deleted → test cases unlinked
3. **Review Queue:** Agent generates TCs → appear in Review Queue → bulk approve → status updates
4. **Dashboard:** Shows pending review count, agent activity feed, own projects
5. **Project Wizard:** Admin creates project → agent key generated → copy instructions shown
6. **KB framework patterns:** Seed endpoint populates anti-patterns from CLAUDE.md → visible in KB with new badges
7. **FG Framework:** `bash init.sh test-app app` → qaforge.py included → `setup` works → `status` shows connected
8. **End-to-end:** New Claude session → `qaforge.py setup` → generate tests → results appear in QAForge UI → engineer reviews in Review Queue

---

*Document generated: March 3, 2026*
*Platform: QAForge v2.0 — FreshGravity*
