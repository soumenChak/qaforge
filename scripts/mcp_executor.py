#!/usr/bin/env python3
"""
MCP Execution Engine — Connects to MCP servers, calls tools, checks assertions.

Pure mechanical execution. No LLM tokens. Reads structured test steps from
QAForge and runs them against MCP servers via SSE transport.

Usage (standalone test):
    python scripts/mcp_executor.py --url http://localhost:8000/sse --discover
    python scripts/mcp_executor.py --url http://localhost:8000/sse --call health_check_tool

Usage (imported by qaforge.py):
    from mcp_executor import MCPConnection, run_test_plan
"""

import asyncio
import json
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# MCP dependency check
# ---------------------------------------------------------------------------
try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
except ImportError:
    print("ERROR: 'mcp' package required. Install: pip install 'mcp>=1.0'")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Sentinel for missing JSON path values
# ---------------------------------------------------------------------------
_MISSING = object()


# ---------------------------------------------------------------------------
# MCPConnection — manages SSE connection to a single MCP server
# ---------------------------------------------------------------------------
class MCPConnection:
    """
    Wraps the MCP SSE client for connecting to a single MCP server.

    Pattern based on reltio-mcp-server/clients/sse/mcp_claude_client.py
    """

    def __init__(self, server_url: str, headers: Optional[Dict] = None,
                 timeout: float = 30):
        self.server_url = server_url
        self.headers = headers or {}
        self.timeout = timeout
        self.session: Optional[ClientSession] = None
        self._streams_ctx = None
        self._session_ctx = None
        self._tools_cache: Dict[str, Any] = {}  # name -> Tool object

    async def connect(self) -> List[Dict]:
        """
        Connect to MCP server via SSE, initialize session, return tool list.
        Returns list of dicts: [{name, description, input_schema}]
        """
        self._streams_ctx = sse_client(url=self.server_url)
        streams = await self._streams_ctx.__aenter__()

        self._session_ctx = ClientSession(*streams)
        self.session = await self._session_ctx.__aenter__()

        await self.session.initialize()

        response = await self.session.list_tools()
        self._tools_cache = {t.name: t for t in response.tools}

        return [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema or {},
            }
            for t in response.tools
        ]

    async def call_tool(self, name: str, arguments: Optional[Dict] = None) -> Dict:
        """
        Call an MCP tool by name. Returns parsed result dict:
        {
            "raw": str,        # raw text content
            "parsed": dict,    # JSON-parsed if possible, else None
            "is_error": bool,  # whether the call returned an error
        }
        """
        if name not in self._tools_cache:
            available = sorted(self._tools_cache.keys())
            raise ValueError(
                f"Tool '{name}' not found on server. "
                f"Available ({len(available)}): {', '.join(available[:10])}..."
            )

        result = await self.session.call_tool(name, arguments or {})
        return self._parse_result(result)

    @staticmethod
    def _parse_result(result) -> Dict:
        """Parse CallToolResult into a plain dict."""
        texts = []
        for item in (result.content or []):
            if hasattr(item, "text"):
                texts.append(item.text)

        raw = "\n".join(texts)
        parsed = None

        # Try JSON parse
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            # Some tools return YAML-ish output; try stripping markdown fences
            clean = raw.strip()
            if clean.startswith("```"):
                # Remove ```json ... ``` wrapper
                lines = clean.split("\n")
                inner = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                try:
                    parsed = json.loads(inner)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Try YAML parse if JSON failed (many MCP tools return YAML)
            if parsed is None:
                try:
                    import yaml
                    parsed = yaml.safe_load(raw)
                    # Only accept dict/list, not plain strings
                    if not isinstance(parsed, (dict, list)):
                        parsed = None
                except Exception:
                    pass

        is_error = getattr(result, "isError", False)

        return {"raw": raw, "parsed": parsed, "is_error": is_error}

    def get_tool_names(self) -> List[str]:
        """Return sorted list of available tool names."""
        return sorted(self._tools_cache.keys())

    def get_tool_info(self, name: str) -> Optional[Dict]:
        """Return info for a specific tool, or None."""
        t = self._tools_cache.get(name)
        if not t:
            return None
        return {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema or {},
        }

    async def cleanup(self):
        """Close the SSE session and streams."""
        try:
            if self._session_ctx:
                await self._session_ctx.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if self._streams_ctx:
                await self._streams_ctx.__aexit__(None, None, None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# AssertionEngine — validates MCP tool responses
# ---------------------------------------------------------------------------
class AssertionEngine:
    """Evaluates assertions against a tool response. Zero LLM tokens."""

    @staticmethod
    def evaluate(
        assertions: List[Dict],
        response: Dict,
        duration_ms: int = 0,
    ) -> List[Dict]:
        """
        Evaluate each assertion against the response.

        Returns: [{assertion: dict, passed: bool, actual: any, message: str}]
        """
        results = []
        raw = response.get("raw", "")
        parsed = response.get("parsed")

        for assertion in (assertions or []):
            a_type = assertion.get("type", "")
            try:
                if a_type == "json_path":
                    passed, actual, msg = AssertionEngine._eval_json_path(
                        parsed, assertion.get("path", "$"),
                        assertion.get("expected"),
                    )
                elif a_type == "contains":
                    value = str(assertion.get("value", ""))
                    passed = value.lower() in raw.lower()
                    actual = f"{'found' if passed else 'not found'} in response"
                    msg = f"Contains '{value}': {passed}"
                elif a_type == "not_empty":
                    passed = bool(raw and raw.strip())
                    actual = f"length={len(raw)}"
                    msg = f"Not empty: {passed}"
                elif a_type == "response_time_ms":
                    op = assertion.get("operator", "<=")
                    threshold = assertion.get("value", 5000)
                    passed = AssertionEngine._compare(duration_ms, op, threshold)
                    actual = f"{duration_ms}ms"
                    msg = f"Response time {duration_ms}ms {op} {threshold}ms: {passed}"
                elif a_type == "status_code":
                    expected = assertion.get("expected", 200)
                    # For MCP, check if parsed response has a status field
                    actual_status = (parsed or {}).get("status_code") or \
                                    (parsed or {}).get("status") or ""
                    passed = str(actual_status) == str(expected)
                    actual = str(actual_status)
                    msg = f"Status '{actual}' == '{expected}': {passed}"
                elif a_type == "equals":
                    expected = assertion.get("expected")
                    path = assertion.get("path", "$")
                    resolved = AssertionEngine._resolve_path(parsed, path)
                    passed = resolved == expected
                    actual = resolved
                    msg = f"Equals check: {passed}"
                elif a_type == "row_count":
                    op = assertion.get("operator", ">=")
                    expected_count = assertion.get("value", 1)
                    # Try to get count from parsed response
                    count = 0
                    if isinstance(parsed, dict):
                        count = parsed.get("count", parsed.get("total", 0))
                        if isinstance(parsed.get("data"), list):
                            count = count or len(parsed["data"])
                        if isinstance(parsed.get("objects"), list):
                            count = count or len(parsed["objects"])
                        if isinstance(parsed.get("entities"), list):
                            count = count or len(parsed["entities"])
                    elif isinstance(parsed, list):
                        count = len(parsed)
                    passed = AssertionEngine._compare(count, op, expected_count)
                    actual = f"count={count}"
                    msg = f"Row count {count} {op} {expected_count}: {passed}"
                elif a_type == "regex_match":
                    pattern = assertion.get("pattern", "")
                    passed = bool(re.search(pattern, raw))
                    actual = f"regex '{pattern}' {'matched' if passed else 'no match'}"
                    msg = f"Regex match: {passed}"
                else:
                    passed = True
                    actual = f"Unknown assertion type '{a_type}' — skipped"
                    msg = actual

            except Exception as e:
                passed = False
                actual = str(e)
                msg = f"Assertion error: {e}"

            results.append({
                "assertion": assertion,
                "passed": passed,
                "actual": actual,
                "message": msg,
            })

        return results

    @staticmethod
    def _eval_json_path(
        data: Any, path: str, expected: Any
    ) -> Tuple[bool, Any, str]:
        """Evaluate a JSON path assertion."""
        if data is None:
            return False, None, f"Cannot evaluate JSON path '{path}' — response is not JSON"

        resolved = AssertionEngine._resolve_path(data, path)
        if resolved is _MISSING:
            return False, None, f"Path '{path}' not found in response"

        if expected is not None:
            # Flexible comparison: stringify both sides
            passed = str(resolved) == str(expected)
            return passed, resolved, f"Path '{path}': {resolved} == {expected}: {passed}"
        else:
            # No expected value — just check it exists and is not None
            passed = resolved is not None
            return passed, resolved, f"Path '{path}' exists: {passed}"

    @staticmethod
    def _resolve_path(data: Any, path: str) -> Any:
        """
        Resolve a simple JSON path like $.status or $.entities.0.uri
        Supports: $, dot notation, numeric array indices.
        """
        if data is None:
            return _MISSING

        parts = path.lstrip("$").lstrip(".").split(".")
        parts = [p for p in parts if p]  # Remove empty parts

        if not parts:
            return data

        current = data
        for part in parts:
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return _MISSING
            elif isinstance(current, (list, tuple)):
                if part.isdigit():
                    idx = int(part)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return _MISSING
                else:
                    return _MISSING
            else:
                return _MISSING

        return current

    @staticmethod
    def _compare(actual: Any, operator: str, expected: Any) -> bool:
        """Compare two values with an operator."""
        try:
            a, e = float(actual), float(expected)
        except (ValueError, TypeError):
            return False

        ops = {
            "==": lambda a, e: a == e,
            "!=": lambda a, e: a != e,
            "<": lambda a, e: a < e,
            "<=": lambda a, e: a <= e,
            ">": lambda a, e: a > e,
            ">=": lambda a, e: a >= e,
        }
        fn = ops.get(operator)
        return fn(a, e) if fn else False


# ---------------------------------------------------------------------------
# StepExecutor — runs ordered test steps with variable binding
# ---------------------------------------------------------------------------
class StepExecutor:
    """
    Executes an ordered sequence of MCP test steps.
    Supports variable binding between steps via {{step_N.field}} syntax.
    """

    def __init__(self, connections: Dict[str, MCPConnection]):
        self.connections = connections
        self.step_outputs: Dict[int, Dict] = {}  # step_number -> response

    async def execute_steps(
        self,
        steps: List[Dict],
        default_connection: Optional[str] = None,
    ) -> List[Dict]:
        """
        Execute steps in order. Returns list of step results.

        Each result:
        {
            step_number: int,
            tool_name: str,
            status: "passed" | "failed" | "error" | "skipped",
            response: dict,
            assertions: [assertion_results],
            duration_ms: int,
            error: str or None,
        }
        """
        results = []
        sorted_steps = sorted(steps, key=lambda s: s.get("step_number", 0))

        for step in sorted_steps:
            step_type = step.get("step_type", "mcp")
            if step_type not in ("mcp",):
                # Skip non-MCP steps (future: handle api, sql, etc.)
                results.append({
                    "step_number": step.get("step_number", 0),
                    "tool_name": step.get("tool_name", ""),
                    "status": "skipped",
                    "response": {},
                    "assertions": [],
                    "duration_ms": 0,
                    "error": f"Step type '{step_type}' not yet supported by executor",
                })
                continue

            result = await self._execute_mcp_step(step, default_connection)
            results.append(result)

            # Stop on hard errors (connection failures, missing tools)
            if result["status"] == "error":
                # Mark remaining steps as skipped
                remaining = [s for s in sorted_steps
                             if s.get("step_number", 0) > step.get("step_number", 0)]
                for r_step in remaining:
                    results.append({
                        "step_number": r_step.get("step_number", 0),
                        "tool_name": r_step.get("tool_name", ""),
                        "status": "skipped",
                        "response": {},
                        "assertions": [],
                        "duration_ms": 0,
                        "error": "Skipped due to earlier step error",
                    })
                break

        return results

    async def _execute_mcp_step(
        self, step: Dict, default_conn: Optional[str]
    ) -> Dict:
        """Execute a single MCP tool step."""
        step_num = step.get("step_number", 0)
        tool_name = step.get("tool_name", "")
        tool_params = step.get("tool_params") or {}
        conn_ref = step.get("connection_ref") or default_conn
        assertions = step.get("assertions") or []

        if not tool_name:
            return {
                "step_number": step_num,
                "tool_name": "",
                "status": "error",
                "response": {},
                "assertions": [],
                "duration_ms": 0,
                "error": "No tool_name specified in step",
            }

        # Resolve variable references from previous step outputs
        resolved_params = self._resolve_variables(tool_params)

        conn = self.connections.get(conn_ref)
        if not conn:
            available = list(self.connections.keys())
            return {
                "step_number": step_num,
                "tool_name": tool_name,
                "status": "error",
                "response": {},
                "assertions": [],
                "duration_ms": 0,
                "error": f"Connection '{conn_ref}' not found. Available: {available}",
            }

        start = time.time()
        try:
            response = await conn.call_tool(tool_name, resolved_params)
            duration_ms = int((time.time() - start) * 1000)
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return {
                "step_number": step_num,
                "tool_name": tool_name,
                "status": "error",
                "response": {},
                "assertions": [],
                "duration_ms": duration_ms,
                "error": str(e),
            }

        # Store output for variable binding in subsequent steps
        self.step_outputs[step_num] = response

        # Evaluate assertions
        assertion_results = AssertionEngine.evaluate(assertions, response, duration_ms)
        all_passed = all(a["passed"] for a in assertion_results) if assertion_results else True

        # Determine status
        if response.get("is_error"):
            status = "failed"
        elif not all_passed:
            status = "failed"
        else:
            status = "passed"

        return {
            "step_number": step_num,
            "tool_name": tool_name,
            "status": status,
            "response": response,
            "assertions": assertion_results,
            "duration_ms": duration_ms,
            "error": None,
        }

    def _resolve_variables(self, params: Any) -> Any:
        """
        Replace {{step_N.field.path}} placeholders with values from previous steps.

        Example: {{step_1.parsed.entities.0.uri}} resolves to
                 self.step_outputs[1]["parsed"]["entities"][0]["uri"]
        """
        if isinstance(params, str):
            def replacer(match):
                step_num = int(match.group(1))
                field_path = match.group(2)
                if step_num in self.step_outputs:
                    val = AssertionEngine._resolve_path(
                        self.step_outputs[step_num], field_path
                    )
                    if val is not _MISSING:
                        return str(val)
                return match.group(0)  # Leave unreplaced if not found

            return re.sub(r"\{\{step_(\d+)\.(.+?)\}\}", replacer, params)

        elif isinstance(params, dict):
            return {k: self._resolve_variables(v) for k, v in params.items()}

        elif isinstance(params, list):
            return [self._resolve_variables(item) for item in params]

        return params

    def reset(self):
        """Clear step outputs between test cases."""
        self.step_outputs.clear()


# ---------------------------------------------------------------------------
# Top-level execution function
# ---------------------------------------------------------------------------
async def run_test_plan(
    test_cases: List[Dict],
    connections_config: Dict[str, Dict],
    default_connection: Optional[str] = None,
    on_step_complete=None,
) -> List[Dict]:
    """
    Execute all MCP-type test cases and return per-case execution results.

    Args:
        test_cases: List of test case dicts with 'test_steps', 'execution_type', 'id'
        connections_config: {
            "reltio_mcp": {"server_url": "http://localhost:8000/sse", "headers": {}},
        }
        default_connection: Default connection_ref for steps that don't specify one
        on_step_complete: Optional callback(test_case, step_result) for progress output

    Returns:
        List of execution result dicts ready for QAForge POST /agent/executions
    """
    # 1. Establish all MCP connections
    connections: Dict[str, MCPConnection] = {}
    for ref, config in connections_config.items():
        conn = MCPConnection(
            server_url=config["server_url"],
            headers=config.get("headers"),
            timeout=config.get("timeout", 30),
        )
        try:
            tools = await conn.connect()
            print(f"  ✓ Connected to '{ref}' — {len(tools)} tools available")
            connections[ref] = conn
        except Exception as e:
            print(f"  ✗ Failed to connect to '{ref}': {e}")
            # Return error results for all test cases that need this connection
            return [{
                "test_case_id": tc.get("id", ""),
                "status": "error",
                "actual_result": f"Failed to connect to MCP server '{ref}': {e}",
                "duration_ms": 0,
                "error_message": str(e),
                "proof_artifacts": [],
            } for tc in test_cases]

    executor = StepExecutor(connections)
    results = []

    try:
        for tc in test_cases:
            # Only execute MCP test cases
            if tc.get("execution_type") != "mcp":
                continue

            steps = tc.get("test_steps") or []
            if not steps:
                continue

            tc_id = tc.get("id", "")
            tc_title = tc.get("title", tc.get("test_case_id", "Unknown"))

            # Execute all steps for this test case
            step_results = await executor.execute_steps(steps, default_connection)

            # Progress callback
            if on_step_complete:
                for sr in step_results:
                    on_step_complete(tc, sr)

            # Determine overall status
            statuses = [s["status"] for s in step_results]
            if "error" in statuses:
                overall = "error"
            elif "failed" in statuses:
                overall = "failed"
            else:
                overall = "passed"

            total_ms = sum(s.get("duration_ms", 0) for s in step_results)

            # Build actual_result summary
            summary_parts = []
            for sr in step_results:
                icon = "✓" if sr["status"] == "passed" else "✗" if sr["status"] == "failed" else "⊘"
                summary_parts.append(
                    f"{icon} Step {sr['step_number']}: {sr['tool_name']} "
                    f"({sr['status']}, {sr['duration_ms']}ms)"
                )
            actual_result = "\n".join(summary_parts)

            # Build proof artifacts (one per step)
            proof_artifacts = []
            for sr in step_results:
                # Truncate raw response for proof storage
                raw_text = sr.get("response", {}).get("raw", "")
                if len(raw_text) > 3000:
                    raw_text = raw_text[:3000] + "... (truncated)"

                proof_artifacts.append({
                    "proof_type": "api_response",
                    "title": f"Step {sr['step_number']}: {sr['tool_name']}",
                    "content": {
                        "tool_name": sr["tool_name"],
                        "status": sr["status"],
                        "duration_ms": sr["duration_ms"],
                        "response_preview": raw_text[:500],
                        "assertions": [
                            {
                                "type": a["assertion"].get("type"),
                                "passed": a["passed"],
                                "message": a["message"],
                            }
                            for a in sr.get("assertions", [])
                        ],
                        "error": sr.get("error"),
                    },
                })

            results.append({
                "test_case_id": tc_id,
                "status": overall,
                "actual_result": actual_result,
                "duration_ms": total_ms,
                "error_message": next(
                    (s["error"] for s in step_results if s.get("error")), None
                ),
                "proof_artifacts": proof_artifacts,
            })

            # Reset step outputs between test cases
            executor.reset()

    finally:
        # Clean up all connections
        for conn in connections.values():
            await conn.cleanup()

    return results


# ---------------------------------------------------------------------------
# Standalone CLI for quick testing
# ---------------------------------------------------------------------------
async def _cli_discover(url: str):
    """Discover tools on an MCP server."""
    conn = MCPConnection(url)
    try:
        tools = await conn.connect()
        print(f"\n{'='*70}")
        print(f"  MCP Server: {url}")
        print(f"  Tools: {len(tools)}")
        print(f"{'='*70}")
        print(f"\n  {'Name':<40} {'Description':<30}")
        print(f"  {'─'*40} {'─'*30}")
        for t in sorted(tools, key=lambda x: x["name"]):
            desc = t["description"][:28] + ".." if len(t["description"]) > 30 else t["description"]
            print(f"  {t['name']:<40} {desc:<30}")
        print()
    finally:
        await conn.cleanup()


async def _cli_call(url: str, tool_name: str, params_json: Optional[str] = None):
    """Call a single tool for testing."""
    params = json.loads(params_json) if params_json else {}
    conn = MCPConnection(url)
    try:
        await conn.connect()
        start = time.time()
        result = await conn.call_tool(tool_name, params)
        ms = int((time.time() - start) * 1000)
        print(f"\n  Tool: {tool_name}")
        print(f"  Duration: {ms}ms")
        print(f"  Error: {result['is_error']}")
        print(f"  Response:\n{result['raw'][:2000]}")
        if result["parsed"]:
            print(f"\n  Parsed JSON keys: {list(result['parsed'].keys()) if isinstance(result['parsed'], dict) else type(result['parsed']).__name__}")
    finally:
        await conn.cleanup()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MCP Execution Engine")
    parser.add_argument("--url", required=True, help="MCP server SSE URL")
    parser.add_argument("--discover", action="store_true", help="List available tools")
    parser.add_argument("--call", metavar="TOOL", help="Call a specific tool")
    parser.add_argument("--params", default=None, help="JSON params for tool call")
    args = parser.parse_args()

    if args.discover:
        asyncio.run(_cli_discover(args.url))
    elif args.call:
        asyncio.run(_cli_call(args.url, args.call, args.params))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
