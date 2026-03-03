#!/usr/bin/env python3
"""
Populate the Reltio MDM E2E Demo project with structured executable test data.

Updates:
  - 3 test cases with structured test steps (tool_name, tool_params, assertions)
  - App profile with connections registry (reltio_mcp connection)
  - Test plan with execution_config (playbook metadata)

Usage:
  QAFORGE_API_URL=https://13.233.36.18:8080 \
  QAFORGE_AGENT_KEY=qf_... \
  python scripts/populate_reltio_demo.py
"""

import json
import os
import sys
import urllib3

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = os.environ.get("QAFORGE_API_URL", "https://13.233.36.18:8080")
AGENT_KEY = os.environ.get("QAFORGE_AGENT_KEY", "qf_3aXCESoqp47dZd2kB1QcnHRuNxA7Bysp8W3XdT9Alc8U3dDq3WcIzgfeVbzZxCbV")
PROJECT_ID = "a8cd771e-07fa-4585-886b-0ff69d655f64"

# Login to get a JWT token for the main API (agent key only works for agent endpoints)
LOGIN_EMAIL = "admin@freshgravity.com"
LOGIN_PASSWORD = "admin123"

HEADERS = {"X-Agent-Key": AGENT_KEY}
S = requests.Session()
S.verify = False


def login():
    """Get JWT token for authenticated API calls."""
    r = S.post(f"{API_URL}/api/auth/login", json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD})
    r.raise_for_status()
    token = r.json().get("access_token")
    S.headers["Authorization"] = f"Bearer {token}"
    print(f"  Logged in as {LOGIN_EMAIL}")


def update_test_case(tc_id, payload):
    """Update a test case via the main API."""
    r = S.put(f"{API_URL}/api/projects/{PROJECT_ID}/test-cases/{tc_id}", json=payload)
    r.raise_for_status()
    return r.json()


def update_app_profile(profile):
    """Update project app profile."""
    r = S.put(f"{API_URL}/api/projects/{PROJECT_ID}/app-profile", json=profile)
    r.raise_for_status()
    return r.json()


def create_test_plan(payload):
    """Create a test plan."""
    r = S.post(f"{API_URL}/api/projects/{PROJECT_ID}/test-plans", json=payload)
    if r.status_code == 409 or r.status_code == 400:
        print(f"  Test plan may already exist: {r.status_code}")
        return None
    r.raise_for_status()
    return r.json()


def assign_tc_to_plan(tc_uuid, plan_id):
    """Assign a test case to a test plan."""
    r = S.put(f"{API_URL}/api/projects/{PROJECT_ID}/test-cases/{tc_uuid}", json={"test_plan_id": plan_id})
    r.raise_for_status()


# ═══════════════════════════════════════════════════════════════════════════
# Data definitions
# ═══════════════════════════════════════════════════════════════════════════

TC_001_STEPS = [
    {
        "step_number": 1,
        "action": "Call health_check_tool via Reltio MCP server to verify server is running and accessible",
        "expected_result": "Returns JSON with status 'ok', message 'MCP server is running', tools_count, and transport type",
        "step_type": "mcp",
        "connection_ref": "reltio_mcp",
        "tool_name": "health_check_tool",
        "tool_params": {},
        "assertions": [
            {"type": "json_path", "path": "$.status", "expected": "ok"},
            {"type": "json_path", "path": "$.transport", "expected": "SSE"},
            {"type": "response_time_ms", "operator": "<=", "value": 5000},
        ],
    }
]

TC_002_STEPS = [
    {
        "step_number": 1,
        "action": "Search for entities of type Individual in the Reltio dev tenant using search_entities_tool",
        "expected_result": "Returns list of entities with uri, label, type fields. Entity count should be >= 1",
        "step_type": "mcp",
        "connection_ref": "reltio_mcp",
        "tool_name": "search_entities_tool",
        "tool_params": {
            "filter": "(equals(type,'Individual'))",
            "entity_type": "Individual",
            "max_results": 5,
            "select": "uri,label,type",
        },
        "assertions": [
            {"type": "not_empty"},
            {"type": "json_path", "path": "$.entity_count", "operator": ">=", "value": 1},
        ],
    }
]

TC_003_STEPS = [
    {
        "step_number": 1,
        "action": "Retrieve data model definition (entity types schema) from the Reltio dev tenant via get_data_model_definition_tool",
        "expected_result": "Returns the configuration/entityTypes schema definition with entity type structures and attribute definitions",
        "step_type": "mcp",
        "connection_ref": "reltio_mcp",
        "tool_name": "get_data_model_definition_tool",
        "tool_params": {
            "object_type": ["configuration/entityTypes"],
        },
        "assertions": [
            {"type": "not_empty"},
            {"type": "json_path", "path": "$.response_status", "expected": "success"},
        ],
    }
]

