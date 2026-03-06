# QAForge Setup Guide

Complete guide to deploying QAForge for your team.

## Deployment Options

### Option 1: Docker Compose (Recommended)

```bash
git clone git@bitbucket.org:lifio/qaforge.git
cd qaforge
cp .env.example .env
```

Edit `.env` with your values:

```bash
# REQUIRED
SECRET_KEY=<generate: python3 -c "import secrets; print(secrets.token_urlsafe(64))">
ANTHROPIC_API_KEY=sk-ant-...    # or OPENAI_API_KEY or GROQ_API_KEY

# OPTIONAL — change defaults for production
DB_PASSWORD=strong-password-here
QAFORGE_BOOTSTRAP_TOKEN=<generate: python3 -c "import secrets; print(secrets.token_urlsafe(32))">
```

Start everything:

```bash
docker compose up -d
```

Verify:

```bash
docker compose ps          # All services should be "running"
curl http://localhost:8080  # Frontend loads
curl http://localhost:8080/api/health  # {"status": "ok"}
```

### Option 2: Behind HTTPS (Production)

Add nginx in front for SSL termination. Example config:

```nginx
server {
    listen 443 ssl http2;
    server_name qaforge.yourdomain.com;

    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    client_max_body_size 50m;

    location / {
        proxy_pass https://127.0.0.1:8081;  # frontend container
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_ssl_verify off;

        # SSE support (for MCP)
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        chunked_transfer_encoding off;
        proxy_read_timeout 3600s;
    }
}
```

The frontend container's internal nginx routes `/api/*` to the backend and `/qaforge-mcp/*` to the MCP server.

## First-Time Configuration

### 1. Login

Default credentials: `admin@qaforge.io` / `admin123`

**Change the password immediately** via Settings.

### 2. Create a Project

1. Go to **Projects** > **New Project**
2. Fill in:
   - **Name**: e.g., "Reltio MDM"
   - **Domain**: mdm, ai, data_eng, integration, or digital
   - **Sub-domain**: e.g., reltio, snowflake
   - **Description**: Brief project context
3. Save

### 3. Generate Agent API Key

1. Open your project
2. Go to **Settings** tab
3. Under **Agent API Key**, click **Generate**
4. Copy the key immediately (shown only once, starts with `qf_`)

### 4. Seed the Knowledge Base (Optional)

Upload domain patterns to improve AI test generation:

```bash
# From the qaforge directory
python3 backend/seed_knowledge.py
```

This populates ChromaDB with MDM, AI, Data Engineering, and Integration test patterns.

## Connecting AI Assistants

### Claude Code (CLI)

```bash
# Global MCP server (available in all projects)
claude mcp add qaforge --transport sse \
  --url "https://qaforge.yourdomain.com/qaforge-mcp/sse"

# Or project-level: add .mcp.json to any repo
```

Then in Claude Code:

```
> Connect to QAForge with key qf_your-key-here
> Show me the project dashboard
> Generate 10 test cases from requirements
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "qaforge": {
      "type": "sse",
      "url": "https://qaforge.yourdomain.com/qaforge-mcp/sse"
    }
  }
}
```

### Any HTTP Client (Direct API)

```bash
# List test cases
curl -H "X-Agent-Key: qf_your-key" https://qaforge.yourdomain.com/api/agent/test-cases

# Submit a test case
curl -X POST -H "X-Agent-Key: qf_your-key" \
  -H "Content-Type: application/json" \
  -d '{"test_cases": [{"test_case_id": "TC-001", "title": "Login test", ...}]}' \
  https://qaforge.yourdomain.com/api/agent/test-cases
```

## Adding External MCP Servers

QAForge can execute tests against external MCP servers (Reltio, Snowflake, etc.).

### Reltio MCP

1. Deploy the Reltio MCP server (see its repo)
2. Add to `.env`:
   ```
   RELTIO_MCP_URL=http://reltio_mcp_server:8000/sse
   ```
3. Create test cases with `execution_type: "mcp"` and `tool_name` in test steps

### Custom MCP Server

Any MCP server accessible via SSE can be used. Configure the URL in project settings or `.env`.

## Troubleshooting

### Services won't start

```bash
docker compose logs backend --tail 50   # Check for errors
docker compose logs db --tail 20        # DB connection issues?
```

Common issues:
- Port conflict: Change ports in `.env` (`FRONTEND_PORT`, `DB_PORT`, `REDIS_PORT`)
- DB not ready: Backend retries automatically, but if it fails, restart: `docker compose restart backend`

### MCP connection fails

```bash
docker compose logs qaforge_mcp --tail 20
# "Could not find session" → restart MCP: docker compose restart qaforge_mcp
```

### AI generation returns empty

- Verify LLM API key is set in `.env`
- Check backend logs for API errors: `docker compose logs backend | grep -i error`
- Try a different provider: set `DEFAULT_LLM_PROVIDER=groq` (free tier)

### Reset everything

```bash
docker compose down -v   # WARNING: deletes all data
docker compose up -d     # Fresh start
```

## Backup & Restore

### Database backup

```bash
docker exec qaforge_db pg_dump -U qaforge -d qaforge > backup.sql
```

### Database restore

```bash
docker exec -i qaforge_db psql -U qaforge -d qaforge < backup.sql
```

### ChromaDB

ChromaDB data is in the `qaforge_chromadb_data` Docker volume. Back it up with:

```bash
docker run --rm -v qaforge_chromadb_data:/data -v $(pwd):/backup busybox tar czf /backup/chromadb-backup.tar.gz /data
```
