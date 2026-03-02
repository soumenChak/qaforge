# QAForge Runbook

**Operations Guide — Deploy, Monitor, Troubleshoot**

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Initial Deployment](#2-initial-deployment)
3. [Environment Variables](#3-environment-variables)
4. [SSL Certificates](#4-ssl-certificates)
5. [Database Management](#5-database-management)
6. [Monitoring & Health Checks](#6-monitoring--health-checks)
7. [Log Management](#7-log-management)
8. [Backup & Restore](#8-backup--restore)
9. [Updating & Redeployment](#9-updating--redeployment)
10. [Troubleshooting](#10-troubleshooting)
11. [Scaling](#11-scaling)
12. [Security Hardening](#12-security-hardening)

---

## 1. Prerequisites

- **Docker** 24+ and **Docker Compose** v2
- **2 GB RAM** minimum (4 GB recommended)
- **10 GB disk** (database + vector DB grow with usage)
- **Ports available:** 8080 (frontend), 5434 (postgres), 6381 (redis), 8001 (chromadb)
- At least one LLM API key (Anthropic, OpenAI, or Groq) — or Ollama for local AI

---

## 2. Initial Deployment

```bash
# 1. Clone
git clone git@bitbucket.org:lifio/qaforge.git
cd qaforge

# 2. Configure
cp .env.example .env
# Edit .env — set SECRET_KEY and at least one LLM API key

# 3. Generate SSL certs (if no Let's Encrypt)
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=qaforge.local"

# 4. Launch
docker compose up -d

# 5. Verify all 5 containers are healthy
docker compose ps

# 6. Login
# Open https://localhost:8080
# Credentials: admin@freshgravity.com / admin123
```

### VM Deployment (Production)

```bash
# On VM
cd /opt/qaforge
bash scripts/vm-deploy.sh
```

The `vm-deploy.sh` script:
1. Checks prerequisites (.env, Docker)
2. Builds all containers in parallel
3. Starts services
4. Waits for PostgreSQL readiness
5. Runs Alembic migrations
6. Validates all 5 health checks
7. Reports final status

---

## 3. Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key (min 32 chars) | `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DB_PASSWORD` | PostgreSQL password | `qaforge_pass` |

### LLM Configuration (at least one required)

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `GROQ_API_KEY` | Groq API key (free tier available) | — |
| `DEFAULT_LLM_PROVIDER` | Provider to use | `anthropic` |
| `DEFAULT_LLM_MODEL` | Model name | `claude-sonnet-4-20250514` |

### Ports (avoid conflicts)

| Variable | Default | Description |
|----------|---------|-------------|
| `FRONTEND_PORT` | `8080` | HTTPS frontend port |
| `DB_PORT` | `5434` | PostgreSQL external port |
| `REDIS_PORT` | `6381` | Redis external port |
| `CHROMADB_PORT` | `8001` | ChromaDB external port |

### Connection Strings (auto-configured in Docker)

| Variable | Default |
|----------|---------|
| `DATABASE_URL` | `postgresql://qaforge:${DB_PASSWORD}@db:5432/qaforge` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `CHROMADB_HOST` | `chromadb` |
| `CHROMADB_PORT` | `8000` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose logging |
| `SQL_ECHO` | `false` | Log all SQL queries |

---

## 4. SSL Certificates

### Self-Signed (Development)

```bash
mkdir -p certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem \
  -subj "/CN=qaforge.local"
```

### Let's Encrypt (Production)

```bash
# Install certbot
sudo apt install certbot

# Generate certs
sudo certbot certonly --standalone -d qaforge.yourdomain.com

# Copy to project
sudo cp /etc/letsencrypt/live/qaforge.yourdomain.com/fullchain.pem certs/cert.pem
sudo cp /etc/letsencrypt/live/qaforge.yourdomain.com/privkey.pem certs/key.pem

# Auto-renew cron
echo "0 3 * * * root certbot renew --quiet && cp /etc/letsencrypt/live/qaforge.yourdomain.com/*.pem /opt/qaforge/certs/ && docker compose -f /opt/qaforge/docker-compose.yml restart frontend" | sudo tee /etc/cron.d/certbot-qaforge
```

The `certs/` directory is mounted read-only into the nginx container.

---

## 5. Database Management

### Access PostgreSQL

```bash
# Via Docker
docker compose exec db psql -U qaforge

# Via external tool (DBeaver, pgAdmin)
# Host: localhost, Port: 5434, User: qaforge, DB: qaforge
```

### Alembic Migrations

```bash
# Run pending migrations
docker compose exec backend sh -c "cd /app && alembic upgrade head"

# Check current revision
docker compose exec backend sh -c "cd /app && alembic current"

# Create new migration
docker compose exec backend sh -c "cd /app && alembic revision --autogenerate -m 'description'"
```

### Table Overview

| Table | Description | Grows With |
|-------|-------------|------------|
| `projects` | QA projects | New projects created |
| `test_cases` | Test case definitions | AI generation + agent submissions |
| `execution_results` | Test run outcomes | Every test execution |
| `proof_artifacts` | Evidence payloads | JSONB, can be large |
| `knowledge_entries` | RAG knowledge base | Manual + auto-learning |
| `generation_runs` | LLM usage tracking | Every AI generation |
| `cost_tracking` | Cost analytics | Every LLM call |
| `audit_log` | Immutable audit | Every significant action |

### Size Check

```sql
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 6. Monitoring & Health Checks

### Built-in Health Endpoints

```bash
# Backend health
curl -k https://localhost:8080/api/health
# → {"status": "ok", "service": "qaforge-backend"}

# Frontend health
curl http://localhost:80/health
# → {"status": "ok", "service": "qaforge-frontend"}
```

### Container Health

```bash
# All services status
docker compose ps

# Expected output: all 5 services "healthy"
# qaforge_backend    healthy
# qaforge_db         healthy
# qaforge_redis      healthy
# qaforge_chromadb   healthy
# qaforge_frontend   healthy
```

### Service-Specific Checks

```bash
# PostgreSQL
docker compose exec db pg_isready -U qaforge

# Redis
docker compose exec redis redis-cli ping
# → PONG

# ChromaDB
curl http://localhost:8001/api/v1/heartbeat
# → {"nanosecond heartbeat": ...}

# Backend (direct)
docker compose exec backend curl http://localhost:8000/health
```

### Resource Usage

```bash
docker stats --no-stream
```

---

## 7. Log Management

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db

# Last 100 lines
docker compose logs --tail 100 backend
```

### Backend Log Format

```
2026-03-02 10:15:32 INFO  qaforge  POST /api/agent/test-cases -> 200 (145ms)
2026-03-02 10:15:33 INFO  qaforge  Agent submitted 5 test cases for project Orbit
```

### Enable Debug Logging

```bash
# In .env
LOG_LEVEL=DEBUG

# Restart backend
docker compose restart backend
```

### Log Rotation

Docker handles log rotation. Configure in `docker-compose.yml`:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

---

## 8. Backup & Restore

### PostgreSQL Backup

```bash
# Full dump
docker compose exec db pg_dump -U qaforge qaforge > backup_$(date +%Y%m%d).sql

# Compressed
docker compose exec db pg_dump -U qaforge -Fc qaforge > backup_$(date +%Y%m%d).dump
```

### PostgreSQL Restore

```bash
# From SQL dump
docker compose exec -T db psql -U qaforge qaforge < backup_20260302.sql

# From compressed dump
docker compose exec -T db pg_restore -U qaforge -d qaforge backup_20260302.dump
```

### Redis Backup

Redis uses AOF persistence. Data survives container restarts via `qaforge_redis_data` volume.

```bash
# Manual snapshot
docker compose exec redis redis-cli BGSAVE
```

### ChromaDB Backup

ChromaDB data persists in `qaforge_chromadb_data` volume.

```bash
# Backup volume (Docker)
docker run --rm -v qaforge_chromadb_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/chromadb_backup.tar.gz -C /data .
```

### Automated Backup Script

```bash
#!/bin/bash
# backup_qaforge.sh — run via cron
DATE=$(date +%Y%m%d_%H%M)
BACKUP_DIR=/opt/backups/qaforge

mkdir -p $BACKUP_DIR
docker compose -f /opt/qaforge/docker-compose.yml exec -T db \
  pg_dump -U qaforge -Fc qaforge > $BACKUP_DIR/db_$DATE.dump

# Keep last 7 days
find $BACKUP_DIR -name "db_*.dump" -mtime +7 -delete
```

---

## 9. Updating & Redeployment

### Standard Update

```bash
cd /opt/qaforge
git pull
docker compose build --parallel
docker compose up -d
docker compose exec backend sh -c "cd /app && alembic upgrade head"
docker compose ps  # verify all healthy
```

### Zero-Downtime Update

```bash
# Build new images without stopping
docker compose build --parallel

# Restart one service at a time
docker compose up -d --no-deps backend
sleep 10  # wait for health check
docker compose up -d --no-deps frontend
```

### Rollback

```bash
git checkout <previous-commit>
docker compose build --parallel
docker compose up -d
```

---

## 10. Troubleshooting

### Container Won't Start

```bash
# Check logs for the failing service
docker compose logs backend
docker compose logs db

# Common: database not ready yet
# → Backend depends on db health check, should auto-retry
```

### Backend 500 Errors

```bash
# Check backend logs
docker compose logs --tail 50 backend

# Enable debug
# Set LOG_LEVEL=DEBUG in .env, restart backend
```

### Database Connection Refused

```bash
# Check db is running
docker compose ps db

# Check connection
docker compose exec db pg_isready -U qaforge

# Common: wrong DATABASE_URL
# → Must use service name 'db', not 'localhost' inside Docker
```

### Agent API 401 Unauthorized

```bash
# Check the key format
echo $QAFORGE_AGENT_KEY  # should start with qf_

# Test directly
curl -k -v https://localhost:8080/api/agent/summary \
  -H "X-Agent-Key: $QAFORGE_AGENT_KEY"

# Regenerate key if needed (UI: Projects → Agent API Key → Regenerate)
```

### ChromaDB Not Responding

```bash
# Check health
curl http://localhost:8001/api/v1/heartbeat

# Restart
docker compose restart chromadb

# Check logs
docker compose logs chromadb
```

### Frontend Shows Blank Page

```bash
# Check nginx logs
docker compose logs frontend

# Common: missing certs
ls -la certs/  # should have cert.pem and key.pem

# Common: backend not reachable
docker compose exec frontend wget -q -O- http://backend:8000/health
```

### Rate Limiting (429 Too Many Requests)

```bash
# Check Redis rate limit keys
docker compose exec redis redis-cli keys "LIMITER*"

# Clear rate limits
docker compose exec redis redis-cli FLUSHDB

# Note: 200 req/min default, adjust in backend/main.py if needed
```

### Migration Errors

```bash
# Check current state
docker compose exec backend sh -c "cd /app && alembic current"

# Stamp current (if tables exist but alembic doesn't know)
docker compose exec backend sh -c "cd /app && alembic stamp head"

# Then run migrations
docker compose exec backend sh -c "cd /app && alembic upgrade head"
```

---

## 11. Scaling

### Current Capacity

- **Backend:** 10 DB connections (pool), 20 max overflow
- **Redis:** 128 MB max memory, LRU eviction
- **ChromaDB:** Persistent storage, no built-in clustering
- **Rate limit:** 200 req/min per IP

### Vertical Scaling

```yaml
# docker-compose.yml — increase backend resources
backend:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 2G
```

### Horizontal Scaling (Future)

- Backend: multiple replicas behind load balancer (stateless)
- Database: read replicas for query-heavy workloads
- Redis: Redis Cluster for high-volume rate limiting
- ChromaDB: external managed instance

### Performance Tuning

```bash
# PostgreSQL — increase shared buffers
docker compose exec db psql -U qaforge -c "SHOW shared_buffers;"
# Default: 128MB, increase for larger datasets

# Redis — check memory usage
docker compose exec redis redis-cli INFO memory

# Backend — check connection pool
# Set SQL_ECHO=true in .env to log all SQL
```

---

## 12. Security Hardening

### Pre-Production Checklist

- [ ] **SECRET_KEY:** Generate strong key (≥64 chars): `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`
- [ ] **Admin password:** Change default `admin123` immediately after first login
- [ ] **CORS_ORIGINS:** Set to specific origins (not `*`)
- [ ] **SSL certificates:** Use Let's Encrypt (not self-signed)
- [ ] **Database password:** Change from default `qaforge_pass`
- [ ] **Ports:** Restrict DB/Redis external access (remove port mappings or firewall)
- [ ] **LLM keys:** Use environment variables, never commit to git
- [ ] **Agent keys:** Rotate periodically, revoke unused keys
- [ ] **Firewall:** Only expose port 8080 (frontend HTTPS)
- [ ] **Updates:** Keep Docker images and dependencies updated

### Network Isolation

```yaml
# docker-compose.yml — restrict external access
db:
  # Remove ports mapping for production
  # ports:
  #   - "${DB_PORT:-5434}:5432"
  expose:
    - "5432"  # internal only
```

### Audit Review

```sql
-- Recent actions
SELECT action, entity_type, created_at, details->>'ip_address'
FROM audit_log
ORDER BY created_at DESC
LIMIT 50;

-- Failed login attempts
SELECT * FROM audit_log
WHERE action = 'login_failed'
ORDER BY created_at DESC;
```
