# Open Source Readiness Checklist

Steps to prepare QAForge for team access and contributions.

## Security Audit

### Secrets Scan

- [ ] **No hardcoded secrets in code** — search for patterns:
  ```bash
  grep -rn "sk-ant\|sk-proj\|qf_\|password.*=" --include="*.py" --include="*.js" | grep -v node_modules | grep -v .env
  ```
- [ ] **`.env` is in `.gitignore`** (already done)
- [ ] **`.env.example` has no real values** (already done — uses placeholders)
- [ ] **No PEM/cert files committed** — `certs/` is in `.gitignore`
- [ ] **Agent keys in demo scripts** — remove or replace with `qf_YOUR_KEY_HERE`
- [ ] **SSH keys / server IPs** — remove from CLAUDE.md and demo scripts

### Code Security

- [ ] All user input sanitized via `bleach` (already in `dependencies.py`)
- [ ] SQL injection: using SQLAlchemy ORM (parameterized queries)
- [ ] XSS: React escapes by default; backend sanitizes HTML
- [ ] Auth: JWT for UI, `X-Agent-Key` for agent API (project-scoped)
- [ ] Rate limiting: Redis-backed per-IP and per-key limits
- [ ] CORS: configurable via `CORS_ORIGINS` env var

## Files to Clean Before Sharing

### Remove / Redact

| File | Action |
|------|--------|
| `CLAUDE.md` | Remove server IPs, SSH paths, agent keys, login credentials |
| `docs/MDM_MCP_DEMO_SCRIPT.md` | Remove real agent keys and server URLs |
| `~/qa-workspace/CLAUDE.md` | This is per-user, not in repo — no action needed |
| `.mcp.json` | Remove real MCP server URLs (use localhost examples) |

### Add

| File | Status |
|------|--------|
| `README.md` | Done |
| `CONTRIBUTING.md` | Done |
| `docs/SETUP_GUIDE.md` | Done |
| `docs/OPEN_SOURCE_CHECKLIST.md` | This file |
| `LICENSE` | TODO — choose license (Apache 2.0 recommended for enterprise open source) |

## Repository Setup

### Branch Protection (Bitbucket/GitHub)

- [ ] Protect `main` branch — require PR reviews
- [ ] Require at least 1 approval before merge
- [ ] Require passing CI checks (if CI exists)
- [ ] No force-push to `main`

### Access Control

- [ ] Create a team/org on Bitbucket or GitHub
- [ ] Add team members with appropriate roles:
  - **Admin**: repo settings, deploy keys
  - **Write**: push branches, merge PRs
  - **Read**: clone, view code
- [ ] Use SSH keys or personal access tokens (not shared passwords)

### CI/CD (Optional but Recommended)

```yaml
# Example GitHub Actions
name: QAForge CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker images
        run: docker compose build
      - name: Start services
        run: docker compose up -d
      - name: Health check
        run: |
          sleep 10
          curl -f http://localhost:8080/api/health
```

## Deployment Access

### Option A: Shared Server (Current)

- Server: AWS EC2 at `13.233.36.18`
- SSH key: `innovation-lab.pem` (distribute to authorized team members only)
- Code location: `/opt/qaforge`
- Deploy: `git pull && sudo docker compose build <service> && sudo docker compose up -d <service>`

### Option B: Individual Environments (Recommended for Dev)

Each contributor runs locally:
```bash
git clone <repo> && cd qaforge
cp .env.example .env
# Add their own LLM API key
docker compose up -d
```

## Team Onboarding Checklist (Per Person)

- [ ] Git access to the repo
- [ ] Copy of `.env.example` → `.env` with their own LLM API key
- [ ] `docker compose up -d` works locally
- [ ] Can create a project and generate an agent key
- [ ] Can connect Claude Code to their local MCP server
- [ ] Read CONTRIBUTING.md

## Knowledge Transfer

Key things new contributors should understand:

1. **Agent API pattern** — `X-Agent-Key` auth, endpoints in `backend/routes/agent_api.py`
2. **MCP tool pattern** — impl in `mcp-server/src/tools/`, registration in `server.py`
3. **Execution engine** — Templates in `backend/execution/templates/`, dispatched by `execution_type`
4. **Knowledge Base** — ChromaDB for vector search, PostgreSQL for metadata
5. **Frontend routing** — React Router, pages in `frontend/src/pages/`