APP_PROFILE = {
    "app_url": "http://localhost:8000/sse",
    "api_base_url": "https://dev.reltio.com/reltio/api/lKF8afvLiCCRsS6",
    "tech_stack": {
        "frontend": "N/A (API-only)",
        "backend": "Python MCP Server",
        "database": "Reltio Cloud MDM",
    },
    "connections": {
        "reltio_mcp": {
            "type": "mcp",
            "transport": "sse",
            "server_url": "http://localhost:8000/sse",
            "description": "Reltio MCP server - 45 tools for entity CRUD, search, data model, match/merge, and analytics",
            "setup_command": "cd /opt/reltio-mcp && source venv/bin/activate && python main.py",
            "env_vars": [
                "RELTIO_TENANT_ID",
                "RELTIO_ENVIRONMENT",
                "RELTIO_CLIENT_ID",
                "RELTIO_CLIENT_SECRET",
                "RELTIO_AUTH_URL",
            ],
        },
        "reltio_api": {
            "type": "rest_api",
            "base_url": "https://dev.reltio.com/reltio/api/lKF8afvLiCCRsS6",
            "auth_type": "oauth2",
            "description": "Reltio REST API direct access for the dev tenant",
            "env_vars": [
                "RELTIO_AUTH_URL",
                "RELTIO_CLIENT_ID",
                "RELTIO_CLIENT_SECRET",
            ],
        },
    },
    "mdm_config": {
        "entity_types": ["Individual", "Organization", "Contact", "HCP_RIH_TRAINING"],
        "source_systems": ["Reltio Dev Tenant lKF8afvLiCCRsS6"],
        "match_rules": "Configured in Reltio tenant - fuzzy match on name + exact match on email",
        "survivorship_rules": "Reltio SRS (Survivorship Rule Set) - most recent wins",
        "crosswalk_model": "Reltio native crosswalk with source system tracking",
        "data_quality_rules": "Completeness checks on required attributes, format validation on email/phone",
    },
    "notes": "MCP server must be running before executing tests. Start with: cd /opt/reltio-mcp && source venv/bin/activate && python main.py",
}

EXECUTION_CONFIG = {
    "environment": "Reltio Dev (tenant: lKF8afvLiCCRsS6)",
    "connection_refs": ["reltio_mcp"],
    "required_env_vars": [
        {"name": "RELTIO_TENANT_ID", "description": "Reltio tenant ID (e.g. lKF8afvLiCCRsS6)"},
        {"name": "RELTIO_ENVIRONMENT", "description": "Reltio environment (dev/sit/uat/prod)"},
        {"name": "RELTIO_CLIENT_ID", "description": "OAuth2 client ID for Reltio API"},
        {"name": "RELTIO_CLIENT_SECRET", "description": "OAuth2 client secret"},
        {"name": "RELTIO_AUTH_URL", "description": "Reltio OAuth2 token endpoint"},
    ],
    "prerequisites": [
        "Start Reltio MCP server: cd /opt/reltio-mcp && source venv/bin/activate && python main.py",
        "Verify MCP server: curl http://localhost:8000/sse returns SSE stream",
        "Ensure Reltio dev tenant credentials are set in environment",
    ],
    "execution_order": "sequential",
    "post_conditions": [
        "Verify all 3 test cases passed",
        "Review proof artifacts in QAForge UI",
        "Archive execution results",
    ],
    "estimated_duration_minutes": 5,
}


def main():
    print("=" * 60)
    print("Populating Reltio MDM E2E Demo with structured data")
    print("=" * 60)

    # Step 1: Login
    print("\n1. Logging in...")
    login()

    # Step 2: Get test case UUIDs
    print("\n2. Fetching test cases...")
    r = S.get(f"{API_URL}/api/projects/{PROJECT_ID}/test-cases")
    r.raise_for_status()
    test_cases = r.json()
    tc_map = {tc["test_case_id"]: tc for tc in test_cases}
    for tc_id, tc in tc_map.items():
        print(f"  {tc_id} -> {tc['id']}")

    # Step 3: Update test cases with structured steps
    print("\n3. Updating test cases with structured steps...")
    steps_map = {
        "TC-RELTIO-001": TC_001_STEPS,
        "TC-RELTIO-002": TC_002_STEPS,
        "TC-RELTIO-003": TC_003_STEPS,
    }
    for tc_id, steps in steps_map.items():
        tc = tc_map.get(tc_id)
        if not tc:
            print(f"  SKIP: {tc_id} not found")
            continue
        result = update_test_case(tc["id"], {
            "test_steps": steps,
            "execution_type": "mcp",
        })
        print(f"  Updated {tc_id}: {len(steps)} step(s), execution_type=mcp")

    # Step 4: Update app profile with connections
    print("\n4. Updating app profile with connections registry...")
    update_app_profile(APP_PROFILE)
    print(f"  Added {len(APP_PROFILE['connections'])} connections: {', '.join(APP_PROFILE['connections'].keys())}")

    # Step 5: Create test plan with execution config
    print("\n5. Creating test plan with execution playbook...")
    plan = create_test_plan({
        "name": "Reltio MCP Smoke Test",
        "description": "End-to-end smoke test for Reltio MCP server integration. Verifies health check, entity search, and data model retrieval via MCP tools.",
        "plan_type": "smoke",
        "execution_config": EXECUTION_CONFIG,
    })
    if plan:
        plan_id = plan["id"]
        print(f"  Created plan: {plan_id}")

        # Step 6: Assign test cases to the plan
        print("\n6. Assigning test cases to plan...")
        for tc_id in ["TC-RELTIO-001", "TC-RELTIO-002", "TC-RELTIO-003"]:
            tc = tc_map.get(tc_id)
            if tc:
                assign_tc_to_plan(tc["id"], plan_id)
                print(f"  Assigned {tc_id}")
    else:
        print("  Skipped plan creation (may already exist)")

    print("\n" + "=" * 60)
    print("Done! Verify in QAForge UI:")
    print(f"  Project: {API_URL.replace('https://', 'https://')}")
    print("  - Test cases -> open any TC -> see Spec Details")
    print("  - App Profile -> scroll to Connections Registry")
    print("  - Test Plan -> Playbook tab")
    print("=" * 60)


if __name__ == "__main__":
    main()
