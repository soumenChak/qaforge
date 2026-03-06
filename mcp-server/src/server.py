"""
QAForge MCP Server — Tool Registration

Exposes QAForge operations as MCP tools that Claude Code can call remotely.
Each tool maps to a QAForge Agent API endpoint.

Supports dynamic project switching via the `connect` tool — users can
switch between projects without restarting the MCP server.
"""
import logging
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.config import QAFORGE_SERVER_NAME
from src.api_client import set_agent_key, get_active_key, is_override_active
from src.tools.project import get_project_info, update_project_info
from src.tools.requirements import list_requirements_impl, extract_requirements_impl, submit_requirements_impl
from src.tools.test_cases import (
    list_test_cases_impl, generate_test_cases_impl, submit_test_cases_impl,
    archive_test_cases_impl, delete_test_cases_impl,
)
from src.tools.test_plans import (
    list_test_plans_impl, create_test_plan_impl, get_plan_test_cases_impl,
    archive_test_plan_impl, delete_test_plan_impl,
)
from src.tools.executions import submit_results_impl, add_proof_impl, delete_execution_runs_impl
from src.tools.knowledge import kb_stats_impl, upload_reference_impl
from src.tools.frameworks import get_frameworks_impl, check_framework_coverage_impl
from src.tools.summary import get_summary_impl

logger = logging.getLogger("qaforge.mcp.server")

# ── Initialize MCP Server ──
# When behind a reverse proxy (e.g. nginx at /qaforge-mcp/), set FASTMCP_MOUNT_PATH
# so SSE advertises the correct message endpoint URL for clients.
_mount = os.getenv("FASTMCP_MOUNT_PATH", "").rstrip("/")
_sse = f"{_mount}/sse" if _mount else "/sse"
_msg = f"{_mount}/messages/" if _mount else "/messages/"
mcp = FastMCP(QAFORGE_SERVER_NAME, host="0.0.0.0", port=8000, sse_path=_sse, message_path=_msg)


# ═══════════════════════════════════════════════════════════════════
# Connection Tools — Switch between QAForge projects dynamically
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def connect(agent_key: str) -> dict:
    """Connect to a QAForge project using its agent API key.

    Use this to switch between projects without restarting the MCP server.
    Each project has its own agent key (generated in Project Settings).
    After connecting, all subsequent tool calls operate on the new project.

    Args:
        agent_key: The project's agent API key (starts with 'qf_')
    """
    if not agent_key or not agent_key.strip():
        return {"status": "error", "message": "Agent key cannot be empty."}

    key = agent_key.strip()
    set_agent_key(key)

    # Validate by fetching project info
    try:
        project = await get_project_info()
        logger.info("Connected to project: %s (domain: %s)", project.get("name"), project.get("domain"))
        return {
            "status": "connected",
            "project": project.get("name"),
            "domain": project.get("domain"),
            "sub_domain": project.get("sub_domain"),
            "key_prefix": key[:10] + "...",
            "message": f"Successfully connected to '{project.get('name')}'. All tools now operate on this project.",
        }
    except Exception as e:
        # Revert on failure — clear the bad key
        set_agent_key(None)
        logger.warning("Connection failed: %s", e)
        return {
            "status": "error",
            "message": f"Invalid agent key — could not connect to any project. Error: {str(e)}",
        }


@mcp.tool()
async def connection_status() -> dict:
    """Check current connection status — which project is connected and how.

    Shows whether using a session override key (set via `connect`) or the
    default server-configured key, along with the connected project info.
    """
    key = get_active_key()
    if not key:
        return {
            "status": "not_connected",
            "message": "No agent key configured. Use `connect(agent_key)` to connect to a project.",
        }

    try:
        project = await get_project_info()
        return {
            "status": "connected",
            "project": project.get("name"),
            "domain": project.get("domain"),
            "sub_domain": project.get("sub_domain"),
            "key_source": "session_override" if is_override_active() else "server_default",
            "key_prefix": key[:10] + "...",
        }
    except Exception as e:
        return {
            "status": "error",
            "key_source": "session_override" if is_override_active() else "server_default",
            "key_prefix": key[:10] + "..." if key else "none",
            "message": f"Key is set but connection failed: {str(e)}",
        }


# ═══════════════════════════════════════════════════════════════════
# Project Tools
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_project() -> dict:
    """Get project metadata including name, domain, sub-domain, app profile (URLs, tech stack, auth config), and description.

    Use this to understand the project context before performing other operations.
    """
    return await get_project_info()


@mcp.tool()
async def update_project(
    description: str = "",
    brd_prd_text: str = "",
) -> dict:
    """Update project description or BRD/PRD context text.

    Args:
        description: New project description
        brd_prd_text: BRD/PRD document text for requirement extraction context
    """
    return await update_project_info(
        description=description or None,
        brd_prd_text=brd_prd_text or None,
    )


# ═══════════════════════════════════════════════════════════════════
# Requirements Tools
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_requirements() -> list:
    """List all requirements in the project.

    Returns requirements with: id, req_id, title, description, priority (high/medium/low),
    category, source, status, created_at.
    """
    return await list_requirements_impl()


