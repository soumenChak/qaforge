"""QAForge MCP Tools — Test Case Management"""
import logging

from src.api_client import agent_get, agent_post

logger = logging.getLogger("qaforge.mcp.tools.test_cases")


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
    """Generate test cases from requirements using AI + Knowledge Base.

    Automatically fetches project requirements to use as BRD context
    when no explicit description is provided.
    """
    # Build brd_text from requirements + description
    brd_parts = []

    # Auto-fetch requirements to use as BRD context
    try:
        reqs = await agent_get("/requirements")
        if reqs:
            req_lines = []
            for r in reqs:
                line = f"- [{r.get('priority', 'medium').upper()}] {r.get('req_id', '')}: {r.get('title', '')}"
                if r.get("description"):
                    line += f"\n  {r['description']}"
                req_lines.append(line)
            brd_parts.append("PROJECT REQUIREMENTS:\n" + "\n".join(req_lines))
            logger.info("Auto-fetched %d requirements as BRD context", len(reqs))
    except Exception as exc:
        logger.warning("Could not fetch requirements for BRD context: %s", exc)

    if description:
        brd_parts.append(description)

    brd_text = "\n\n".join(brd_parts) if brd_parts else "Generate general test cases for the project"

    payload = {"brd_text": brd_text, "count": count}
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
