"""
QAForge -- MCP Tool Execution Template.

Connects to an MCP server via SSE transport, calls a tool by name,
and validates the response.

LLM-extracted params schema:
{
  "tool_name": "health_check_tool",
  "arguments": {},
  "expected_fields": ["status"],
  "expected_body_contains": null,
  "max_response_time_ms": 30000
}
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def execute(
    params: Dict[str, Any],
    connection_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run an MCP tool call test.

    1. Connect to MCP server via SSE
    2. Call the specified tool with arguments
    3. Validate response (fields, content, timing)
    4. Return standardised result dict
    """
    # -- Import MCP client (may not be installed) --
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
    except ImportError:
        return {
            "passed": False,
            "assertions": [{"check": "mcp_import", "passed": False,
                            "actual": "mcp package not installed"}],
            "logs": ["ERROR: 'mcp' package not installed in backend. "
                     "Add 'mcp>=1.0' to requirements.txt"],
            "details": {},
            "duration_seconds": 0,
        }

    tool_name = params.get("tool_name") or params.get("tool") or params.get("action", "")
    arguments = params.get("arguments") or params.get("args") or {}
    expected_fields = params.get("expected_fields") or []
    expected_contains = params.get("expected_body_contains")
    max_time_ms = params.get("max_response_time_ms", 30000)

    # Resolve MCP server URL from connection config
    server_url = (
        connection_config.get("app_url")
        or connection_config.get("mcp_url")
        or connection_config.get("base_url", "")
    )
    if not server_url:
        return {
            "passed": False,
            "assertions": [{"check": "server_url", "passed": False,
                            "actual": "No MCP server URL in connection config"}],
            "logs": ["No app_url or mcp_url found in connection config"],
            "details": {"connection_config_keys": list(connection_config.keys())},
            "duration_seconds": 0,
        }

    # Ensure URL ends with /sse for SSE transport
    if not server_url.endswith("/sse"):
        if server_url.endswith("/"):
            server_url += "sse"
        else:
            server_url += "/sse"

    logs: List[str] = []
    assertions: List[Dict] = []
    details: Dict[str, Any] = {}
    passed = True

    logs.append(f"Connecting to MCP server: {server_url}")
    logs.append(f"Tool: {tool_name}")
    if arguments:
        logs.append(f"Arguments: {json.dumps(arguments)[:200]}")

    session = None
    streams_ctx = None
    session_ctx = None
    start = time.perf_counter()

    try:
        # -- Connect to MCP server --
        streams_ctx = sse_client(url=server_url)
        streams = await streams_ctx.__aenter__()

        session_ctx = ClientSession(*streams)
        session = await session_ctx.__aenter__()
        await session.initialize()

        # Get available tools
        response = await session.list_tools()
        tool_names = [t.name for t in response.tools]
        logs.append(f"Connected. {len(tool_names)} tools available.")
        details["available_tools"] = tool_names[:20]

        assertions.append({
            "check": "mcp_connection",
            "passed": True,
            "actual": f"Connected, {len(tool_names)} tools",
        })

        # -- Validate tool exists --
        if tool_name not in tool_names:
            # Try fuzzy match
            matches = [t for t in tool_names if tool_name.lower() in t.lower()]
            if matches:
                old_name = tool_name
                tool_name = matches[0]
                logs.append(f"Fuzzy matched '{old_name}' -> '{tool_name}'")
            else:
                assertions.append({
                    "check": "tool_exists",
                    "passed": False,
                    "actual": f"Tool '{tool_name}' not found. Available: {', '.join(tool_names[:10])}",
                })
                elapsed = time.perf_counter() - start
                return {
                    "passed": False,
                    "assertions": assertions,
                    "logs": logs,
                    "details": details,
                    "duration_seconds": elapsed,
                }

        assertions.append({
            "check": "tool_exists",
            "passed": True,
            "actual": tool_name,
        })

        # -- Call the tool --
        logs.append(f"Calling {tool_name}...")
        call_start = time.perf_counter()
        result = await session.call_tool(tool_name, arguments or {})
        call_elapsed_ms = (time.perf_counter() - call_start) * 1000

        # Parse result
        texts = []
        for item in (result.content or []):
            if hasattr(item, "text"):
                texts.append(item.text)
        raw = "\n".join(texts)

        parsed = None
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            # Try stripping markdown fences
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                inner = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                try:
                    parsed = json.loads(inner)
                except (json.JSONDecodeError, TypeError):
                    pass
            # Try YAML
            if parsed is None:
                try:
                    import yaml
                    parsed = yaml.safe_load(raw)
                    if not isinstance(parsed, (dict, list)):
                        parsed = None
                except Exception:
                    pass

        is_error = getattr(result, "isError", False)

        logs.append(f"  Response: {call_elapsed_ms:.0f}ms, "
                     f"{'ERROR' if is_error else 'OK'}, "
                     f"{len(raw)} chars")
        details["raw_response"] = raw[:2000]
        details["parsed_response"] = parsed if parsed else None
        details["call_duration_ms"] = round(call_elapsed_ms)
        details["is_error"] = is_error

        # -- Assertion: tool did not return error --
        if is_error:
            passed = False
            assertions.append({
                "check": "no_error",
                "passed": False,
                "actual": f"Tool returned error: {raw[:200]}",
            })
        else:
            assertions.append({
                "check": "no_error",
                "passed": True,
                "actual": "No error",
            })

        # -- Assertion: expected fields --
        if expected_fields and isinstance(parsed, dict):
            for field in expected_fields:
                field_present = field in parsed
                assertions.append({
                    "check": f"field:{field}",
                    "passed": field_present,
                    "actual": f"{'present' if field_present else 'missing'}",
                })
                if not field_present:
                    passed = False
                    logs.append(f"  ✗ Field '{field}' missing from response")
                else:
                    logs.append(f"  ✓ Field '{field}' present")

        # -- Assertion: body contains --
        if expected_contains:
            needle = str(expected_contains).lower()
            found = needle in raw.lower()
            assertions.append({
                "check": f"contains:{expected_contains}",
                "passed": found,
                "actual": f"{'found' if found else 'not found'}",
            })
            if not found:
                passed = False
                logs.append(f"  ✗ Expected content not found: {expected_contains}")
            else:
                logs.append(f"  ✓ Contains: {expected_contains}")

        # -- Assertion: response time --
        if max_time_ms and call_elapsed_ms > max_time_ms:
            passed = False
            assertions.append({
                "check": "response_time",
                "passed": False,
                "actual": f"{call_elapsed_ms:.0f}ms > {max_time_ms}ms",
            })
        else:
            assertions.append({
                "check": "response_time",
                "passed": True,
                "actual": f"{call_elapsed_ms:.0f}ms",
            })

    except Exception as exc:
        passed = False
        logs.append(f"Execution error: {type(exc).__name__}: {exc}")
        assertions.append({
            "check": "execution",
            "passed": False,
            "actual": str(exc)[:300],
        })
        details["error_type"] = type(exc).__name__
        details["error_message"] = str(exc)[:500]

    finally:
        # Cleanup connections
        try:
            if session_ctx:
                await session_ctx.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if streams_ctx:
                await streams_ctx.__aexit__(None, None, None)
        except Exception:
            pass

    elapsed = time.perf_counter() - start
    logs.append(f"Total time: {elapsed:.2f}s — {'PASSED' if passed else 'FAILED'}")

    return {
        "passed": passed,
        "assertions": assertions,
        "logs": logs,
        "details": details,
        "duration_seconds": elapsed,
    }
