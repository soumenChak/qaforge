"""QAForge MCP Server — HTTP Client for Agent API

Wraps the QAForge Agent REST API with async httpx calls.
All endpoints are under /api/agent/* and use X-Agent-Key auth.
"""
import logging
import httpx
from src.config import QAFORGE_API_URL, QAFORGE_AGENT_KEY

logger = logging.getLogger("qaforge.mcp.client")

_HEADERS = {"X-Agent-Key": QAFORGE_AGENT_KEY, "Content-Type": "application/json"}
_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


def _url(path: str) -> str:
    """Build full URL for an Agent API endpoint."""
    return f"{QAFORGE_API_URL}/api/agent{path}"


async def agent_get(path: str, params: dict | None = None) -> dict | list:
    """GET request to Agent API."""
    async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as client:
        r = await client.get(_url(path), headers=_HEADERS, params=params)
        r.raise_for_status()
        return r.json()


async def agent_post(path: str, json: dict | list | None = None) -> dict | list:
    """POST request to Agent API."""
    async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as client:
        r = await client.post(_url(path), headers=_HEADERS, json=json)
        r.raise_for_status()
        return r.json()


async def agent_put(path: str, json: dict | None = None) -> dict | list:
    """PUT request to Agent API."""
    async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as client:
        r = await client.put(_url(path), headers=_HEADERS, json=json)
        r.raise_for_status()
        return r.json()
