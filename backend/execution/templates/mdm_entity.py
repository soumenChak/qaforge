"""
QAForge -- MDM Entity Test Template.

Tests Reltio/Semarchy MDM entity operations:
  1. Create entity via POST
  2. Read entity via GET and validate fields
  3. Update entity and verify changes
  4. Match test: create duplicate entity, verify match detected
  5. Merge test: merge two entities, verify golden record
  6. Cleanup: delete test entities

LLM-extracted params schema:
{
  "entity_type": "configuration/entityTypes/HCP",
  "entity_data": {"attributes": {"FirstName": [{"value": "John"}], "LastName": [{"value": "Doe"}]}},
  "match_attributes": ["FirstName", "LastName"],
  "duplicate_entity_data": null,
  "expected_create_status": 200,
  "expected_read_status": 200,
  "expected_update_status": 200,
  "update_data": {"attributes": {"FirstName": [{"value": "Jane"}]}},
  "match_endpoint": "/match",
  "merge_endpoint": "/merge",
  "id_field": "uri",
  "expected_fields": ["uri", "attributes"]
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
    Run an MDM entity lifecycle test (CRUD + match + merge).

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

    entity_type = params.get("entity_type", "entities")
    entity_data = params.get("entity_data", {})
    match_attributes: List[str] = params.get("match_attributes") or []
    duplicate_entity_data = params.get("duplicate_entity_data")
    update_data = params.get("update_data", {})
    expected_create_status = params.get("expected_create_status", 200)
    expected_read_status = params.get("expected_read_status", 200)
    expected_update_status = params.get("expected_update_status", 200)
    match_endpoint = params.get("match_endpoint", "/match")
    merge_endpoint = params.get("merge_endpoint", "/merge")
    id_field = params.get("id_field", "uri")
    expected_fields: List[str] = params.get("expected_fields") or []

    # Build entity endpoint
    entity_endpoint = entity_type if entity_type.startswith("/") else f"/{entity_type}"
    entity_url = f"{base_url}{entity_endpoint}"

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
    step_details: Dict[str, Any] = {}
    created_ids: List[str] = []

    try:
        async with httpx.AsyncClient(verify=False, timeout=30, follow_redirects=True) as client:

            # Log auth state
            if "Authorization" in headers:
                logs.append(f"Auth: Bearer ***{headers['Authorization'][-10:]}")
            else:
                logs.append("Auth: none")
            logs.append(f"Entity URL: {entity_url}")

            # -- Step 1: CREATE entity --
            logs.append(f"[1/6] POST {entity_url} — Create entity")
            start = time.perf_counter()
            resp = await client.post(entity_url, json=entity_data, headers=headers)
            latency = (time.perf_counter() - start) * 1000

            create_ok = resp.status_code == expected_create_status
            assertions.append({
                "type": "create_entity",
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
                return _build_result(passed, assertions, logs, step_details, total_start)

            try:
                created = resp.json()
                entity_id = _extract_id(created, id_field)
                if entity_id:
                    created_ids.append(entity_id)
                step_details["create"] = {"status": resp.status_code, "id": str(entity_id)}
                logs.append(f"  Created entity with {id_field}={entity_id}")
            except Exception:
                passed = False
                logs.append("  FAIL: Could not parse create response as JSON")
                return _build_result(passed, assertions, logs, step_details, total_start)

            # -- Step 2: READ entity and validate fields --
            read_url = f"{entity_url}/{entity_id}" if entity_id else entity_url
            logs.append(f"[2/6] GET {read_url} — Read entity")
            start = time.perf_counter()
            resp = await client.get(read_url, headers=headers)
            latency = (time.perf_counter() - start) * 1000

            read_ok = resp.status_code == expected_read_status
            assertions.append({
                "type": "read_entity",
                "step": "GET (read)",
                "expected": expected_read_status,
                "actual": resp.status_code,
                "passed": read_ok,
            })
            logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")
            if not read_ok:
                passed = False
                logs.append(f"  FAIL: Expected {expected_read_status}, got {resp.status_code}")

            # Validate expected fields
            if read_ok and expected_fields:
                try:
                    read_data = resp.json()
                    check_obj = read_data
                    if isinstance(read_data, list) and len(read_data) > 0:
                        check_obj = read_data[0]
                    if isinstance(check_obj, dict):
                        for field in expected_fields:
                            exists = _check_field(check_obj, field)
                            assertions.append({
                                "type": "entity_field_exists",
                                "field": field,
                                "passed": exists,
                            })
                            if not exists:
                                passed = False
                                logs.append(f"  FAIL: Expected field '{field}' not found")
                except Exception:
                    logs.append("  WARN: Could not parse read response for field validation")

            step_details["read"] = {"status": resp.status_code}

            # -- Step 3: UPDATE entity --
            if update_data:
                logs.append(f"[3/6] PUT {read_url} — Update entity")
                start = time.perf_counter()
                resp = await client.put(read_url, json=update_data, headers=headers)
                latency = (time.perf_counter() - start) * 1000

                update_ok = resp.status_code == expected_update_status
                assertions.append({
                    "type": "update_entity",
                    "step": "PUT (update)",
                    "expected": expected_update_status,
                    "actual": resp.status_code,
                    "passed": update_ok,
                })
                logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")
                if not update_ok:
                    passed = False
                    logs.append(f"  FAIL: Expected {expected_update_status}, got {resp.status_code}")

                # Verify update applied by re-reading
                if update_ok:
                    resp = await client.get(read_url, headers=headers)
                    try:
                        updated = resp.json()
                        if isinstance(updated, dict):
                            for key, val in update_data.items():
                                actual_val = updated.get(key)
                                if actual_val == val:
                                    assertions.append({
                                        "type": "update_verified",
                                        "field": key,
                                        "passed": True,
                                    })
                                else:
                                    assertions.append({
                                        "type": "update_verified",
                                        "field": key,
                                        "expected": str(val)[:100],
                                        "actual": str(actual_val)[:100],
                                        "passed": False,
                                    })
                                    passed = False
                                    logs.append(f"  FAIL: Field '{key}' not updated as expected")
                    except Exception:
                        logs.append("  WARN: Could not verify update response body")
                step_details["update"] = {"status": resp.status_code}
            else:
                logs.append("[3/6] UPDATE — skipped (no update_data provided)")
                step_details["update"] = {"status": "skipped"}

            # -- Step 4: MATCH test — create duplicate, check match detection --
            if match_attributes:
                dup_data = duplicate_entity_data or entity_data
                logs.append(f"[4/6] POST {entity_url} — Create duplicate for match test")
                start = time.perf_counter()
                resp = await client.post(entity_url, json=dup_data, headers=headers)
                latency = (time.perf_counter() - start) * 1000
                logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")

                dup_id = None
                try:
                    dup_created = resp.json()
                    dup_id = _extract_id(dup_created, id_field)
                    if dup_id:
                        created_ids.append(dup_id)
                    logs.append(f"  Duplicate entity {id_field}={dup_id}")
                except Exception:
                    logs.append("  WARN: Could not parse duplicate create response")

                # Call match endpoint
                match_url = f"{base_url}{match_endpoint}"
                match_payload = {
                    "entity_type": entity_type,
                    "attributes": {attr: entity_data.get("attributes", {}).get(attr) for attr in match_attributes},
                }
                logs.append(f"  POST {match_url} — Check match")
                start = time.perf_counter()
                resp = await client.post(match_url, json=match_payload, headers=headers)
                latency = (time.perf_counter() - start) * 1000
                logs.append(f"  Match response: {resp.status_code} ({latency:.0f}ms)")

                match_ok = resp.status_code in (200, 201)
                match_found = False
                if match_ok:
                    try:
                        match_result = resp.json()
                        # Check if matches/candidates returned (various MDM API formats)
                        if isinstance(match_result, list):
                            match_found = len(match_result) > 0
                        elif isinstance(match_result, dict):
                            matches = match_result.get("matches") or match_result.get("candidates") or match_result.get("results") or []
                            match_found = len(matches) > 0
                    except Exception:
                        logs.append("  WARN: Could not parse match response")

                assertions.append({
                    "type": "match_detection",
                    "step": "POST (match)",
                    "match_found": match_found,
                    "passed": match_found,
                })
                if not match_found:
                    passed = False
                    logs.append("  FAIL: No match detected for duplicate entity")
                else:
                    logs.append("  PASS: Match detected for duplicate entity")

                step_details["match"] = {"status": resp.status_code, "match_found": match_found}
            else:
                logs.append("[4/6] MATCH — skipped (no match_attributes provided)")
                step_details["match"] = {"status": "skipped"}

            # -- Step 5: MERGE test --
            if len(created_ids) >= 2:
                merge_url = f"{base_url}{merge_endpoint}"
                merge_payload = {
                    "winner": created_ids[0],
                    "loser": created_ids[1],
                }
                logs.append(f"[5/6] POST {merge_url} — Merge entities")
                start = time.perf_counter()
                resp = await client.post(merge_url, json=merge_payload, headers=headers)
                latency = (time.perf_counter() - start) * 1000
                logs.append(f"  Response: {resp.status_code} ({latency:.0f}ms)")

                merge_ok = resp.status_code in (200, 201, 204)
                assertions.append({
                    "type": "merge_entities",
                    "step": "POST (merge)",
                    "passed": merge_ok,
                })
                if not merge_ok:
                    passed = False
                    logs.append(f"  FAIL: Merge returned {resp.status_code}")
                else:
                    logs.append("  PASS: Merge completed successfully")

                # Verify golden record: winner should still exist
                if merge_ok:
                    winner_url = f"{entity_url}/{created_ids[0]}"
                    resp = await client.get(winner_url, headers=headers)
                    golden_ok = resp.status_code == 200
                    assertions.append({
                        "type": "golden_record",
                        "step": "GET (verify golden record)",
                        "passed": golden_ok,
                    })
                    if not golden_ok:
                        passed = False
                        logs.append("  FAIL: Golden record (winner) not found after merge")
                    else:
                        logs.append("  PASS: Golden record (winner) exists after merge")

                step_details["merge"] = {"status": resp.status_code}
            else:
                logs.append("[5/6] MERGE — skipped (need 2 entities)")
                step_details["merge"] = {"status": "skipped"}

            # -- Step 6: CLEANUP — delete test entities --
            logs.append(f"[6/6] Cleanup — deleting {len(created_ids)} test entities")
            cleanup_ok = True
            for eid in created_ids:
                del_url = f"{entity_url}/{eid}"
                try:
                    resp = await client.delete(del_url, headers=headers)
                    if resp.status_code not in (200, 204, 404):
                        cleanup_ok = False
                        logs.append(f"  WARN: Delete {eid} returned {resp.status_code}")
                    else:
                        logs.append(f"  Deleted {eid}")
                except Exception as exc:
                    cleanup_ok = False
                    logs.append(f"  WARN: Delete {eid} failed: {exc}")

            assertions.append({
                "type": "cleanup",
                "entities_cleaned": len(created_ids),
                "passed": cleanup_ok,
            })
            step_details["cleanup"] = {"entities": len(created_ids), "ok": cleanup_ok}

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
            "template": "mdm_entity",
            "total_duration_ms": round(total_ms, 1),
            "steps": step_details,
        },
    }


def _extract_id(data: Any, id_field: str) -> Any:
    """Extract the entity ID from a response (dict or nested)."""
    if isinstance(data, dict):
        if id_field in data:
            return data[id_field]
        if "data" in data and isinstance(data["data"], dict):
            return data["data"].get(id_field)
        # Common MDM patterns
        for key in ["id", "uri", "entityId", "objectId"]:
            if key in data:
                return data[key]
    return None


def _safe_json(resp: httpx.Response) -> Any:
    """Safely try to parse response JSON."""
    try:
        return resp.json()
    except Exception:
        return resp.text[:300]


def _check_field(obj: dict, field_path: str) -> bool:
    """Check if a field exists, supporting dot notation (e.g. 'attributes.name')."""
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
