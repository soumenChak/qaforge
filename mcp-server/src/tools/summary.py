"""QAForge MCP Tools — Summary & Coverage"""
from src.api_client import agent_get


async def get_summary_impl() -> dict:
    """Get project summary: test case counts, pass rates, coverage metrics."""
    return await agent_get("/summary")
