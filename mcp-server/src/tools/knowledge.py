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


async def create_kb_entry_impl(
    domain: str, entry_type: str, title: str, content: str,
    sub_domain: str = "", tags: list = None, version: str = "1.0",
) -> dict:
    """Create a new Knowledge Base entry (pattern, best practice, framework, etc.)."""
    body = {
        "domain": domain,
        "entry_type": entry_type,
        "title": title,
        "content": content,
        "version": version,
    }
    if sub_domain:
        body["sub_domain"] = sub_domain
    if tags:
        body["tags"] = tags
    return await agent_post("/knowledge", json=body)


async def list_kb_entries_impl(domain: str = "", entry_type: str = "") -> list:
    """List Knowledge Base entries with optional domain and type filters."""
    params = {}
    if domain:
        params["domain"] = domain
    if entry_type:
        params["entry_type"] = entry_type
    return await agent_get("/knowledge", params=params or None)
