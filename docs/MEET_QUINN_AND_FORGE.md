# Meet Quinn & Forge

> *"You don't need to become an AI expert. You just need the right partners."*

---

## Breathe. You're Going to Be Fine.

New AI tool every Tuesday. New framework every Thursday. New "this changes everything" LinkedIn post every 47 minutes. MCP, RAG, agents, copilots, vibe coding — if you're a QA engineer, a developer, or a team lead, you're not just doing your job anymore. You're also supposed to be an AI strategist, a prompt engineer, and somehow keep up with a field that reinvents itself monthly.

Here's the honest truth: **you don't need to keep up with any of that.**

You need two things: someone to handle quality, and someone to handle code. You make the decisions. They do the work.

Meet Quinn and Forge.

---

## Who Are They?

**Quinn** is your AI QA Engineer. She manages testing, generates test cases, executes them against live systems, debugs failures, and documents everything — all through conversation. She doesn't need access to your source code. She doesn't need you to learn a new UI. You just talk to her.

**Forge** is your AI Developer. He has the full codebase. He builds dashboards from live data, shows you what's under the hood, and writes code that Quinn's test cases validate. When new requirements come in, Forge builds. When things break, Quinn catches it.

They're a team. They share the same platform — **QAForge** — but see it from different angles. Quinn sees quality. Forge sees architecture. Together, they cover everything.

---

## The Before & After

| | Before (The Old Way) | After (Quinn & Forge) |
|---|---|---|
| **Test creation** | 2 hours clicking through TestRail fields | "Quinn, generate 10 security tests from the requirements" — done in 30 seconds |
| **Debugging a failure** | File Jira ticket → wait for standup → developer context-switches → 3-day round trip | "Quinn, what's wrong with TC-MCP-004?" → she fixes it and re-runs in 60 seconds |
| **Cross-system testing** | Postman for APIs, separate MCP client, manual copy-paste of results | Quinn hits both in one conversation, files results with proof artifacts |
| **Test documentation** | 78% of QA time (Capgemini World Quality Report) | Automatic — every test Quinn runs is documented with evidence |
| **Keeping up with AI** | Read 15 newsletters, attend 3 webinars, still confused | Quinn and Forge absorb the upgrades. LLMs improve → they improve. You do nothing. |
| **Getting started** | 6-month transformation project + professional services | `./scripts/setup-qa-workspace.sh` → talk to Quinn |

---

## Why This Matters

### The $40 Billion Problem

The test management market is worth over $40 billion. It's dominated by tools designed in 2005 — TestRail, Zephyr, qTest. Good tools for their era. But QA engineers still spend **78% of their time on documentation and test management** — not actual testing.

Then AI arrived. Every platform bolted on a copilot. "AI-assisted test generation!" But it's still the same old click-through UI with a ChatGPT sidebar. That's not transformation. That's a renovation on a building that needs to be rebuilt.

### What's Different Here

QAForge isn't AI-assisted. It's **AI-native** — built from the ground up for a world where AI agents do the work and humans make the decisions.

- **76 tools** across 2 MCP servers (Model Context Protocol — the open standard that lets AI talk to systems)
- **Zero** mainstream test platforms support MCP today. QAForge is the first.
- **Two built-in personas** — not chatbots, not copilots. Full-stack AI partners that understand your domain.
- **Knowledge Base** with domain patterns that make every AI interaction enterprise-grade, not generic.
- **Self-service** — no professional services engagement needed. Quinn and Forge are your team.

---

## What Quinn Can Do

Quinn is the QA persona. She works from a clean workspace — no source code, no IDE, no build tools. Just conversation.

| Capability | How It Works |
|-----------|-------------|
| **Connect to any project** | One agent key, instant access to all project data |
| **Pull live dashboards** | Test counts, pass rates, execution history — in seconds |
| **Test live systems** | Hit real APIs, real MCP servers, real databases — record everything |
| **Generate test cases** | AI-powered, backed by domain Knowledge Base — not generic ChatGPT |
| **Debug failing tests** | Inspect a test case, see why it failed, fix it on the spot |
| **Re-execute tests** | Trigger execution, poll results — no developer needed |
| **Track coverage** | Check test cases against enterprise testing frameworks |
| **Build the Knowledge Base** | Add patterns, best practices — Quinn gets smarter over time |

Quinn doesn't need you to be an AI expert. She doesn't need you to write prompts. You describe what you want in plain English, and she does the rest.

---

## What Forge Can Do

Forge is the developer persona. He has the full codebase and the engineering context.

| Capability | How It Works |
|-----------|-------------|
| **Build from live data** | Pull API data and generate dashboards, reports, artifacts on the fly |
| **Show the guardrails** | Read the actual code — domain agents, KB injection, prompt pipelines |
| **Explain architecture** | Walk through the 6 layers of context that make AI generation enterprise-grade |
| **Add new features** | New MCP tools, new API endpoints, new execution templates |
| **Self-test the platform** | QAForge tests itself — 18 test cases for its own API and tools |
| **Deploy changes** | Build, push, deploy — with the full engineering context |

Forge doesn't replace your developers. He amplifies them. When new requirements come in, Forge builds. When Quinn finds a bug, Forge fixes the root cause.

---

## What Does a Conversation Actually Look Like?

