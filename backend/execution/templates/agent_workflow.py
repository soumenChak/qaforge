"""
QAForge -- AI Agent Workflow Test Template.

Tests multi-step AI agent workflows:
  1. Initialize agent session
  2. Send sequence of messages and verify each response
  3. Check tool/function calls made by agent
  4. Verify conversation flow follows expected path
  5. Test error recovery (invalid input, verify graceful handling)
  6. Measure end-to-end latency

LLM-extracted params schema:
{
  "agent_url": "/api/agent/chat",
  "session_init_endpoint": "/api/agent/session",
  "session_init_body": {"model": "gpt-4", "system_prompt": "You are a helpful assistant."},
  "session_id_field": "session_id",
  "conversation_steps": [
    {
      "user_message": "What's the weather in London?",
      "expected_action": "tool_call",
      "expected_tool_calls": ["get_weather"],
      "expected_patterns": ["London", "temperature"],
      "max_latency_ms": 10000
    },
    {
      "user_message": "Convert that to Celsius",
      "expected_action": "response",
      "expected_patterns": ["Celsius", "degrees"],
      "max_latency_ms": 5000
    }
  ],
  "error_recovery_inputs": [
    {
      "input": "",
      "expected_graceful": true,
      "grace_indicators": ["provide", "try again", "rephrase", "clarify"]
    }
  ],
  "message_field": "message",
  "response_field": "response",
  "tool_calls_field": "tool_calls",
  "headers": {}
}
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


async def execute(
    params: Dict[str, Any],
    connection_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run an AI agent workflow test with multi-step conversation.

    Args:
        params: LLM-extracted test parameters.
        connection_config: Connection profile config (base_url, headers, auth).

    Returns:
        Standardised result dict with passed, assertions, logs, details.
    """
    base_url = connection_config.get("base_url", "").rstrip("/")
    default_headers = connection_config.get("headers", {})
    auth_type = connection_config.get("auth_type")
    auth_token = connection_config.get("auth_token")

    agent_url = params.get("agent_url", "/api/agent/chat")
    if not agent_url.startswith("/"):
        agent_url = f"/{agent_url}"
    chat_url = f"{base_url}{agent_url}"

    session_init_endpoint = params.get("session_init_endpoint")
    session_init_body = params.get("session_init_body") or {}
    session_id_field = params.get("session_id_field", "session_id")

    conversation_steps: List[Dict] = params.get("conversation_steps") or []
    error_recovery_inputs: List[Dict] = params.get("error_recovery_inputs") or []
    message_field = params.get("message_field", "message")
    response_field = params.get("response_field", "response")
    tool_calls_field = params.get("tool_calls_field", "tool_calls")

    headers = {**default_headers, **(params.get("headers") or {})}
    headers.setdefault("Content-Type", "application/json")
    if auth_type == "bearer" and auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    elif auth_type == "api_key" and auth_token:
        headers["X-API-Key"] = auth_token

    assertions: List[Dict[str, Any]] = []
    logs: List[str] = []
    passed = True
    total_start = time.perf_counter()
    step_results: List[Dict[str, Any]] = []
    session_id: Optional[str] = None

    if not conversation_steps:
        return {
            "passed": False,
            "assertions": [{"type": "steps_provided", "expected": "non-empty", "actual": "empty", "passed": False}],
            "logs": ["No conversation_steps provided"],
            "details": {},
        }

    logs.append(f"Agent Workflow Test: {chat_url}")
    logs.append(f"  Conversation steps: {len(conversation_steps)}")
    logs.append(f"  Error recovery inputs: {len(error_recovery_inputs)}")

    try:
        async with httpx.AsyncClient(verify=False, timeout=60, follow_redirects=True) as client:

            # Log auth state
            if "Authorization" in headers:
                logs.append(f"Auth: Bearer ***{headers['Authorization'][-10:]}")
            else:
                logs.append("Auth: none")

            # -- Step 0: Initialize session (optional) --
            if session_init_endpoint:
                init_url = f"{base_url}{session_init_endpoint}" if session_init_endpoint.startswith("/") else f"{base_url}/{session_init_endpoint}"
                logs.append(f"[Init] POST {init_url} — Initialize session")
                start = time.perf_counter()
                resp = await client.post(init_url, json=session_init_body, headers=headers)
                latency = (time.perf_counter() - start) * 1000
                logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")

                init_ok = resp.status_code in (200, 201)
                assertions.append({
                    "type": "session_init",
                    "expected_status": "200 or 201",
                    "actual": resp.status_code,
                    "passed": init_ok,
                })

                if not init_ok:
                    passed = False
                    logs.append(f"  FAIL: Session init returned {resp.status_code}")
                    return _build_result(passed, assertions, logs, step_results, total_start)

                try:
                    init_data = resp.json()
                    session_id = _extract_field(init_data, session_id_field)
                    logs.append(f"  Session ID: {session_id}")
                except Exception:
                    logs.append("  WARN: Could not extract session ID from init response")

            # -- Conversation steps --
            for i, step in enumerate(conversation_steps):
                user_message = step.get("user_message", "")
                expected_action = step.get("expected_action", "response")
                expected_tool_calls: List[str] = step.get("expected_tool_calls") or []
                expected_patterns: List[str] = step.get("expected_patterns") or []
                max_latency_ms = step.get("max_latency_ms", 10000)

                logs.append(f"[Step {i + 1}/{len(conversation_steps)}] {_truncate(user_message, 80)}")

                # Build request body
                request_body: Dict[str, Any] = {message_field: user_message}
                if session_id:
                    request_body[session_id_field] = session_id

                start = time.perf_counter()
                resp = await client.post(chat_url, json=request_body, headers=headers)
                latency = (time.perf_counter() - start) * 1000
                logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")

                # Check HTTP status
                status_ok = resp.status_code == 200
                assertions.append({
                    "type": "step_status",
                    "step_index": i,
                    "expected": 200,
                    "actual": resp.status_code,
                    "passed": status_ok,
                })
                if not status_ok:
                    passed = False
                    logs.append(f"  FAIL: Expected 200, got {resp.status_code}")
                    step_results.append({"index": i, "status": resp.status_code, "passed": False})
                    continue

                # Parse response
                try:
                    resp_json = resp.json()
                except Exception:
                    passed = False
                    logs.append("  FAIL: Response is not valid JSON")
                    assertions.append({"type": "step_response_format", "step_index": i, "passed": False})
                    continue

                response_text = _extract_response_text(resp_json, response_field)

                # Update session ID if present in response
                if session_id_field in (resp_json if isinstance(resp_json, dict) else {}):
                    session_id = resp_json[session_id_field]

                # Check latency
                latency_ok = latency <= max_latency_ms
                assertions.append({
                    "type": "step_latency",
                    "step_index": i,
                    "max_ms": max_latency_ms,
                    "actual_ms": round(latency, 1),
                    "passed": latency_ok,
                })
                if not latency_ok:
                    passed = False
                    logs.append(f"  FAIL: Latency {latency:.0f}ms exceeds max {max_latency_ms}ms")

                # Check tool/function calls
                if expected_tool_calls and isinstance(resp_json, dict):
                    actual_tool_calls = _extract_tool_calls(resp_json, tool_calls_field)
                    actual_names = [tc.get("name", tc.get("function", "")) if isinstance(tc, dict) else str(tc) for tc in actual_tool_calls]

                    for expected_tool in expected_tool_calls:
                        tool_found = any(expected_tool.lower() in name.lower() for name in actual_names)
                        assertions.append({
                            "type": "tool_call",
                            "step_index": i,
                            "expected_tool": expected_tool,
                            "actual_tools": actual_names,
                            "passed": tool_found,
                        })
                        if not tool_found:
                            passed = False
                            logs.append(f"  FAIL: Expected tool call '{expected_tool}' not found. Actual: {actual_names}")
                        else:
                            logs.append(f"  PASS: Tool call '{expected_tool}' detected")

                # Check expected patterns in response
                for pattern in expected_patterns:
                    import re
                    try:
                        match_found = bool(re.search(pattern, response_text, re.IGNORECASE))
                    except re.error:
                        match_found = pattern.lower() in response_text.lower()

                    assertions.append({
                        "type": "step_pattern",
                        "step_index": i,
                        "pattern": pattern,
                        "passed": match_found,
                    })
                    if not match_found:
                        passed = False
                        logs.append(f"  FAIL: Expected pattern '{pattern}' not found")

                # Verify action type
                if expected_action == "tool_call" and isinstance(resp_json, dict):
                    actual_tools = _extract_tool_calls(resp_json, tool_calls_field)
                    action_ok = len(actual_tools) > 0
                    assertions.append({
                        "type": "expected_action",
                        "step_index": i,
                        "expected": "tool_call",
                        "actual": "tool_call" if action_ok else "response",
                        "passed": action_ok,
                    })
                    if not action_ok:
                        passed = False
                        logs.append("  FAIL: Expected tool_call action but none found")

                step_results.append({
                    "index": i,
                    "status": resp.status_code,
                    "latency_ms": round(latency, 1),
                    "response_preview": _truncate(response_text, 200),
                })

            # -- Error recovery tests --
            for i, er in enumerate(error_recovery_inputs):
                bad_input = er.get("input", "")
                expected_graceful = er.get("expected_graceful", True)
                grace_indicators: List[str] = er.get("grace_indicators") or [
                    "provide", "try again", "rephrase", "clarify", "sorry",
                    "error", "invalid", "please",
                ]

                display_input = repr(bad_input) if not bad_input else _truncate(bad_input, 60)
                logs.append(f"[Error Recovery {i + 1}/{len(error_recovery_inputs)}] Input: {display_input}")

                request_body = {message_field: bad_input}
                if session_id:
                    request_body[session_id_field] = session_id

                start = time.perf_counter()
                resp = await client.post(chat_url, json=request_body, headers=headers)
                latency = (time.perf_counter() - start) * 1000
                logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")

                # Graceful = did not crash (no 500) and responded meaningfully
                not_crashed = resp.status_code < 500
                graceful_response = False

                if resp.status_code in (200, 400, 422):
                    try:
                        resp_json = resp.json()
                        response_text = _extract_response_text(resp_json, response_field)
                        response_lower = response_text.lower()
                        graceful_response = any(ind.lower() in response_lower for ind in grace_indicators)
                    except Exception:
                        pass
                    # 400/422 status codes themselves indicate graceful rejection
                    if resp.status_code in (400, 422):
                        graceful_response = True

                is_graceful = not_crashed and (graceful_response or resp.status_code in (400, 422))
                recovery_ok = is_graceful if expected_graceful else not is_graceful

                assertions.append({
                    "type": "error_recovery",
                    "recovery_index": i,
                    "expected_graceful": expected_graceful,
                    "status_code": resp.status_code,
                    "not_crashed": not_crashed,
                    "graceful_response": graceful_response,
                    "passed": recovery_ok,
                })
                if not recovery_ok:
                    passed = False
                    logs.append(f"  FAIL: Error recovery — expected graceful={expected_graceful}, got status={resp.status_code}")
                else:
                    logs.append(f"  PASS: Error handled gracefully")

    except httpx.ConnectError as exc:
        passed = False
        logs.append(f"Connection failed: {exc}")
        assertions.append({
            "type": "connection",
            "expected": "reachable",
            "actual": "connection_error",
            "passed": False,
        })
    except httpx.TimeoutException:
        passed = False
        logs.append("Request timed out (60s)")
        assertions.append({
            "type": "connection",
            "expected": "reachable",
            "actual": "timeout",
            "passed": False,
        })
    except Exception as exc:
        passed = False
        logs.append(f"Unexpected error: {type(exc).__name__}: {exc}")
        assertions.append({
            "type": "execution",
            "expected": "success",
            "actual": str(exc),
            "passed": False,
        })

    return _build_result(passed, assertions, logs, step_results, total_start)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_result(
    passed: bool,
    assertions: list,
    logs: list,
    step_results: list,
    total_start: float,
) -> Dict[str, Any]:
    total_ms = (time.perf_counter() - total_start) * 1000
    return {
        "passed": passed,
        "assertions": assertions,
        "logs": logs,
        "details": {
            "template": "agent_workflow",
            "total_duration_ms": round(total_ms, 1),
            "steps_completed": len(step_results),
            "step_results": step_results,
        },
    }


