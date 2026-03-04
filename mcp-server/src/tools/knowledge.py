"""QAForge MCP Tools — Knowledge Base"""
from src.api_client import agent_get, agent_post


async def kb_stats_impl(domain: str = "") -> dict:
    """Get Knowledge Base statistics."""
    params = {}
    if domain:
        params["domain"] = domain
    return await agent_get("/kb-stats", params=params or None)


async def upload_reference_impl(entries: list, domain: str, sub_domain: str) -> dict:
    """Upload reference test cases to the Knowledge Base for future AI generation.

    Each entry: {title, content, tags?}
    """
    return await agent_post("/upload-reference", json={
        "reference_test_cases": entries,
        "domain": domain,
        "sub_domain": sub_domain,
    })
