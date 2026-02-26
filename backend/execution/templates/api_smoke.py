"""
QAForge -- API Smoke Test Template.

Executes a single HTTP request and validates:
  1. Status code matches expected
  2. Expected fields exist in JSON response
  3. Response time within threshold
  4. Optional response body pattern matching

LLM-extracted params schema:
{
  "method": "GET",
  "endpoint": "/api/users",
  "expected_status": 200,
  "expected_fields": ["id", "name", "email"],
  "headers": {"Authorization": "Bearer ..."},
  "body": null,
  "query_params": {"page": 1},
  "max_response_time_ms": 5000,
  "expected_body_contains": null
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
    Run an API smoke test.

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

    # -- Build request --
    method = (params.get("method") or "GET").upper()
    endpoint = params.get("endpoint", "/")
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    url = f"{base_url}{endpoint}"

    headers = {**default_headers, **(params.get("headers") or {})}

    # Always apply connection-level auth (override LLM-extracted auth to prevent
    # stale or wrong tokens). Skip only for explicit login/auth endpoints.
    is_auth_endpoint = any(seg in endpoint.lower() for seg in ["/auth/login", "/auth/register", "/auth/token"])
    if not is_auth_endpoint:
        if auth_type == "bearer" and auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        elif auth_type == "api_key" and auth_token:
            headers["X-API-Key"] = auth_token

    body = params.get("body")
    query_params = params.get("query_params")
    expected_status = params.get("expected_status", 200)
    expected_fields: List[str] = params.get("expected_fields") or []
    max_response_time_ms = params.get("max_response_time_ms", 5000)
    expected_body_contains: Optional[str] = params.get("expected_body_contains")

    assertions: List[Dict[str, Any]] = []
    logs: List[str] = []
    passed = True
    response_preview = None
    status_code = None
    latency_ms = 0.0

    logs.append(f"Sending {method} {url}")
    if "Authorization" in headers:
        logs.append(f"  Auth: Bearer ***{headers['Authorization'][-10:]}")
    elif "X-API-Key" in headers:
        logs.append(f"  Auth: API-Key ***{headers['X-API-Key'][-10:]}")
    else:
        logs.append(f"  Auth: none")
    if query_params:
        logs.append(f"  Query params: {query_params}")
    if body:
        logs.append(f"  Request body: {_truncate(str(body), 200)}")

    try:
        async with httpx.AsyncClient(verify=False, timeout=30, follow_redirects=True) as client:
            start = time.perf_counter()
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if method in ("POST", "PUT", "PATCH") else None,
                params=query_params,
            )
            latency_ms = (time.perf_counter() - start) * 1000

        status_code = resp.status_code
        logs.append(f"Response: {status_code} ({latency_ms:.0f}ms)")

        # Try to parse JSON
        try:
            resp_json = resp.json()
            response_preview = _truncate(str(resp_json), 500)
        except Exception:
            resp_json = None
            response_preview = _truncate(resp.text, 500)

        # -- Assertion 1: Status code --
        status_ok = status_code == expected_status
        assertions.append({
            "type": "status_code",
            "expected": expected_status,
            "actual": status_code,
            "passed": status_ok,
        })
        if not status_ok:
            passed = False
            logs.append(f"  FAIL: Expected status {expected_status}, got {status_code}")

        # -- Assertion 2: Expected fields --
        if expected_fields and resp_json is not None:
            # Handle both dict and list-of-dicts
            check_obj = resp_json
            if isinstance(resp_json, list) and len(resp_json) > 0:
                check_obj = resp_json[0]

            if isinstance(check_obj, dict):
                for field_name in expected_fields:
                    field_exists = _check_field(check_obj, field_name)
                    assertions.append({
                        "type": "field_exists",
                        "field": field_name,
                        "passed": field_exists,
                    })
                    if not field_exists:
                        passed = False
                        logs.append(f"  FAIL: Expected field '{field_name}' not found")
            else:
                logs.append("  WARN: Response is not a JSON object/array — skipping field checks")

        # -- Assertion 3: Response time --
        time_ok = latency_ms <= max_response_time_ms
        assertions.append({
            "type": "response_time",
            "max_ms": max_response_time_ms,
            "actual_ms": round(latency_ms, 1),
            "passed": time_ok,
        })
        if not time_ok:
            passed = False
            logs.append(f"  FAIL: Response took {latency_ms:.0f}ms (max: {max_response_time_ms}ms)")

        # -- Assertion 4: Body contains --
        if expected_body_contains:
            # Ensure it's a string (LLM sometimes extracts a dict)
            if not isinstance(expected_body_contains, str):
                expected_body_contains = str(expected_body_contains)
            body_text = resp.text
            contains_ok = expected_body_contains.lower() in body_text.lower()
            assertions.append({
                "type": "body_contains",
                "expected": expected_body_contains,
                "passed": contains_ok,
            })
            if not contains_ok:
                passed = False
                logs.append(f"  FAIL: Response body does not contain '{expected_body_contains}'")

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
        logs.append("Request timed out (30s)")
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

    return {
        "passed": passed,
        "assertions": assertions,
        "logs": logs,
        "details": {
            "url": url,
            "method": method,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 1),
            "response_preview": response_preview,
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(s: str, max_len: int = 300) -> str:
    """Truncate a string with ellipsis if too long."""
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _check_field(obj: dict, field_path: str) -> bool:
    """Check if a field exists, supporting dot notation (e.g. 'data.users')."""
    parts = field_path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and len(current) > 0:
            current = current[0]
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        else:
            return False
    return True