def _truncate(s: str, max_len: int = 300) -> str:
    """Truncate a string with ellipsis if too long."""
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _extract_field(data: Any, field: str) -> Any:
    """Extract a field from response data, supporting nested dicts."""
    if isinstance(data, dict):
        if field in data:
            return data[field]
        if "data" in data and isinstance(data["data"], dict):
            return data["data"].get(field)
    return None


def _extract_response_text(resp_json: Any, response_field: str) -> str:
    """Extract the response text from various agent API response formats."""
    if isinstance(resp_json, str):
        return resp_json

    if isinstance(resp_json, dict):
        # Direct field
        if response_field in resp_json:
            val = resp_json[response_field]
            return str(val) if val is not None else ""

        # OpenAI-style: choices[0].message.content
        choices = resp_json.get("choices")
        if isinstance(choices, list) and len(choices) > 0:
            msg = choices[0].get("message") or {}
            if isinstance(msg, dict) and "content" in msg:
                return str(msg["content"])

        # Common patterns
        for key in ["response", "text", "output", "answer", "content", "result", "reply"]:
            if key in resp_json:
                val = resp_json[key]
                if isinstance(val, str):
                    return val

    return str(resp_json)[:500]


def _extract_tool_calls(resp_json: dict, tool_calls_field: str) -> List[Any]:
    """Extract tool/function calls from agent response."""
    # Direct field
    if tool_calls_field in resp_json:
        val = resp_json[tool_calls_field]
        return val if isinstance(val, list) else [val]

    # OpenAI-style: choices[0].message.tool_calls
    choices = resp_json.get("choices")
    if isinstance(choices, list) and len(choices) > 0:
        msg = choices[0].get("message") or {}
        if isinstance(msg, dict):
            tc = msg.get("tool_calls") or msg.get("function_call")
            if tc:
                return tc if isinstance(tc, list) else [tc]

    # Common patterns
    for key in ["tool_calls", "function_calls", "actions", "tools_used"]:
        if key in resp_json:
            val = resp_json[key]
            return val if isinstance(val, list) else [val]

    return []
