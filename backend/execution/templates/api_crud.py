"""
QAForge -- API CRUD Lifecycle Template.

Executes a full Create-Read-Update-Delete lifecycle:
  1. POST   — create a resource
  2. GET    — verify it exists
  3. PUT    — update the resource
  4. DELETE — remove it
  5. GET    — verify it's gone (expect 404)

LLM-extracted params schema:
{
  "resource_endpoint": "/api/users",
  "create_body": {"name": "Test User", "email": "test@example.com"},
  "update_body": {"name": "Updated User"},
  "id_field": "id",
  "headers": {},
  "expected_create_status": 201,
  "expected_read_status": 200,
  "expected_update_status": 200,
  "expected_delete_status": 200,
  "expected_fields": ["id", "name"]
}
"""

import logging
import time
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


async def execute(
    params: Dict[str, Any],
    connection_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run a full CRUD lifecycle test.

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

    endpoint = params.get("resource_endpoint", "")
    if not endpoint:
        return {
            "passed": False,
            "assertions": [{"type": "param_validation", "expected": "valid resource_endpoint", "actual": "missing", "passed": False, "message": "No resource_endpoint provided by LLM extraction"}],
            "logs": ["FAIL: No resource_endpoint provided. The LLM did not extract a valid endpoint path from the test case."],
            "details": {"template": "api_crud"},
        }
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    url = f"{base_url}{endpoint}"

    headers = {**default_headers, **(params.get("headers") or {})}
    headers.setdefault("Content-Type", "application/json")
    # Always apply connection-level auth (override LLM-extracted auth)
    if auth_type == "bearer" and auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    elif auth_type == "api_key" and auth_token:
        headers["X-API-Key"] = auth_token

    create_body = params.get("create_body", {})
    update_body = params.get("update_body", {})
    id_field = params.get("id_field", "id")
    expected_create_status = params.get("expected_create_status", 201)
    expected_read_status = params.get("expected_read_status", 200)
    expected_update_status = params.get("expected_update_status", 200)
    expected_delete_status = params.get("expected_delete_status", 200)
    expected_fields: List[str] = params.get("expected_fields") or []

    assertions: List[Dict[str, Any]] = []
    logs: List[str] = []
    passed = True
    total_start = time.perf_counter()
    created_id = None
    step_details = {}

    try:
        async with httpx.AsyncClient(verify=False, timeout=30, follow_redirects=True) as client:

            # Log auth state
            if "Authorization" in headers:
                logs.append(f"Auth: Bearer ***{headers['Authorization'][-10:]}")
            else:
                logs.append("Auth: none")

            # ── Step 1: CREATE ──
            logs.append(f"[1/5] POST {url}")
            start = time.perf_counter()
            resp = await client.post(url, json=create_body, headers=headers)
            latency = (time.perf_counter() - start) * 1000

            create_ok = resp.status_code == expected_create_status
            assertions.append({
                "type": "create_status",
                "step": "POST (create)",
                "expected": expected_create_status,
                "actual": resp.status_code,
                "passed": create_ok,
            })
            logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")

            if not create_ok:
                passed = False
                logs.append(f"  FAIL: Expected {expected_create_status}, got {resp.status_code}")
                step_details["create"] = {"status": resp.status_code, "body": _safe_json(resp)}
                # Abort early if create fails
                return _build_result(passed, assertions, logs, step_details, total_start)

            try:
                created = resp.json()
                created_id = _extract_id(created, id_field)
                step_details["create"] = {"status": resp.status_code, "id": str(created_id)}
                logs.append(f"  Created resource with {id_field}={created_id}")
            except Exception:
                passed = False
                logs.append("  FAIL: Could not parse create response as JSON")
                return _build_result(passed, assertions, logs, step_details, total_start)

            # Validate expected fields on create response
            if expected_fields and isinstance(created, dict):
                for f in expected_fields:
                    exists = f in created
                    assertions.append({
                        "type": "create_field_exists",
                        "field": f,
                        "passed": exists,
                    })
                    if not exists:
                        passed = False
                        logs.append(f"  FAIL: Field '{f}' missing from create response")

            # ── Step 2: READ ──
            read_url = f"{url}/{created_id}"
            logs.append(f"[2/5] GET {read_url}")
            start = time.perf_counter()
            resp = await client.get(read_url, headers=headers)
            latency = (time.perf_counter() - start) * 1000

            read_ok = resp.status_code == expected_read_status
            assertions.append({
                "type": "read_status",
                "step": "GET (read)",
                "expected": expected_read_status,
                "actual": resp.status_code,
                "passed": read_ok,
            })
            logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")
            if not read_ok:
                passed = False
                logs.append(f"  FAIL: Expected {expected_read_status}, got {resp.status_code}")
            step_details["read"] = {"status": resp.status_code}

            # ── Step 3: UPDATE ──
            if update_body:
                logs.append(f"[3/5] PUT {read_url}")
                start = time.perf_counter()
                resp = await client.put(read_url, json=update_body, headers=headers)
                latency = (time.perf_counter() - start) * 1000

                update_ok = resp.status_code == expected_update_status
                assertions.append({
                    "type": "update_status",
                    "step": "PUT (update)",
                    "expected": expected_update_status,
                    "actual": resp.status_code,
                    "passed": update_ok,
                })
                logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")
                if not update_ok:
                    passed = False
                    logs.append(f"  FAIL: Expected {expected_update_status}, got {resp.status_code}")
                step_details["update"] = {"status": resp.status_code}

                # Verify update applied
                if update_ok:
                    try:
                        updated = resp.json()
                        for key, val in update_body.items():
                            if isinstance(updated, dict) and updated.get(key) == val:
                                assertions.append({
                                    "type": "update_field_value",
                                    "field": key,
                                    "expected": val,
                                    "actual": updated.get(key),
                                    "passed": True,
                                })
                            elif isinstance(updated, dict):
                                assertions.append({
                                    "type": "update_field_value",
                                    "field": key,
                                    "expected": val,
                                    "actual": updated.get(key),
                                    "passed": False,
                                })
                                passed = False
                                logs.append(f"  FAIL: Field '{key}' expected '{val}', got '{updated.get(key)}'")
                    except Exception:
                        logs.append("  WARN: Could not verify update response body")
            else:
                logs.append("[3/5] PUT — skipped (no update_body provided)")
                step_details["update"] = {"status": "skipped"}

            # ── Step 4: DELETE ──
            logs.append(f"[4/5] DELETE {read_url}")
            start = time.perf_counter()
            resp = await client.delete(read_url, headers=headers)
            latency = (time.perf_counter() - start) * 1000

            delete_ok = resp.status_code == expected_delete_status
            assertions.append({
                "type": "delete_status",
                "step": "DELETE",
                "expected": expected_delete_status,
                "actual": resp.status_code,
                "passed": delete_ok,
            })
            logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")
            if not delete_ok:
                passed = False
                logs.append(f"  FAIL: Expected {expected_delete_status}, got {resp.status_code}")
            step_details["delete"] = {"status": resp.status_code}

            # ── Step 5: VERIFY DELETION ──
            logs.append(f"[5/5] GET {read_url} (expect 404)")
            start = time.perf_counter()
            resp = await client.get(read_url, headers=headers)
            latency = (time.perf_counter() - start) * 1000

            gone_ok = resp.status_code == 404
            assertions.append({
                "type": "verify_deletion",
                "step": "GET after DELETE",
                "expected": 404,
                "actual": resp.status_code,
                "passed": gone_ok,
            })
            logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")
            if not gone_ok:
                passed = False
                logs.append(f"  FAIL: Resource still exists (expected 404, got {resp.status_code})")
            step_details["verify_deletion"] = {"status": resp.status_code}

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

    return _build_result(passed, assertions, logs, step_details, total_start)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_result(
    passed: bool,
    assertions: list,
    logs: list,
    step_details: dict,
    total_start: float,
) -> Dict[str, Any]:
    total_ms = (time.perf_counter() - total_start) * 1000
    return {
        "passed": passed,
        "assertions": assertions,
        "logs": logs,
        "details": {
            "template": "api_crud",
            "total_duration_ms": round(total_ms, 1),
            "steps": step_details,
        },
    }


def _extract_id(data: Any, id_field: str) -> Any:
    """Extract the resource ID from a response (dict or nested)."""
    if isinstance(data, dict):
        # Try direct field
        if id_field in data:
            return data[id_field]
        # Try nested data.id pattern
        if "data" in data and isinstance(data["data"], dict):
            return data["data"].get(id_field)
    return None


def _safe_json(resp: httpx.Response) -> Any:
    """Safely try to parse response JSON."""
    try:
        return resp.json()
    except Exception:
        return resp.text[:300]
