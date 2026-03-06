"""
QAForge -- Execution Engine (Core Orchestrator).

Drives the end-to-end execution of test cases:
  1. Loads test cases and connection config from DB
  2. For each test case, asks the LLM to extract template parameters
  3. Matches to the best template (api_smoke / api_crud) or falls back to sandbox
  4. Executes the template and captures results
  5. Updates ExecutionRun.results JSONB after each test case (live progress)
  6. Updates TestCase.status to passed/failed

Runs as a FastAPI BackgroundTask with its own DB session.
"""

import asyncio
import json
import logging
import re
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

from sqlalchemy.orm.attributes import flag_modified

from db_session import SessionLocal
from db_models import Connection, ExecutionRun, Project, TestAgent, TestCase

logger = logging.getLogger(__name__)

# -- LLM prompts for parameter extraction (per execution_type) ---------------

PARAM_EXTRACTION_PROMPTS = {
    "api": """You are a QA test execution assistant. Given a test case, extract the parameters needed to execute it via an HTTP API.

Analyze the test case steps and determine which template to use:
- "api_smoke" — for single HTTP request tests (GET/POST/PUT/DELETE an endpoint and verify response)
- "api_crud" — for full CRUD lifecycle tests (Create → Read → Update → Delete flow)

Return ONLY valid JSON with this structure:

For api_smoke:
{
  "template": "api_smoke",
  "params": {
    "method": "GET",
    "endpoint": "<EXACT path from API Endpoints list>",
    "expected_status": 200,
    "expected_fields": ["field1", "field2"],
    "headers": {},
    "body": null,
    "query_params": null,
    "max_response_time_ms": 5000,
    "expected_body_contains": null
  }
}

For expected_body_contains, use one of:
- null (skip body check)
- A string to search for in the response body (case-insensitive substring match)
- A dict where values can be:
  - An exact literal value: {"name": "Admin User"}
  - A type descriptor: {"name": "string", "age": "number", "active": "boolean", "role": "string"}
  - "any" or "non-empty-string" for flexible matching

For api_crud:
{
  "template": "api_crud",
  "params": {
    "resource_endpoint": "<EXACT path from API Endpoints list>",
    "create_body": {"field": "value"},
    "update_body": {"field": "updated_value"},
    "id_field": "id",
    "headers": {},
    "expected_create_status": 201,
    "expected_read_status": 200,
    "expected_update_status": 200,
    "expected_delete_status": 200,
    "expected_fields": ["id", "field"]
  }
}

CRITICAL: For "endpoint" and "resource_endpoint", you MUST use the EXACT path from the "API Endpoints" list provided in the application profile context. NEVER use placeholder paths like "/api/resource" or "/api/endpoint". Match the test case to a real endpoint from the list.

If you cannot determine parameters from the test steps, return:
{"template": "unknown", "params": {}, "reason": "explanation"}

IMPORTANT: Return ONLY the JSON, no markdown fences, no extra text.""",

    "sql": """You are a QA database test execution assistant. Given a test case about ETL/ELT pipelines, data quality, or database validation, extract SQL parameters.

Analyze the test case steps and determine which template to use:
- "db_query" — for single SQL query tests (run a query and validate results: row count, column existence, value checks, null checks)
- "db_reconciliation" — for source-to-target data reconciliation (compare row counts, aggregates, or data between source and target tables)

Return ONLY valid JSON with this structure:

For db_query:
{
  "template": "db_query",
  "params": {
    "query": "SELECT * FROM schema.table WHERE condition",
    "expected_row_count": 10,
    "row_count_operator": "gte",
    "expected_columns": ["col1", "col2"],
    "value_assertions": [
      {"column": "status", "row": 0, "expected": "active", "operator": "eq"}
    ],
    "null_check_columns": ["id", "email"],
    "max_query_time_ms": 10000
  }
}

For db_reconciliation:
{
  "template": "db_reconciliation",
  "params": {
    "source_query": "SELECT COUNT(*) as cnt FROM source_schema.orders",
    "target_query": "SELECT COUNT(*) as cnt FROM target_schema.fact_orders",
    "reconciliation_type": "row_count",
    "tolerance_percent": 0,
    "column_mappings": [
      {"source": "customer_name", "target": "cust_name"}
    ],
    "aggregate_checks": [
      {"source_query": "SELECT SUM(amount) FROM src.orders", "target_query": "SELECT SUM(total) FROM tgt.fact_orders", "tolerance_percent": 0.01}
    ],
    "freshness_query": "SELECT MAX(updated_at) FROM target.fact_orders",
    "freshness_max_hours": 24
  }
}

Use the execution context to understand table names, schema mappings, and ETL/ELT pipeline details.
If you cannot determine parameters, return: {"template": "unknown", "params": {}, "reason": "explanation"}

IMPORTANT: Return ONLY the JSON, no markdown fences, no extra text.""",

    "ui": """You are a QA UI test execution assistant. Given a test case about browser-based UI testing, extract Playwright parameters.

Use the "ui_playwright" template. Extract step-by-step browser actions from the test case.

CRITICAL: Use Playwright SEMANTIC locators (resilient to CSS changes, works on any app including SaaS):
- click_by_role — for buttons, links, headings, tabs, menu items: {"action": "click_by_role", "role": "button", "name": "Submit"}
- click_by_text — for elements with visible text: {"action": "click_by_text", "text": "Create New"}
- click_by_label — for labeled elements (checkboxes, radios): {"action": "click_by_label", "label": "Accept Terms"}
- fill_by_label — for form inputs with labels: {"action": "fill_by_label", "label": "Email", "value": "test@example.com"}
- fill_by_placeholder — for inputs with placeholder text: {"action": "fill_by_placeholder", "placeholder": "Search...", "value": "query"}
- select_by_label — for dropdowns with labels: {"action": "select_by_label", "label": "Status", "value": "Active"}
- assert_visible_by_role — verify element by role: {"action": "assert_visible_by_role", "role": "heading", "name": "Dashboard"}
- assert_visible_by_text — verify text is visible: {"action": "assert_visible_by_text", "text": "Success"}

Fall back to CSS-based actions ONLY if no semantic alternative exists:
- click, fill, select_option, assert_visible, assert_text (these use CSS selectors)

Other actions: navigate, wait, wait_for_selector, press_key, hover, assert_url, assert_element_count, screenshot.

Return ONLY valid JSON:
{
  "template": "ui_playwright",
  "params": {
    "steps": [
      {"action": "navigate", "url": "/page-path"},
      {"action": "click_by_role", "role": "button", "name": "Create New"},
      {"action": "fill_by_label", "label": "Email", "value": "test@example.com"},
      {"action": "fill_by_placeholder", "placeholder": "Search entities...", "value": "John"},
      {"action": "click_by_text", "text": "Submit"},
      {"action": "wait", "ms": 1000},
      {"action": "assert_visible_by_role", "role": "heading", "name": "Dashboard"},
      {"action": "assert_visible_by_text", "text": "Entity created successfully"},
      {"action": "assert_url", "pattern": "/dashboard"},
      {"action": "screenshot", "name": "final-state"}
    ],
    "timeout_ms": 5000,
    "screenshot_on_failure": true
  }
}

PREFER semantic locators from the execution context (discovered UI pages with get_by_role, get_by_label, etc.).
Use the execution context for app-specific elements, page structure, and navigation hints.

If you cannot determine parameters, return: {"template": "unknown", "params": {}, "reason": "explanation"}

IMPORTANT: Return ONLY the JSON, no markdown fences, no extra text.""",

    "mcp": """You are a QA test execution assistant for MCP (Model Context Protocol) servers.
Given a test case, extract the parameters needed to call an MCP tool via SSE transport.

Use the "mcp_tool" template. Extract the tool name and arguments from the test case steps.

Return ONLY valid JSON with this structure:
{
  "template": "mcp_tool",
  "params": {
    "tool_name": "<exact MCP tool name from the test steps>",
    "arguments": {},
    "expected_fields": ["field1", "field2"],
    "expected_body_contains": null,
    "max_response_time_ms": 30000
  }
}

Rules:
- "tool_name" must be the exact MCP tool name (e.g., "health_check_tool", "search_entities_tool")
- "arguments" should contain any input parameters the tool expects (can be empty {} for no-arg tools)
- "expected_fields" is a list of field names expected in the JSON response
- "expected_body_contains" is an optional string to search for in the response (null to skip)
- "max_response_time_ms" defaults to 30000 (30 seconds)

If you cannot determine parameters, return:
{"template": "mcp_tool", "params": {"tool_name": "unknown"}, "reason": "explanation"}

IMPORTANT: Return ONLY the JSON, no markdown fences, no extra text.""",
}

