"""QAForge MCP Server — HTTP Client for Agent API

Wraps the QAForge Agent REST API with async httpx calls.
All endpoints are under /api/agent/* and use X-Agent-Key auth.

Supports dynamic project switching via set_agent_key() — the MCP
`connect` tool calls this to override the default env-based key.
"""
import logging
import httpx
from src.config import QAFORGE_API_URL, QAFORGE_AGENT_KEY

logger = logging.getLogger("qaforge.mcp.client")

# ── Dynamic key management ──────────────────────────────────────
# Module-level override. Safe because FastMCP processes tools
# sequentially within a single SSE session.
_session_key: str | None = None

_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


def set_agent_key(key: str | None) -> None:
    """Override the agent key for this MCP session. Pass None to clear override."""
    global _session_key
    _session_key = key
    if key:
        logger.info("Agent key overridden (prefix: %s...)", key[:10])
    else:
        logger.info("Agent key override cleared — using server default")


def get_active_key() -> str:
    """Return the currently active agent key (session override or env default)."""
    return _session_key or QAFORGE_AGENT_KEY


def is_override_active() -> bool:
    """Check if a session key override is active (vs using env default)."""
    return _session_key is not None


def _headers() -> dict:
    """Build auth headers using the active agent key."""
    return {"X-Agent-Key": get_active_key(), "Content-Type": "application/json"}


def _url(path: str) -> str:
    """Build full URL for an Agent API endpoint."""
    return f"{QAFORGE_API_URL}/api/agent{path}"


async def agent_get(path: str, params: dict | None = None) -> dict | list:
    """GET request to Agent API."""
    async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as client:
        r = await client.get(_url(path), headers=_headers(), params=params)
        r.raise_for_status()
        return r.json()


async def agent_post(path: str, json: dict | list | None = None) -> dict | list:
    """POST request to Agent API."""
    async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as client:
        r = await client.post(_url(path), headers=_headers(), json=json)
        r.raise_for_status()
        return r.json()


async def agent_put(path: str, json: dict | None = None) -> dict | list:
    """PUT request to Agent API."""
    async with httpx.AsyncClient(verify=False, timeout=_TIMEOUT) as client:
        r = await client.put(_url(path), headers=_headers(), json=json)
        r.raise_for_status()
        return r.json()
