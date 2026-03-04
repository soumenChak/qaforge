"""QAForge MCP Server — Entry Point"""
from dotenv import load_dotenv
load_dotenv()

from src.server import mcp  # noqa: E402


def run():
    """Run the QAForge MCP server with SSE transport."""
    mcp.run(transport="sse")


if __name__ == "__main__":
    run()