### Quinn debugging a failing test:

```
You:    "Quinn, TC-MCP-004 failed in the last run. Can you look at it?"

Quinn:  Looking at TC-MCP-004 — "Find Potential Duplicate Matches via MCP"...

        The test step calls find_potential_matches_tool with just entity_type,
        but this tool requires search_type and filter params too. The expected
        result also doesn't match the actual response format.

        I'll fix both:
        - Adding search_type: "score" and filter: "0,100" to the tool params
        - Updating expected result to match the actual response structure

        ✓ Test case updated. Re-executing the test plan now...

        Run complete: TC-MCP-004 — PASSED (2.4s)
        Proof artifact attached with the actual MCP response.

You:    "Nice. Can you add what you learned to the Knowledge Base?"

Quinn:  Done — created KB entry "find_potential_matches_tool requires search_type
        parameter" under MDM/reltio patterns. Next time I generate test cases
        for this tool, I'll get the params right from the start.
```

### Forge building from live data:

```
You:    "Forge, build me a dashboard from the live project data"

Forge:  On it. Pulling from 3 endpoints in parallel...

        [calls GET /api/agent/summary]
        [calls GET /api/agent/test-plans]
        [calls GET /api/agent/kb-stats]

        Got it. 25 test cases, 100% pass rate, 96 KB entries across 5 domains.
        Building the dashboard now...

        ✓ Dashboard generated at /tmp/qaforge-dashboard.html
        [opens in browser]

        Built from live API data — same numbers you see in the QAForge UI.
        Quinn sees this through conversation. I just built it from code.
        Same data, different superpowers.
```

No special syntax. No prompt engineering. Just plain English.

---

## The Magic: They Get Better Without You Doing Anything

Quinn and Forge are powered by Large Language Models — Claude, GPT, Groq, or even local models via Ollama. As these models improve (and they improve fast), Quinn and Forge automatically get smarter.

- **Better test generation** — as LLMs understand more domain context
- **Better debugging** — as reasoning capabilities improve
- **Better code** — as Forge gets access to newer model capabilities
- **Your Knowledge Base compounds** — every pattern Quinn learns, every test Forge validates, makes the next interaction better

You don't need to retrain anything. You don't need to upgrade a model. The foundation improves underneath you, and Quinn and Forge pass that improvement directly to your workflow.

---

## Who Is This For?

**If you're overwhelmed by the pace of AI change** — this is literally why Quinn and Forge exist. You don't need to understand MCP, RAG, prompt engineering, or whatever new acronym dropped this week. They understand it so you don't have to. And when the next breakthrough lands, they absorb it automatically. Your job is to make quality decisions. Their job is everything else.

**If you're a QA engineer** tired of spending 80% of your time on documentation instead of actual testing — Quinn gives you that time back. She documents as she tests. You review and decide.

**If you're a developer** building with AI and hoping someone is testing properly — Forge validates your architecture while Quinn stress-tests your APIs. Full cycle, no gaps.

**If you're a team lead** who's been asked "what's our AI strategy for QA?" and doesn't have a good answer yet — this is the answer. No consultants. No 6-month transformation. No budget request that dies in committee. One setup script, two personas, done.

---

## First of Its Kind

Let's be clear about what this is:

- **First** MCP-native test management platform
- **First** platform with built-in QA and Developer AI personas
- **First** test platform where QA engineers work entirely through conversation — no UI clicks required
- **First** platform that tests itself using its own tools (we eat our own dogfood)

This isn't a feature added to an existing product. This is a new category.

---

## Get Started

### As Quinn (QA Engineer — No Code Needed)

```bash
# 1. Set up Quinn's workspace
./scripts/setup-qa-workspace.sh

# 2. Start Claude Code from Quinn's workspace
cd ~/qa-workspace && claude

# 3. Talk to Quinn
> "Hey Quinn, connect to my project and show me the dashboard"
```

### As Forge (Developer — Full Codebase)

```bash
# 1. Clone QAForge
git clone <repo-url> && cd qaforge

# 2. Start Claude Code from the repo
claude

# 3. Talk to Forge
> "Hey Forge, show me the architecture and build a live dashboard"
```

### Both at Once (The Full Experience)

Open two terminals. Quinn on the left, Forge on the right. Same platform, two perspectives. That's QAForge.

---

## Built By

**Soumen C.** — who, upon discovering that a $40 billion industry was still running on software older than most interns, did what any reasonable person would do: ignored the 18-month roadmap everyone said was necessary and just... built the whole thing.

A full-stack AI-native quality platform. Two AI personas. 76 MCP tools. A Knowledge Base with 96 domain patterns. An execution engine that talks to external MCP servers. A platform that tests itself. And documentation that you're currently reading, which was also written with the help of his own tools.

Was it a bit ambitious for one person? Absolutely. Did that stop him? Clearly not.

Quinn and Forge are the result — two AI partners that exist so you never have to sit through a "how to use AI in QA" webinar again. They absorb the complexity. They stay current. They handle the 78% of your time that used to go to documentation. You just make the decisions.

No consultants required. No transformation roadmap. No professional services engagement where someone charges you $300/hour to configure a tool from 2005.

Just install, connect, and talk. Quinn and Forge take it from there.

Welcome to QAForge.
