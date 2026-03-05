"""QAForge MCP Tools — Test Plan Management"""
from src.api_client import agent_delete, agent_get, agent_post, agent_put


async def list_test_plans_impl() -> list:
    """List all test plans with execution stats."""
    return await agent_get("/test-plans")


async def create_test_plan_impl(
    name: str,
    description: str = "",
    plan_type: str = "smoke",
    test_case_ids: list | None = None,
) -> dict:
    """Create a new test plan."""
    payload = {"name": name, "plan_type": plan_type}
    if description:
        payload["description"] = description
    if test_case_ids:
        payload["test_case_ids"] = test_case_ids
    return await agent_post("/test-plans", json=payload)


async def get_plan_test_cases_impl(plan_id: str) -> list:
    """Get test cases assigned to a specific test plan."""
    return await agent_get(f"/test-plans/{plan_id}/test-cases")


async def archive_test_plan_impl(plan_id: str) -> dict:
    """Archive a test plan by setting status to 'archived'. Reversible."""
    return await agent_put(f"/test-plans/{plan_id}/archive")


async def delete_test_plan_impl(plan_id: str) -> dict:
    """Permanently delete a test plan. Test cases are unlinked, not deleted."""
    return await agent_delete(f"/test-plans/{plan_id}")
