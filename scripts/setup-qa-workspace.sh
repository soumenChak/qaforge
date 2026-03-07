#!/bin/bash
# ============================================================================
# QAForge — Quinn's Workspace Setup
# Sets up a clean QA workspace where Quinn operates through MCP tools only.
# No source code, no IDE — just conversation.
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

WORKSPACE="${1:-$HOME/qa-workspace}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Meet Quinn — Your AI QA Engineer        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Get MCP URL
if [ -z "$QAFORGE_MCP_URL" ]; then
    echo -e "${YELLOW}Where is your QAForge MCP server running?${NC}"
    echo "  Examples:"
    echo "    Local:      http://localhost:8080/qaforge-mcp/sse"
    echo "    Production: https://qaforge.yourdomain.com/qaforge-mcp/sse"
    echo ""
    read -p "MCP URL: " QAFORGE_MCP_URL
fi

if [ -z "$QAFORGE_MCP_URL" ]; then
    echo "Error: MCP URL is required."
    exit 1
fi

# Create workspace
echo ""
echo -e "${GREEN}Setting up Quinn's workspace at: ${WORKSPACE}${NC}"
mkdir -p "$WORKSPACE"

# Copy CLAUDE.md
cp "$REPO_DIR/templates/qa-workspace/CLAUDE.md" "$WORKSPACE/CLAUDE.md"
echo "  ✓ CLAUDE.md (Quinn's persona + tool guide)"

# Create .mcp.json with actual URL
cat > "$WORKSPACE/.mcp.json" << EOF
{
  "mcpServers": {
    "qaforge": {
      "type": "sse",
      "url": "$QAFORGE_MCP_URL"
    }
  }
}
EOF
echo "  ✓ .mcp.json (MCP server: $QAFORGE_MCP_URL)"

# Optional: add extra MCP servers
echo ""
echo -e "${YELLOW}Do you have additional MCP servers to add? (e.g., Reltio, Snowflake)${NC}"
echo "  Enter SSE URLs one per line, format: name=url"
echo "  Examples: reltio=https://host/mcp/sse"
echo "  Press Enter with empty line to skip."
echo ""

while true; do
    read -p "  MCP server (name=url): " MCP_ENTRY
    [ -z "$MCP_ENTRY" ] && break

    MCP_NAME="${MCP_ENTRY%%=*}"
    MCP_URL="${MCP_ENTRY#*=}"

    if [ -z "$MCP_NAME" ] || [ -z "$MCP_URL" ] || [ "$MCP_NAME" = "$MCP_URL" ]; then
        echo "  Invalid format. Use: name=url"
        continue
    fi

    # Add to .mcp.json using python for proper JSON handling
    python3 -c "
import json
with open('$WORKSPACE/.mcp.json') as f:
    config = json.load(f)
config['mcpServers']['$MCP_NAME'] = {'type': 'sse', 'url': '$MCP_URL'}
with open('$WORKSPACE/.mcp.json', 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
"
    echo "  ✓ Added $MCP_NAME ($MCP_URL)"
done

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Quinn is ready!                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  To start:"
echo ""
echo -e "    ${BLUE}cd $WORKSPACE && claude${NC}"
echo ""
echo "  Then say:"
echo ""
echo "    \"Hey Quinn, connect to my project with key qf_...\""
echo ""
echo "  Quinn will introduce herself and guide you from there."
echo ""
echo -e "  ${YELLOW}Tip:${NC} Open a second terminal for Forge (developer persona):"
echo -e "    ${BLUE}cd $(dirname "$SCRIPT_DIR") && claude${NC}"
echo ""
