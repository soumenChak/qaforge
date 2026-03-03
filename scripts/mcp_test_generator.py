#!/usr/bin/env python3
"""
MCP Sanity Test Generator — generates basic connectivity test cases
from discovered MCP tools. No LLM needed.

Usage (imported by qaforge.py):
    from mcp_test_generator import generate_sanity_tests
"""

from typing import Any, Dict, List


def generate_sanity_tests(
    tools: List[Dict],
    connection_ref: str,
    prefix: str = "TC-MCP",
    max_tests: int = 20,
) -> List[Dict]:
    """
    Generate sanity/connectivity test cases from discovered MCP tools.

    Args:
        tools: List from MCPConnection.connect() — [{name, description, input_schema}]
        connection_ref: Connection key in app_profile (e.g., "reltio_mcp")
        prefix: Test case ID prefix (e.g., "TC-RELTIO")
        max_tests: Maximum number of tests to generate

    Returns:
        List of test case dicts ready for POST /agent/test-cases
    """
    cases: List[Dict] = []
    counter = 1

    # --- 1. Health check (always first if available) ---
    health_tools = [t for t in tools if "health" in t["name"].lower()]
    if health_tools:
        tool = health_tools[0]
        cases.append({
            "test_case_id": f"{prefix}-{counter:03d}",
            "title": f"Sanity: {tool['name']} — verify server is healthy",
            "description": f"Verify MCP server connectivity by calling {tool['name']}. "
                           f"This is a zero-impact read-only check.",
            "category": "smoke",
            "priority": "P1",
            "execution_type": "mcp",
            "expected_result": "Server responds with healthy status (status: ok)",
            "test_steps": [{
                "step_number": 1,
                "action": f"Call {tool['name']} on MCP server",
                "expected_result": "Returns JSON with status 'ok' or 'healthy'",
                "step_type": "mcp",
                "connection_ref": connection_ref,
                "tool_name": tool["name"],
                "tool_params": {},
                "assertions": [
                    {"type": "not_empty"},
                    {"type": "json_path", "path": "$.status", "expected": "ok"},
                ],
            }],
        })
        counter += 1

    # --- 2. Capabilities/discovery (if available) ---
    caps_tools = [t for t in tools if "capabilit" in t["name"].lower()]
    if caps_tools:
        tool = caps_tools[0]
        cases.append({
            "test_case_id": f"{prefix}-{counter:03d}",
            "title": f"Sanity: {tool['name']} — discover tool inventory",
            "description": f"Retrieve the full tool manifest from the MCP server. "
                           f"Validates that the server exposes its capabilities.",
            "category": "smoke",
            "priority": "P1",
            "execution_type": "mcp",
            "expected_result": "Returns non-empty tool manifest with tool names and descriptions",
            "test_steps": [{
                "step_number": 1,
                "action": f"Call {tool['name']} to list all available tools",
                "expected_result": "Returns tool manifest (list of tools with descriptions)",
                "step_type": "mcp",
                "connection_ref": connection_ref,
                "tool_name": tool["name"],
                "tool_params": {},
                "assertions": [
                    {"type": "not_empty"},
                ],
            }],
        })
        counter += 1

    # --- 3. One test per safe read-only tool ---
    safe_prefixes = ("get_", "search_", "list_", "find_", "retrieve_", "check_")
    # Skip health/capabilities tools already added
    already = {c["test_steps"][0]["tool_name"] for c in cases}

    for tool in sorted(tools, key=lambda t: t["name"]):
        if counter > max_tests:
            break

        name = tool["name"]
        if name in already:
            continue

        if not any(name.startswith(p) for p in safe_prefixes):
            continue

        # Build minimal params from schema (only required params with defaults)
        params = _build_minimal_params(tool.get("input_schema", {}))

        cases.append({
            "test_case_id": f"{prefix}-{counter:03d}",
            "title": f"Sanity: {name} — read-only connectivity check",
            "description": f"Verify {name} is callable and returns a response. "
                           f"{tool['description'][:100]}",
            "category": "smoke",
            "priority": "P2",
            "execution_type": "mcp",
            "expected_result": f"{name} returns a non-empty response without errors",
            "test_steps": [{
                "step_number": 1,
                "action": f"Call {name} with minimal parameters",
                "expected_result": "Returns non-empty response",
                "step_type": "mcp",
                "connection_ref": connection_ref,
                "tool_name": name,
                "tool_params": params,
                "assertions": [
                    {"type": "not_empty"},
                ],
            }],
        })
        counter += 1

    return cases


def _build_minimal_params(input_schema: Dict) -> Dict:
    """
    Build minimal params from a tool's JSON Schema.
    Only fills required fields with sensible defaults.
    """
    if not input_schema:
        return {}

    params = {}
    required = set(input_schema.get("required", []))
    properties = input_schema.get("properties", {})

    for prop_name, prop_def in properties.items():
        if prop_name not in required:
            continue

        # Use default if available
        if "default" in prop_def:
            params[prop_name] = prop_def["default"]
            continue

        # Generate sensible defaults by type
        prop_type = prop_def.get("type", "string")
        if prop_type == "string":
            # Common parameter patterns
            if "type" in prop_name.lower():
                params[prop_name] = "Individual"  # Common entity type
            elif "filter" in prop_name.lower():
                params[prop_name] = ""
            elif "id" in prop_name.lower():
                params[prop_name] = ""  # Will likely need user input
            else:
                params[prop_name] = ""
        elif prop_type == "integer":
            if "max" in prop_name.lower() or "limit" in prop_name.lower():
                params[prop_name] = 5
            else:
                params[prop_name] = 1
        elif prop_type == "boolean":
            params[prop_name] = False
        elif prop_type == "object":
            params[prop_name] = {}
        elif prop_type == "array":
            params[prop_name] = []

    return params
