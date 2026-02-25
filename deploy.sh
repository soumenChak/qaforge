#!/usr/bin/env bash
# =============================================================================
# QAForge — Remote Deploy Script
# =============================================================================
# Builds a tarball locally, SCPs to the VM, and runs docker compose.
# Preserves .env and certs on the remote to avoid wiping secrets/SSL.
#
# Usage:
#   ./deploy.sh                     # deploy to default VM
#   ./deploy.sh 10.0.0.5            # deploy to custom IP
#   ./deploy.sh 10.0.0.5 mykey.pem  # deploy with custom key
# =============================================================================

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
VM_IP="${1:-13.233.36.18}"
SSH_KEY="${2:-$HOME/Desktop/innovation-lab.pem}"
VM_USER="ubuntu"
REMOTE_DIR="/opt/qaforge"
TARBALL="qaforge-deploy.tar.gz"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Preflight Checks ────────────────────────────────────────────────────────
[[ -f "$SSH_KEY" ]] || fail "SSH key not found: $SSH_KEY"
command -v ssh >/dev/null || fail "ssh not found"
command -v scp >/dev/null || fail "scp not found"
command -v tar >/dev/null || fail "tar not found"

log "Deploying QAForge to $VM_USER@$VM_IP:$REMOTE_DIR"

# ── Build Tarball ────────────────────────────────────────────────────────────
log "Building deployment tarball..."
cd "$PROJECT_DIR"

# COPYFILE_DISABLE=1 prevents macOS resource fork (._*) files that cause
# Python SyntaxError: null bytes in Alembic migrations.
COPYFILE_DISABLE=1 tar czf "/tmp/$TARBALL" \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='certs/' \
    --exclude='*.tar.gz' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='build' \
    --exclude='.next' \
    .

TARBALL_SIZE=$(du -h "/tmp/$TARBALL" | cut -f1)
log "Tarball created: $TARBALL_SIZE"

# ── Upload to VM ─────────────────────────────────────────────────────────────
log "Uploading to $VM_IP..."
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no "/tmp/$TARBALL" \
    "$VM_USER@$VM_IP:/tmp/$TARBALL"

# ── Deploy on VM ─────────────────────────────────────────────────────────────
log "Deploying on remote..."
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" bash -s <<'REMOTE_SCRIPT'
set -euo pipefail

REMOTE_DIR="/opt/qaforge"
TARBALL="/tmp/qaforge-deploy.tar.gz"

# Create target directory if first deploy
sudo mkdir -p "$REMOTE_DIR"
sudo chown "$USER:$USER" "$REMOTE_DIR"

# Backup .env and certs before extraction
[[ -f "$REMOTE_DIR/.env" ]] && cp "$REMOTE_DIR/.env" /tmp/qaforge-env-backup
[[ -d "$REMOTE_DIR/certs" ]] && cp -r "$REMOTE_DIR/certs" /tmp/qaforge-certs-backup

# Extract tarball
cd "$REMOTE_DIR"
tar xzf "$TARBALL"

# Restore .env and certs
[[ -f /tmp/qaforge-env-backup ]] && mv /tmp/qaforge-env-backup "$REMOTE_DIR/.env"
[[ -d /tmp/qaforge-certs-backup ]] && {
    rm -rf "$REMOTE_DIR/certs"
    mv /tmp/qaforge-certs-backup "$REMOTE_DIR/certs"
}

# Run the on-VM deploy script
if [[ -f "$REMOTE_DIR/scripts/vm-deploy.sh" ]]; then
    bash "$REMOTE_DIR/scripts/vm-deploy.sh"
else
    echo "[WARN] scripts/vm-deploy.sh not found, running docker compose directly"
    cd "$REMOTE_DIR"
    docker compose build --parallel
    docker compose up -d
fi

# Cleanup
rm -f "$TARBALL"
REMOTE_SCRIPT

# ── Cleanup Local ────────────────────────────────────────────────────────────
rm -f "/tmp/$TARBALL"

log "Deploy complete! QAForge is live at http://$VM_IP:8090"
