"""QAForge MCP Tools — Requirements Management"""
from src.api_client import agent_get, agent_post


async def list_requirements_impl() -> list:
    """List all requirements in the project."""
    return await agent_get("/requirements")


async def extract_requirements_impl(text: str, source: str = "brd") -> list:
    """Extract requirements from BRD/PRD text using AI."""
    return await agent_post("/requirements/extract", json={"text": text, "source": source})


async def submit_requirements_impl(requirements: list) -> list:
    """Submit requirements to the project.

    Each requirement: {req_id, title, description, priority, category}
    """
    return await agent_post("/requirements", json={"requirements": requirements})