# Legacy fallback for untyped test cases
PARAM_EXTRACTION_PROMPT = PARAM_EXTRACTION_PROMPTS["api"]


def _extract_json_from_llm_response(text: str) -> Optional[Dict]:
    """
    Robustly extract JSON from an LLM response that may contain markdown
    fences, extra commentary, or multiple JSON blocks.

    Returns the parsed dict or None if extraction fails.
    """
    # Strategy 1: Strip markdown fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = cleaned.find("\n")
        if first_newline > 0:
            cleaned = cleaned[first_newline + 1:]
        else:
            cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: Find the first { ... } block using brace matching
    start = text.find("{")
    if start >= 0:
        depth = 0
        end = start
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: Regex for JSON-like block
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            pass

    return None


# ---------------------------------------------------------------------------
# Feature 1: Template Selection Guardrails
# ---------------------------------------------------------------------------

# Patterns for rule-based template correction
_CRUD_VERBS = re.compile(r"\b(create|post|read|get|update|put|delete|remove)\b", re.IGNORECASE)
_SQL_KEYWORDS = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE)\b", re.IGNORECASE)
_CSS_SELECTORS = re.compile(r"(\.[\w-]+|#[\w-]+|\[data-testid|\binput\b|\bbutton\b|\btextarea\b|\.[\w-]+\s*>)", re.IGNORECASE)
_RECONCILIATION = re.compile(r"\b(reconcil|compare\s+tables?|source.*target|row.count.match)\b", re.IGNORECASE)


def _apply_template_guardrails(
    tc: "TestCase",
    extraction: Dict[str, Any],
    execution_type: str,
) -> Dict[str, Any]:
    """
    Rule-based correction of LLM template selection.

    Applies guardrails to prevent common mismatches like:
    - api_smoke chosen for a CRUD lifecycle test
    - api template chosen for a UI test
    - wrong template for SQL/reconciliation tests
    """
    original_template = extraction.get("template", "unknown")

    # Build text from TC steps for pattern matching
    steps_text = ""
    steps = getattr(tc, "test_steps", None) or []
    for step in steps:
        if isinstance(step, dict):
            steps_text += f" {step.get('action', '')} {step.get('expected_result', '')}"
        else:
            steps_text += f" {step}"
    steps_text += f" {getattr(tc, 'title', '')} {getattr(tc, 'description', '')}"

    corrected = original_template

    # Rule 0: Execution type override for MCP
    if execution_type == "mcp" and corrected != "mcp_tool":
        corrected = "mcp_tool"

    # Rule 1: Execution type override for UI
    elif execution_type == "ui" and corrected != "ui_playwright":
        corrected = "ui_playwright"

    # Rule 2: Execution type override for SQL
    elif execution_type == "sql" and corrected not in ("db_query", "db_reconciliation"):
        if _RECONCILIATION.search(steps_text):
            corrected = "db_reconciliation"
        else:
            corrected = "db_query"

    # Rule 3: CRUD detection — if test mentions 2+ distinct CRUD verbs, prefer api_crud
    elif execution_type == "api" and corrected == "api_smoke":
        crud_matches = set()
        for m in _CRUD_VERBS.finditer(steps_text):
            verb = m.group(1).lower()
            if verb in ("create", "post"):
                crud_matches.add("create")
            elif verb in ("read", "get"):
                crud_matches.add("read")
            elif verb in ("update", "put"):
                crud_matches.add("update")
            elif verb in ("delete", "remove"):
                crud_matches.add("delete")
        if len(crud_matches) >= 2:
            corrected = "api_crud"

    # Rule 4: SQL keyword detection
    elif execution_type == "api" and _SQL_KEYWORDS.search(steps_text):
        if _RECONCILIATION.search(steps_text):
            corrected = "db_reconciliation"
        else:
            corrected = "db_query"

    # Rule 5: CSS selector detection (when execution_type wasn't explicitly set to UI)
    elif execution_type == "api" and corrected == "api_smoke":
        css_hits = len(_CSS_SELECTORS.findall(steps_text))
        if css_hits >= 3:  # Multiple CSS selectors strongly indicate UI test
            corrected = "ui_playwright"

    # Rule 6: Reconciliation keyword detection
    elif execution_type == "api" and _RECONCILIATION.search(steps_text):
        corrected = "db_reconciliation"

    if corrected != original_template:
        logger.info(
            "Template guardrail: %s → %s for TC '%s'",
            original_template, corrected, getattr(tc, 'title', 'unknown'),
        )
        extraction["template"] = corrected
        extraction["guardrail_applied"] = {
            "original": original_template,
            "corrected": corrected,
        }

    return extraction