@mcp.tool()
async def extract_requirements(text: str, source: str = "brd") -> list:
    """Extract structured requirements from BRD/PRD document text using AI.

    The AI analyzes the text and creates individual requirements with titles,
    descriptions, priorities, and categories.

    Args:
        text: The BRD/PRD document text to extract requirements from
        source: Source type - 'brd' or 'prd'
    """
    return await extract_requirements_impl(text=text, source=source)


@mcp.tool()
async def submit_requirements(requirements: list) -> list:
    """Submit manually created requirements to the project.

    Args:
        requirements: List of requirement objects, each with:
            - req_id: Unique ID like 'REQ-001'
            - title: Short requirement title
            - description: Detailed requirement text
            - priority: 'high', 'medium', or 'low'
            - category: e.g. 'functional', 'security', 'performance'
    """
    return await submit_requirements_impl(requirements=requirements)


# ═══════════════════════════════════════════════════════════════════
# Test Case Tools
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_test_cases(status: str = "", test_plan_id: str = "") -> list:
    """List test cases in the project, optionally filtered.

    Returns test cases with: id, test_case_id, title, description, category,
    priority, execution_type, status, test_steps, expected_result, tags.

    Args:
        status: Filter by status - 'draft', 'approved', 'active', or '' for all
        test_plan_id: Filter to test cases in a specific test plan (UUID)
    """
    return await list_test_cases_impl(status=status, test_plan_id=test_plan_id)


@mcp.tool()
async def generate_test_cases(
    count: int = 10,
    description: str = "",
    domain: str = "",
    sub_domain: str = "",
) -> list:
    """Generate test cases using AI from frameworks, requirements, and Knowledge Base.

    Automatically fetches: (1) testing frameworks for the domain as mandatory test areas,
    (2) project requirements as BRD context, (3) reference test cases from the KB.
    The AI generates test cases that satisfy both the framework standards and the
    project requirements.

    Args:
        count: Number of test cases to generate (1-50, default 10)
        description: Additional focus area or context (appended to auto-fetched requirements)
        domain: Domain filter for framework + KB retrieval (mdm, ai, data_eng, integration, digital)
        sub_domain: Sub-domain filter (reltio, snowflake, databricks, etc.)
    """
    return await generate_test_cases_impl(
        count=count, description=description,
        domain=domain, sub_domain=sub_domain,
    )


@mcp.tool()
async def submit_test_cases(test_cases: list) -> list:
    """Submit manually created test cases to the project.

    Args:
        test_cases: List of test case objects, each with:
            - test_case_id: Unique ID like 'TC-001'
            - title: Test case title
            - description: What this test validates
            - category: 'functional', 'integration', 'smoke', 'e2e', 'regression', etc.
            - priority: 'P1' (critical), 'P2' (high), 'P3' (medium), 'P4' (low)
            - execution_type: 'api', 'ui', 'sql', 'mcp', 'manual'
            - expected_result: What should happen when the test passes
            - preconditions: Setup required before running
            - test_steps: List of step objects with action/expected_result
            - tags: List of keyword tags
    """
    return await submit_test_cases_impl(test_cases=test_cases)


# ═══════════════════════════════════════════════════════════════════
# Test Plan Tools
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_test_plans() -> list:
    """List all test plans with execution statistics.

    Returns plans with: id, name, description, plan_type, status,
    test_case_count, executed_count, passed_count, failed_count.
    """
    return await list_test_plans_impl()


@mcp.tool()
async def create_test_plan(
    name: str,
    description: str = "",
    plan_type: str = "smoke",
    test_case_ids: list = [],
) -> dict:
    """Create a new test plan to organize test cases for execution.

    Args:
        name: Plan name (e.g. 'Sprint 5 Smoke Test')
        description: What this plan covers
        plan_type: 'smoke', 'regression', 'e2e', 'integration', or 'functional'
        test_case_ids: List of test case UUIDs to include in the plan
    """
    return await create_test_plan_impl(
        name=name, description=description,
        plan_type=plan_type, test_case_ids=test_case_ids or None,
    )


@mcp.tool()
async def get_plan_test_cases(plan_id: str) -> list:
    """Get all test cases assigned to a specific test plan.

    Args:
        plan_id: UUID of the test plan
    """
    return await get_plan_test_cases_impl(plan_id=plan_id)


# ═══════════════════════════════════════════════════════════════════
# Execution Tools
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def submit_results(results: list) -> list:
    """Submit test execution results with optional proof artifacts.

    Args:
        results: List of execution result objects, each with:
            - test_case_id: UUID of the test case
            - status: 'passed', 'failed', 'skipped', or 'error'
            - actual_result: What actually happened
            - duration_ms: Execution duration in milliseconds
            - proof_artifacts: Optional list of proof objects:
                - proof_type: 'api_response', 'test_output', 'screenshot', 'log'
                - title: Proof title
                - content: Proof content (JSON for api_response, string for others)
    """
    return await submit_results_impl(results=results)


