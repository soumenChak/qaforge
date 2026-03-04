"""QAForge MCP Tools — Project Management"""
from src.api_client import agent_get, agent_put


async def get_project_info() -> dict:
    """Fetch project metadata."""
    return await agent_get("/project")


async def update_project_info(
    description: str | None = None,
    app_profile: dict | None = None,
    brd_prd_text: str | None = None,
) -> dict:
    """Update project fields."""
    payload = {}
    if description is not None:
        payload["description"] = description
    if app_profile is not None:
        payload["app_profile"] = app_profile
    if brd_prd_text is not None:
        payload["brd_prd_text"] = brd_prd_text
    return await agent_put("/project", json=payload)