# ---------------------------------------------------------------------------
# Feature 5: Failure-to-Fix Feedback Loop — Failure Analysis
# ---------------------------------------------------------------------------

def _build_proof_artifacts(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build proof artifacts from execution template results.

    Converts raw_response, screenshots, and other details into the
    proof_artifact format expected by the frontend ProofViewer.
    """
    artifacts: List[Dict[str, Any]] = []
    details = result.get("details", {})

    # API / MCP raw response
    raw = details.get("raw_response")
    if raw:
        artifacts.append({
            "proof_type": "api_response",
            "title": "API Response",
            "content": raw if isinstance(raw, dict) else {"body": raw},
        })

    # Screenshots from UI Playwright template
    screenshots = details.get("screenshots", [])
    for ss in screenshots:
        b64 = ss.get("base64") or ss.get("data_base64") or ss.get("image_base64")
        if b64:
            artifacts.append({
                "proof_type": "screenshot",
                "title": ss.get("name", "Screenshot"),
                "content": {"image_base64": b64, "mime_type": "image/png"},
            })

    # Execution logs as proof (only when no other artifacts exist)
    if not artifacts:
        logs = result.get("logs", [])
        if logs:
            artifacts.append({
                "proof_type": "log",
                "title": "Execution Log",
                "content": "\n".join(logs) if isinstance(logs, list) else str(logs),
            })

    return artifacts


def _analyze_failure(test_result: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Analyze a failed test result and return actionable fix suggestions.

    Returns a list of {category, suggestion, detail} dicts.
    """
    suggestions: List[Dict[str, str]] = []
    assertions = test_result.get("assertions", [])
    logs = test_result.get("logs", [])
    details = test_result.get("details", {})
    logs_text = " ".join(logs).lower() if logs else ""

    status_code = details.get("status_code")

    # Check status code patterns
    for assertion in assertions:
        if assertion.get("type") in ("status_code", "create_status", "read_status",
                                      "update_status", "delete_status", "verify_deletion"):
            actual = assertion.get("actual")
            expected = assertion.get("expected")
            if assertion.get("passed"):
                continue

            if actual == 404:
                suggestions.append({
                    "category": "wrong_endpoint",
                    "suggestion": f"Endpoint returned 404 (Not Found). Verify the endpoint path exists in your App Profile's API endpoints list.",
                    "detail": f"Expected status {expected}, got 404",
                })
            elif actual in (401, 403):
                suggestions.append({
                    "category": "auth_issue",
                    "suggestion": "Authentication/authorization failed. Check that auth credentials in App Profile are correct and the token hasn't expired.",
                    "detail": f"Expected status {expected}, got {actual}",
                })
            elif actual == 422:
                suggestions.append({
                    "category": "validation_error",
                    "suggestion": "Request validation failed (422). Check the required_fields for this endpoint in your App Profile — a mandatory field may be missing or have the wrong type.",
                    "detail": f"Expected status {expected}, got 422",
                })
            elif actual is not None and actual >= 500:
                suggestions.append({
                    "category": "server_error",
                    "suggestion": f"Server returned {actual}. This likely indicates a bug in the target application, not in the test case.",
                    "detail": f"Expected status {expected}, got {actual}",
                })
            elif actual is not None and actual != expected:
                suggestions.append({
                    "category": "wrong_status",
                    "suggestion": f"Expected status {expected} but got {actual}. Update the expected_status in the test case or check the App Profile notes for status code corrections.",
                    "detail": f"E.g., some APIs return 200 for POST instead of 201",
                })

        # Check field existence failures
        elif assertion.get("type") in ("field_exists", "create_field_exists") and not assertion.get("passed"):
            field_name = assertion.get("field", "unknown")
            suggestions.append({
                "category": "wrong_field",
                "suggestion": f"Expected field '{field_name}' not found in response. Update response_fields in your App Profile to match the actual API response structure.",
                "detail": f"Field '{field_name}' was expected but not present",
            })

        # Check body_contains failures
        elif assertion.get("type") == "body_contains" and not assertion.get("passed"):
            suggestions.append({
                "category": "wrong_body",
                "suggestion": "Response body doesn't contain expected content. Verify the expected values match the actual API behavior.",
                "detail": f"Expected: {assertion.get('expected', 'N/A')}",
            })

        # Check connection failures
        elif assertion.get("type") == "connection" and not assertion.get("passed"):
            actual = assertion.get("actual", "")
            if "timeout" in str(actual).lower():
                suggestions.append({
                    "category": "timeout",
                    "suggestion": "Request timed out. The target server may be slow or unreachable. Verify api_base_url/app_url in App Profile.",
                    "detail": "Connection timed out after 30s",
                })
            else:
                suggestions.append({
                    "category": "connectivity",
                    "suggestion": "Cannot connect to the target server. Verify the api_base_url or app_url in your App Profile is correct and the server is running.",
                    "detail": f"Connection error: {actual}",
                })

        # Check response time failures
        elif assertion.get("type") == "response_time" and not assertion.get("passed"):
            actual_ms = assertion.get("actual_ms", 0)
            max_ms = assertion.get("max_ms", 5000)
            suggestions.append({
                "category": "slow_response",
                "suggestion": f"Response took {actual_ms}ms (max: {max_ms}ms). Consider increasing max_response_time_ms or investigating server performance.",
                "detail": f"Response time {actual_ms}ms exceeded threshold {max_ms}ms",
            })

    # Check for selector-related failures in logs
    if "selector" in logs_text and ("not found" in logs_text or "timeout" in logs_text):
        suggestions.append({
            "category": "wrong_selector",
            "suggestion": "Element locator not found on the page. Run 'Discover UI' to re-scan pages with AI vision, or update the UI pages section in your App Profile.",
            "detail": "A locator used in the test couldn't be found. Consider re-running UI discovery to refresh semantic locators.",
        })

    # Check template match failure
    template_used = test_result.get("template_used", "")
    if template_used in ("none", "unknown"):
        suggestions.append({
            "category": "no_template",
            "suggestion": "No execution template matched this test case. Ensure the test case has a valid execution_type (api, ui, or sql) and the test steps are specific enough.",
            "detail": f"Template resolution returned: {template_used}",
        })

    # Deduplicate by category
    seen = set()
    unique = []
    for s in suggestions:
        if s["category"] not in seen:
            seen.add(s["category"])
            unique.append(s)

    return unique


def _build_test_case_context(tc: TestCase) -> str:
    """Build a text description of a test case for the LLM."""
    parts = [
        f"Test Case: {tc.title}",
        f"Description: {tc.description or 'N/A'}",
        f"Category: {tc.category or 'N/A'}",
        f"Priority: {tc.priority or 'N/A'}",
    ]
    if tc.preconditions:
        parts.append(f"Preconditions: {tc.preconditions}")

    steps = tc.test_steps or []
    if steps:
        parts.append("Test Steps:")
        for step in steps:
            if isinstance(step, dict):
                sn = step.get("step_number", "?")
                action = step.get("action", "")
                expected = step.get("expected_result", "")
                parts.append(f"  {sn}. {action} → Expected: {expected}")
            else:
                parts.append(f"  - {step}")

    if tc.expected_result:
        parts.append(f"Expected Result: {tc.expected_result}")

    return "\n".join(parts)


def _build_app_profile_context(app_profile: Dict[str, Any], execution_type: str) -> str:
    """Build a context string from the project's app_profile for LLM param extraction."""
    if not app_profile or not isinstance(app_profile, dict):
        return ""

    parts = []

    # URLs
    if app_profile.get("app_url"):
        parts.append(f"Application URL: {app_profile['app_url']}")
    if app_profile.get("api_base_url"):
        parts.append(f"API Base URL: {app_profile['api_base_url']}")

    # Auth config
    auth = app_profile.get("auth", {})
    if auth:
        auth_parts = []
        if auth.get("login_endpoint"):
            auth_parts.append(f"Login endpoint: {auth['login_endpoint']}")
        if auth.get("request_body"):
            auth_parts.append(f"Login request body format: {auth['request_body']}")
        if auth.get("token_header"):
            auth_parts.append(f"Auth header: {auth['token_header']}")
        if auth.get("test_credentials"):
            creds = auth["test_credentials"]
            auth_parts.append(f"Test credentials: email={creds.get('email', '')}, password={creds.get('password', '')}")
        if auth.get("response_fields"):
            auth_parts.append(f"Login response fields: {', '.join(auth['response_fields'])}")
        if auth_parts:
            parts.append("Authentication:\n  " + "\n  ".join(auth_parts))

    # API endpoints (critical for correct paths and field names)
    endpoints = app_profile.get("api_endpoints", [])
    if endpoints and execution_type in ("api", "sql"):
        ep_lines = []
        for ep in endpoints[:30]:
            line = f"  {ep.get('method', 'GET')} {ep.get('path', '')}"
            if ep.get("description"):
                line += f" — {ep['description']}"
            if ep.get("required_fields"):
                line += f"\n    Required fields: {', '.join(ep['required_fields'])}"
            if ep.get("response_fields"):
                line += f"\n    Response fields: {', '.join(ep['response_fields'])}"
            ep_lines.append(line)
        parts.append("API Endpoints (use these EXACT paths):\n" + "\n".join(ep_lines))

    # UI pages (with semantic locators from AI discovery)
    ui_pages = app_profile.get("ui_pages", [])
    if ui_pages and execution_type == "ui":
        page_lines = []
        for pg in ui_pages[:20]:
            line = f"  Route: {pg.get('route', '')}"
            purpose = pg.get("purpose") or pg.get("description", "")
            if purpose:
                line += f" — {purpose}"

            # Rich discovery data: semantic locators (preferred)
            interactions = pg.get("interactions", [])
            if interactions:
                line += "\n    Interactive elements (use these SEMANTIC locators):"
                for elem in interactions[:15]:
                    locator = elem.get("locator", "")
                    elem_name = elem.get("element", "")
                    elem_purpose = elem.get("purpose", "")
                    if locator:
                        line += f"\n      - {elem_name}: {locator}"
                        if elem_purpose:
                            line += f"  ({elem_purpose})"

            # Forms
            forms = pg.get("forms", [])
            if forms:
                for form in forms[:5]:
                    form_name = form.get("name", "Form")
                    fields = form.get("fields", [])
                    if fields:
                        line += f"\n    Form '{form_name}': fields = {', '.join(fields)}"

            # Tables
            tables = pg.get("tables", [])
            if tables:
                for tbl in tables[:5]:
                    tbl_name = tbl.get("name", "Table")
                    cols = tbl.get("columns", [])
                    if cols:
                        line += f"\n    Table '{tbl_name}': columns = {', '.join(cols)}"

            # Navigation hints
            nav = pg.get("navigation", [])
            if nav:
                line += f"\n    Navigation: {'; '.join(nav[:3])}"

            # Legacy fallback: CSS key_elements
            if not interactions and pg.get("key_elements"):
                line += f"\n    CSS selectors (fallback): {', '.join(pg['key_elements'])}"

            page_lines.append(line)
        parts.append("UI Pages (use SEMANTIC locators from discovery, fall back to CSS only if unavailable):\n" + "\n".join(page_lines))

    # RBAC model
    if app_profile.get("rbac_model"):
        parts.append(f"RBAC Model: {app_profile['rbac_model']}")

    # Notes (important corrections and gotchas)
    if app_profile.get("notes"):
        parts.append(f"IMPORTANT Notes:\n{app_profile['notes']}")

    if not parts:
        return ""

    return (
        "\n\n=== APPLICATION PROFILE (use these EXACT URLs, endpoints, field names, and selectors) ===\n"
        "CRITICAL: Do NOT invent or guess URLs, endpoints, field names, CSS selectors, or status codes.\n"
        "Use ONLY the information below. If an endpoint or page is not listed, do not fabricate one.\n\n"
        + "\n\n".join(parts)
    )


async def _extract_params_via_llm(
    test_case_text: str,
    connection_config: Dict[str, Any],
    execution_type: str = "api",
    app_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Use the LLM to extract execution parameters from test case steps."""
    try:
        from core.llm_provider import get_llm_provider

        llm = get_llm_provider()

        # Select the appropriate prompt based on execution_type
        system_prompt = PARAM_EXTRACTION_PROMPTS.get(execution_type, PARAM_EXTRACTION_PROMPT)

        # Add connection context + execution context (user-provided prerequisites)
        context = test_case_text
        if connection_config.get("base_url"):
            context += f"\n\nTarget API base URL: {connection_config['base_url']}"
        if connection_config.get("app_url"):
            context += f"\n\nTarget App URL: {connection_config['app_url']}"
        if connection_config.get("db_url") or connection_config.get("database_url"):
            context += f"\n\nDatabase type: {connection_config.get('db_type', 'postgresql')}"
        if connection_config.get("execution_context"):
            context += f"\n\n--- Execution Context (API docs / ETL mappings / prerequisites) ---\n{connection_config['execution_context']}"

        # Inject app_profile context (exact endpoints, field names, CSS selectors)
        profile_context = _build_app_profile_context(app_profile or {}, execution_type)
        if profile_context:
            context += profile_context

        result = llm.complete(
            system=system_prompt,
            messages=[{"role": "user", "content": context}],
            max_tokens=1024,
            temperature=0.1,
        )

        # Parse JSON from response — robust extraction for Groq/Llama
        text = result.text.strip()
        parsed = _extract_json_from_llm_response(text)
        if parsed is not None:
            return parsed

        # Last resort: try raw parse
        return json.loads(text)

    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM returned invalid JSON for param extraction: %s — raw text: %s", exc, result.text[:300] if hasattr(result, 'text') else 'N/A')
        return {"template": "unknown", "params": {}, "reason": f"Invalid JSON: {exc}"}
    except Exception as exc:
        logger.error("LLM param extraction failed: %s", exc, exc_info=True)
        return {"template": "unknown", "params": {}, "reason": str(exc)}


def _validate_endpoint_against_profile(
    extraction: Dict[str, Any],
    app_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Post-extraction guardrail: correct generic/placeholder endpoints using app_profile."""
    if not app_profile:
        return extraction

    endpoints = app_profile.get("api_endpoints", [])
    if not endpoints:
        return extraction

    template = extraction.get("template", "")
    params = extraction.get("params", {})

    # Determine which param holds the endpoint path
    if template == "api_crud":
        endpoint_key = "resource_endpoint"
    elif template == "api_smoke":
        endpoint_key = "endpoint"
    else:
        return extraction

    extracted_path = params.get(endpoint_key, "")
    if not extracted_path:
        return extraction

    # Build set of known paths (normalised)
    known_paths = set()
    for ep in endpoints:
        p = ep.get("path", "").rstrip("/")
        if p:
            known_paths.add(p.lower())

    # Check if extracted path is a known generic placeholder
    _GENERIC_PATHS = {"/api/resource", "/api/endpoint", "/api/resources", "/resource", "/endpoint"}
    is_generic = extracted_path.lower().rstrip("/") in _GENERIC_PATHS
    is_known = extracted_path.lower().rstrip("/") in known_paths

    if is_generic or (not is_known and known_paths):
        best_match = _find_best_endpoint_match(extracted_path, endpoints, extraction)
        if best_match:
            old_path = params[endpoint_key]
            params[endpoint_key] = best_match
            extraction["params"] = params
            logger.info("Endpoint corrected: '%s' -> '%s'", old_path, best_match)

    return extraction


def _find_best_endpoint_match(
    extracted_path: str,
    endpoints: List[Dict[str, Any]],
    extraction: Dict[str, Any],
) -> Optional[str]:
    """Find the best matching real endpoint from the app_profile."""
    template = extraction.get("template", "")
    params = extraction.get("params", {})

    # Extract resource hints from the path
    path_parts = extracted_path.strip("/").split("/")
    resource_hint = path_parts[-1].lower() if path_parts else ""

    if template == "api_crud":
        # For CRUD, prefer endpoints that support POST (collection endpoints)
        post_endpoints = [ep for ep in endpoints if ep.get("method", "").upper() == "POST"]
        # Filter out auth/login endpoints
        post_endpoints = [ep for ep in post_endpoints
                          if "/auth/" not in ep.get("path", "").lower()
                          and "/login" not in ep.get("path", "").lower()
                          and "/token" not in ep.get("path", "").lower()]
        if len(post_endpoints) == 1:
            return post_endpoints[0]["path"]
        # Try to match by resource name
        if post_endpoints and resource_hint and resource_hint not in ("resource", "resources", "endpoint"):
            for ep in post_endpoints:
                if resource_hint in ep["path"].lower():
                    return ep["path"]
        # Try to match by test case title keywords in extraction
        tc_reason = extraction.get("reason", "")
        for ep in post_endpoints:
            ep_resource = ep["path"].strip("/").split("/")[-1].lower()
            # Check if the endpoint resource name appears in create_body keys
            create_body = params.get("create_body", {})
            if isinstance(create_body, dict):
                body_keys = " ".join(create_body.keys()).lower()
                ep_desc = (ep.get("description", "") or "").lower()
                if ep_resource in body_keys or any(k in ep_desc for k in create_body.keys()):
                    return ep["path"]
        # Fallback: first non-auth POST endpoint
        if post_endpoints:
            return post_endpoints[0]["path"]

    elif template == "api_smoke":
        method = params.get("method", "GET").upper()
        method_endpoints = [ep for ep in endpoints if ep.get("method", "").upper() == method]
        if len(method_endpoints) == 1:
            return method_endpoints[0]["path"]
        # Try resource name matching
        if resource_hint and resource_hint not in ("resource", "resources", "endpoint"):
            for ep in method_endpoints:
                if resource_hint in ep["path"].lower():
                    return ep["path"]

    return None


def _extract_mcp_params_from_steps(tc: "TestCase") -> Dict[str, Any]:
    """
    Extract MCP tool call parameters directly from test case steps.

    MCP test steps contain structured fields (tool_name, tool_params, assertions)
    that can be used directly without LLM extraction.
    """
    steps = getattr(tc, "test_steps", None) or []
    tool_name = ""
    arguments = {}
    expected_fields = []
    expected_contains = None
    max_time_ms = 30000

    for step in steps:
        if not isinstance(step, dict):
            continue
        # Extract tool_name from step
        if step.get("tool_name"):
            tool_name = step["tool_name"]
        # Extract tool_params as arguments
        if step.get("tool_params"):
            arguments = step["tool_params"]
        # Extract assertions for expected_fields and expected_contains
        for assertion in (step.get("assertions") or []):
            if isinstance(assertion, dict):
                atype = assertion.get("type", "")
                if atype == "contains" and assertion.get("value"):
                    expected_contains = assertion["value"]
                elif atype == "response_time_ms" and assertion.get("value"):
                    max_time_ms = assertion["value"]
                elif atype == "has_field" and assertion.get("value"):
                    expected_fields.append(assertion["value"])

    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "expected_fields": expected_fields,
        "expected_body_contains": expected_contains,
        "max_response_time_ms": max_time_ms,
    }


async def _execute_single_test(
    tc: TestCase,
    connection_config: Dict[str, Any],
    agent_config: Optional[Dict[str, Any]] = None,
    app_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a single test case and return the result."""
    start_time = time.perf_counter()
    tc_text = _build_test_case_context(tc)

    # Determine execution type from test case
    execution_type = getattr(tc, "execution_type", "api") or "api"

    # MCP fast-path: skip LLM extraction, use structured step data directly
    if execution_type == "mcp":
        mcp_params = _extract_mcp_params_from_steps(tc)
        template_name = "mcp_tool"
        params = mcp_params
        logger.info("MCP fast-path: tool=%s", mcp_params.get("tool_name", "unknown"))
    else:
        # Step 1: Extract parameters via LLM (using type-specific prompt + app profile)
        extraction = await _extract_params_via_llm(tc_text, connection_config, execution_type, app_profile)

        # Step 1.5: Apply template guardrails (rule-based correction)
        extraction = _apply_template_guardrails(tc, extraction, execution_type)

        # Step 1.6: Validate extracted endpoint against known app_profile endpoints
        if execution_type == "api" and app_profile:
            extraction = _validate_endpoint_against_profile(extraction, app_profile)

        template_name = extraction.get("template", "unknown")
        params = extraction.get("params", {})

    # Step 2: Execute via appropriate template
    from execution.templates import TEMPLATE_REGISTRY

    # Normalise template name (LLMs sometimes use hyphens or mixed case)
    template_name = template_name.lower().replace("-", "_").strip()

    if template_name in TEMPLATE_REGISTRY:
        template_fn = TEMPLATE_REGISTRY[template_name]
        result = await template_fn(params, connection_config)
        result["template_used"] = template_name
    elif template_name == "unknown":
        # No template matched — try sandbox fallback if agent allows it
        if agent_config and agent_config.get("allow_sandbox", False):
            from execution.sandbox import execute_script

            # Ask LLM to generate a test script
            script = await _generate_test_script(tc_text, connection_config)
            if script:
                env_vars = {}
                if connection_config.get("base_url"):
                    env_vars["BASE_URL"] = connection_config["base_url"]
                if connection_config.get("auth_token"):
                    env_vars["AUTH_TOKEN"] = connection_config["auth_token"]
                result = await execute_script(
                    script,
                    timeout=agent_config.get("sandbox_timeout", 30),
                    env_vars=env_vars,
                )
                result["template_used"] = "sandbox"
            else:
                result = {
                    "passed": False,
                    "assertions": [{
                        "type": "template_match",
                        "expected": "matched",
                        "actual": "no_match_no_script",
                        "passed": False,
                    }],
                    "logs": [
                        f"No template matched for this test case",
                        f"Reason: {extraction.get('reason', 'unknown')}",
                        "Sandbox script generation also failed",
                    ],
                    "template_used": "none",
                    "details": {},
                }
        else:
            result = {
                "passed": False,
                "assertions": [{
                    "type": "template_match",
                    "expected": "matched",
                    "actual": "no_match",
                    "passed": False,
                }],
                "logs": [
                    f"No template matched for this test case",
                    f"Reason: {extraction.get('reason', 'unknown')}",
                    "Sandbox execution is disabled for this agent",
                ],
                "template_used": "none",
                "details": {},
            }
    else:
        result = {
            "passed": False,
            "assertions": [{
                "type": "template_match",
                "expected": "known_template",
                "actual": template_name,
                "passed": False,
            }],
            "logs": [f"Unknown template: {template_name}"],
            "template_used": template_name,
            "details": {},
        }

    duration = time.perf_counter() - start_time
    result["duration_seconds"] = round(duration, 2)

    return result


async def _generate_test_script(
    test_case_text: str,
    connection_config: Dict[str, Any],
) -> Optional[str]:
    """Ask the LLM to generate a Python test script as a fallback."""
    try:
        from core.llm_provider import get_llm_provider

        llm = get_llm_provider()

        system_prompt = """You are a QA automation engineer. Generate a Python test script that:
1. Uses the `httpx` library for HTTP requests (already installed)
2. Prints a JSON result to stdout with this structure:
   {"passed": true/false, "assertions": [...], "logs": [...]}
3. Uses environment variables: BASE_URL, AUTH_TOKEN (if applicable)
4. Handles errors gracefully
5. Does NOT use any external test framework (no pytest, unittest)

Return ONLY the Python code, no markdown fences."""

        context = test_case_text
        if connection_config.get("base_url"):
            context += f"\n\nBase URL: {connection_config['base_url']}"

        result = llm.complete(
            system=system_prompt,
            messages=[{"role": "user", "content": context}],
            max_tokens=2048,
            temperature=0.2,
        )

        script = result.text.strip()
        # Strip markdown fences
        if script.startswith("```python"):
            script = script[9:]
        elif script.startswith("```"):
            script = script[3:]
        if script.endswith("```"):
            script = script[:-3]

        return script.strip() if script.strip() else None

    except Exception as exc:
        logger.error("Failed to generate test script: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main execution entry point (runs as BackgroundTask)
# ---------------------------------------------------------------------------

def run_execution(run_id: UUID) -> None:
    """
    Execute a test run. Called as a FastAPI BackgroundTask.

    Creates its own DB session (separate from the request session).
    Updates the ExecutionRun row in real-time with progress.
    """
    # Run the async execution in its own event loop
    # (BackgroundTasks run in a thread, not in the main async loop)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_execute_run(run_id))
    except Exception as exc:
        logger.error("Execution run %s failed: %s", run_id, exc, exc_info=True)
        # Update run status to failed
        _mark_run_failed(run_id, str(exc))
    finally:
        loop.close()


async def _execute_run(run_id: UUID) -> None:
    """Async implementation of the execution run."""
    db = SessionLocal()

    try:
        # Retry-find: the row may not be committed yet if the background task
        # starts before the request session auto-commits.
        run = None
        for attempt in range(5):
            run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
            if run is not None:
                break
            logger.warning("Execution run %s not found (attempt %d/5), retrying...", run_id, attempt + 1)
            await asyncio.sleep(1)
            db.expire_all()  # clear session cache so next query hits DB

        if run is None:
            logger.error("Execution run %s not found after retries", run_id)
            return

        # Mark as running
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.results = {"test_results": [], "summary": {"total": 0, "passed": 0, "failed": 0, "errored": 0, "pass_rate": 0.0}}
        db.commit()

        # Load connection config
        connection_config = {}
        if run.connection_id:
            conn = db.query(Connection).filter(Connection.id == run.connection_id).first()
            if conn:
                connection_config = conn.config or {}

        # ---------- Dynamic token fetch (login) ----------
        # If the connection has login_endpoint + credentials but no static auth_token,
        # call the login endpoint to get a fresh JWT before running tests.
        _login_ep = connection_config.get("login_endpoint")
        _creds = connection_config.get("credentials")
        _base = connection_config.get("base_url", "").rstrip("/")
        if _login_ep and _creds and _base and not connection_config.get("auth_token"):
            _token_field = connection_config.get("token_field", "access_token")
            _login_url = f"{_base}{_login_ep}" if _login_ep.startswith("/") else f"{_base}/{_login_ep}"
            logger.info("Dynamic auth: logging in via %s", _login_url)
            try:
                async with httpx.AsyncClient(verify=False, timeout=15) as _hc:
                    _resp = await _hc.post(_login_url, json=_creds)
                    if _resp.status_code == 200:
                        _data = _resp.json()
                        _token = _data.get(_token_field) or _data.get("access_token") or _data.get("token")
                        if _token:
                            connection_config["auth_token"] = _token
                            logger.info("Dynamic auth: obtained token (%d chars) via %s", len(_token), _token_field)
                        else:
                            logger.warning("Dynamic auth: login 200 but no token field '%s' in response keys: %s",
                                           _token_field, list(_data.keys()))
                    else:
                        logger.warning("Dynamic auth: login returned %d — %s", _resp.status_code, _resp.text[:200])
            except Exception as _exc:
                logger.error("Dynamic auth: login request failed — %s", _exc)
        # ---------- End dynamic token fetch ----------

        # Load project app_profile (contains exact endpoints, field names, CSS selectors)
        app_profile = None
        if run.project_id:
            project = db.query(Project).filter(Project.id == run.project_id).first()
            if project and project.app_profile:
                app_profile = project.app_profile
                logger.info("Loaded app_profile for project %s (%d keys)", project.name, len(app_profile))

        # ---------- OAuth2 client_credentials token fetch ----------
        # If app_profile has OAuth2 auth config and no token yet, fetch one.
        if app_profile and not connection_config.get("auth_token"):
            _auth = app_profile.get("auth", {})
            if _auth.get("type") == "oauth2" and _auth.get("token_url"):
                _token_url = _auth["token_url"]
                _payload = {
                    "grant_type": _auth.get("grant_type", "client_credentials"),
                    "client_id": _auth.get("client_id", ""),
                    "client_secret": _auth.get("client_secret", ""),
                }
                logger.info("OAuth2 auth: requesting token from %s", _token_url)
                try:
                    async with httpx.AsyncClient(verify=False, timeout=15) as _hc:
                        _resp = await _hc.post(_token_url, data=_payload)
                        if _resp.status_code == 200:
                            _data = _resp.json()
                            _token = _data.get("access_token")
                            if _token:
                                connection_config["auth_token"] = _token
                                connection_config["auth_type"] = "bearer"
                                if not connection_config.get("base_url") and app_profile.get("api_base_url"):
                                    connection_config["base_url"] = app_profile["api_base_url"]
                                logger.info("OAuth2 auth: obtained token (%d chars)", len(_token))
                            else:
                                logger.warning("OAuth2 auth: 200 but no access_token in response: %s", list(_data.keys()))
                        else:
                            logger.warning("OAuth2 auth: token request returned %d — %s", _resp.status_code, _resp.text[:200])
                except Exception as _exc:
                    logger.error("OAuth2 auth: token request failed — %s", _exc)
        # ---------- End OAuth2 token fetch ----------

        # Load agent config
        agent_config = None
        if run.test_agent_id:
            agent = db.query(TestAgent).filter(TestAgent.id == run.test_agent_id).first()
            if agent:
                agent_config = agent.config or {}

        # Load test cases
        test_case_ids = run.test_case_ids or []
        test_cases = (
            db.query(TestCase)
            .filter(TestCase.id.in_(test_case_ids))
            .all()
        )

        if not test_cases:
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.results = {
                "test_results": [],
                "summary": {"total": 0, "passed": 0, "failed": 0, "errored": 0, "pass_rate": 0.0},
            }
            db.commit()
            logger.info("Execution run %s completed — no test cases found", run_id)
            return

        total = len(test_cases)
        passed_count = 0
        failed_count = 0
        errored_count = 0
        test_results = []

        for i, tc in enumerate(test_cases):
            # Check if run was cancelled
            db.refresh(run)
            if run.status == "cancelled":
                logger.info("Execution run %s was cancelled at test %d/%d", run_id, i + 1, total)
                break

            logger.info(
                "Executing test %d/%d: %s (%s)",
                i + 1, total, tc.title, tc.test_case_id or tc.id,
            )

            try:
                result = await _execute_single_test(tc, connection_config, agent_config, app_profile)

                test_result = {
                    "test_case_id": str(tc.id),
                    "test_case_display_id": tc.test_case_id or f"TC-{str(tc.id)[:8]}",
                    "title": tc.title,
                    "status": "passed" if result["passed"] else "failed",
                    "duration_seconds": result.get("duration_seconds", 0),
                    "template_used": result.get("template_used", "unknown"),
                    "assertions": result.get("assertions", []),
                    "logs": result.get("logs", []),
                    "details": result.get("details", {}),
                    "error": None,
                }

                # Auto-generate proof_artifacts from execution details
                proof_artifacts = _build_proof_artifacts(result)
                if proof_artifacts:
                    test_result["proof_artifacts"] = proof_artifacts

                if result["passed"]:
                    passed_count += 1
                    tc.status = "passed"
                else:
                    failed_count += 1
                    tc.status = "failed"
                    # Analyze failure and add fix suggestions
                    fix_suggestions = _analyze_failure(result)
                    if fix_suggestions:
                        test_result["fix_suggestions"] = fix_suggestions

                # Persist execution result to test case for historical tracking
                tc.execution_result = {
                    "run_id": str(run_id),
                    "status": test_result["status"],
                    "template_used": test_result.get("template_used", "unknown"),
                    "duration_seconds": test_result.get("duration_seconds", 0),
                    "assertions": test_result.get("assertions", []),
                    "logs": test_result.get("logs", []),
                    "details": test_result.get("details", {}),
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                }
                flag_modified(tc, "execution_result")

            except Exception as exc:
                errored_count += 1
                tc.status = "failed"
                test_result = {
                    "test_case_id": str(tc.id),
                    "test_case_display_id": tc.test_case_id or f"TC-{str(tc.id)[:8]}",
                    "title": tc.title,
                    "status": "error",
                    "duration_seconds": 0,
                    "template_used": "none",
                    "assertions": [],
                    "logs": [f"Execution error: {type(exc).__name__}: {exc}"],
                    "details": {"traceback": traceback.format_exc()[:500]},
                    "error": str(exc),
                }
                logger.error("Test case %s execution error: %s", tc.id, exc, exc_info=True)

                # Analyze the error and add fix suggestions
                error_suggestions = _analyze_failure(test_result)
                if error_suggestions:
                    test_result["fix_suggestions"] = error_suggestions

                # Persist error result to test case
                tc.execution_result = {
                    "run_id": str(run_id),
                    "status": "error",
                    "error": str(exc),
                    "logs": [f"Execution error: {type(exc).__name__}: {exc}"],
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                }
                flag_modified(tc, "execution_result")

            test_results.append(test_result)

            # Update run results in real-time (after each test case)
            pass_rate = round((passed_count / (i + 1)) * 100, 1) if (i + 1) > 0 else 0.0
            run.results = {
                "test_results": test_results,
                "summary": {
                    "total": total,
                    "completed": i + 1,
                    "passed": passed_count,
                    "failed": failed_count,
                    "errored": errored_count,
                    "pass_rate": pass_rate,
                },
            }
            flag_modified(run, "results")
            db.commit()

        # Finalise run
        if run.status != "cancelled":
            run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

        # Final summary
        completed = passed_count + failed_count + errored_count
        pass_rate = round((passed_count / completed) * 100, 1) if completed > 0 else 0.0
        run.results["summary"] = {
            "total": total,
            "completed": completed,
            "passed": passed_count,
            "failed": failed_count,
            "errored": errored_count,
            "pass_rate": pass_rate,
        }
        flag_modified(run, "results")
        db.commit()

        logger.info(
            "Execution run %s completed: %d/%d passed (%.1f%%)",
            run_id, passed_count, total, pass_rate,
        )

    except Exception as exc:
        logger.error("Execution run %s failed: %s", run_id, exc, exc_info=True)
        try:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            if not run.results:
                run.results = {}
            run.results["error"] = str(exc)
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def _mark_run_failed(run_id: UUID, error: str) -> None:
    """Mark a run as failed (called from the outer exception handler)."""
    db = SessionLocal()
    try:
        run = db.query(ExecutionRun).filter(ExecutionRun.id == run_id).first()
        if run:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            run.results = run.results or {}
            run.results["error"] = error
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
