"""QAForge MCP Tools — Execution Results"""
from src.api_client import agent_delete, agent_post


async def submit_results_impl(results: list) -> list:
    """Submit execution results with optional proof artifacts.

    Each result: {test_case_id, status (passed/failed/skipped/error),
                  actual_result, duration_ms, proof_artifacts?}
    """
    return await agent_post("/executions", json={"executions": results})


async def add_proof_impl(execution_id: str, proof: dict) -> dict:
    """Add proof artifact to an existing execution result.

    proof: {proof_type (api_response/test_output/screenshot/log), title, content}
    """
    return await agent_post(f"/executions/{execution_id}/proof", json=proof)


async def delete_execution_runs_impl(run_ids: list) -> dict:
    """Permanently delete execution runs by their IDs."""
    return await agent_delete("/execution-runs", json={"run_ids": run_ids})
