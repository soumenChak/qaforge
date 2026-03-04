"""QAForge MCP Tools — Test Case Management"""
from src.api_client import agent_get, agent_post


async def list_test_cases_impl(status: str = "", test_plan_id: str = "") -> list:
    """List test cases with optional filters."""
    params = {}
    if status:
        params["status"] = status
    if test_plan_id:
        params["test_plan_id"] = test_plan_id
    return await agent_get("/test-cases", params=params or None)


async def generate_test_cases_impl(
    count: int = 10,
    description: str = "",
    domain: str = "",
    sub_domain: str = "",
) -> list:
    """Generate test cases from requirements using AI + Knowledge Base."""
    payload = {"count": count}
    if description:
        payload["description"] = description
    if domain:
        payload["domain"] = domain
    if sub_domain:
        payload["sub_domain"] = sub_domain
    return await agent_post("/generate-from-brd", json=payload)


async def submit_test_cases_impl(test_cases: list) -> list:
    """Submit test cases to the project.

    Each test case: {test_case_id, title, description, category, priority,
                     execution_type, expected_result, preconditions, test_steps, tags}
    """
    return await agent_post("/test-cases", json={"test_cases": test_cases})