@mcp.tool()
async def add_proof(execution_id: str, proof_type: str, title: str, content: str) -> dict:
    """Add a proof artifact to an existing execution result.

    Args:
        execution_id: UUID of the execution result
        proof_type: Type of proof - 'api_response', 'test_output', 'screenshot', 'log', 'query_result'
        title: Short title describing the proof
        content: The proof content (JSON string for structured data, plain text for logs)
    """
    return await add_proof_impl(
        execution_id=execution_id,
        proof={"proof_type": proof_type, "title": title, "content": content},
    )


# ═══════════════════════════════════════════════════════════════════
# Knowledge Base Tools
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def kb_stats(domain: str = "") -> dict:
    """Get Knowledge Base statistics — total entries, breakdown by domain/sub-domain.

    Args:
        domain: Optional domain filter (mdm, ai, data_eng, integration, digital)
    """
    return await kb_stats_impl(domain=domain)


@mcp.tool()
async def upload_reference(entries: list, domain: str, sub_domain: str) -> dict:
    """Upload reference test cases to the Knowledge Base for future AI generation.

    Reference entries improve the quality of AI-generated test cases by providing
    domain-specific patterns and examples.

    Args:
        entries: List of reference entries, each with: {title, content, tags?}
        domain: Domain classification (mdm, ai, data_eng, integration, digital)
        sub_domain: Sub-domain (reltio, snowflake, databricks, etc.)
    """
    return await upload_reference_impl(entries=entries, domain=domain, sub_domain=sub_domain)


# ═══════════════════════════════════════════════════════════════════
# Framework Tools
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_frameworks(domain: str = "") -> list:
    """Get testing frameworks — domain-specific testing standards, patterns, and quality gates.

    Frameworks define MANDATORY test areas for a domain. Use these to guide test case
    generation and ensure comprehensive coverage. When building or testing an app,
    fetch the relevant framework first, then generate test cases that satisfy it.

    Args:
        domain: Filter by domain (mdm, ai, data_eng, integration, digital). Empty = all.
    """
    return await get_frameworks_impl(domain=domain)


@mcp.tool()
async def check_framework_coverage(domain: str = "") -> dict:
    """Check how well existing test cases cover the testing framework standards.

    Compares test cases against framework sections and returns a gap analysis
    showing which framework areas are covered vs missing. Use this to identify
    what additional tests need to be written for full framework compliance.

    Args:
        domain: Domain to check coverage for (mdm, ai, data_eng, etc.). Empty = all.

    Returns:
        Coverage report with per-section analysis, coverage percentages,
        and list of missing items that need test cases.
    """
    return await check_framework_coverage_impl(domain=domain)


# ═══════════════════════════════════════════════════════════════════
# Summary Tools
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_summary() -> dict:
    """Get project quality summary — test case counts, pass rates, execution stats, coverage.

    Returns: total_test_cases, by_status, by_priority, total_executions,
    pass_rate, recent_executions, coverage_percent.
    """
    return await get_summary_impl()


# ═══════════════════════════════════════════════════════════════════
# Archive / Delete Tools
# ═══════════════════════════════════════════════════════════════════

@mcp.tool()
async def archive_test_cases(test_case_ids: list) -> dict:
    """Archive test cases by setting their status to 'archived'. Reversible.

    Use this to soft-delete test cases without losing execution history.
    Archived test cases won't appear in default listings.

    Args:
        test_case_ids: List of test case UUIDs to archive
    """
    return await archive_test_cases_impl(test_case_ids)


@mcp.tool()
async def delete_test_cases(test_case_ids: list) -> dict:
    """Permanently delete test cases and all their execution results. NOT reversible.

    Use archive_test_cases for reversible soft-delete instead.
    Cascades: execution results and feedback for these test cases are also deleted.

    Args:
        test_case_ids: List of test case UUIDs to permanently delete
    """
    return await delete_test_cases_impl(test_case_ids)


@mcp.tool()
async def archive_test_plan(plan_id: str) -> dict:
    """Archive a test plan by setting its status to 'archived'. Reversible.

    Test cases in the plan are NOT affected — only the plan itself is archived.

    Args:
        plan_id: UUID of the test plan to archive
    """
    return await archive_test_plan_impl(plan_id)


@mcp.tool()
async def delete_test_plan(plan_id: str) -> dict:
    """Permanently delete a test plan. NOT reversible.

    Test cases are unlinked (test_plan_id set to NULL), NOT deleted.
    Use delete_test_cases separately if you also want to remove the test cases.

    Args:
        plan_id: UUID of the test plan to permanently delete
    """
    return await delete_test_plan_impl(plan_id)


@mcp.tool()
async def delete_execution_runs(run_ids: list) -> dict:
    """Permanently delete execution runs. NOT reversible.

    Use this to clean up bad or orphaned execution runs (e.g., failed runs
    with incorrect results that skew pass rates).

    Args:
        run_ids: List of execution run UUIDs to delete
    """
    return await delete_execution_runs_impl(run_ids)
