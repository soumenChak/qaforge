"""QAForge MCP Server — Entry Point"""
import os

# Ensure host binding before any MCP imports read settings
os.environ.setdefault("FASTMCP_HOST", "0.0.0.0")
os.environ.setdefault("FASTMCP_PORT", "8000")

from dotenv import load_dotenv
load_dotenv()

from src.server import mcp  # noqa: E402


def run():
    """Run the QAForge MCP server with SSE transport."""
    mcp.run(transport="sse")


if __name__ == "__main__":
    run()
