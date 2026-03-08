"""
Quinn -- Tool definitions and executors for the QAForge AI assistant.

Each tool maps to existing business logic via direct DB queries.
Tools are used by the LLM orchestrator loop in routes/chat.py.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from db_models import (
    ExecutionResult,
    ExecutionRun,
    KnowledgeEntry,
    Project,
    Requirement,
    TestCase,
    TestPlan,
    User,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    executor: Callable


# ---------------------------------------------------------------------------
# Tool Executors
# ---------------------------------------------------------------------------
def _get_project_summary(
    project_id: uuid.UUID, db: Session, user: User, **kwargs
) -> dict:
    """Get an overview of the project with key stats."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": "Project not found"}

    req_count = db.query(sa_func.count(Requirement.id)).filter(
        Requirement.project_id == project_id
    ).scalar() or 0

    tc_count = db.query(sa_func.count(TestCase.id)).filter(
        TestCase.project_id == project_id
    ).scalar() or 0

    plan_count = db.query(sa_func.count(TestPlan.id)).filter(
        TestPlan.project_id == project_id
    ).scalar() or 0

    tc_by_status = dict(
        db.query(TestCase.status, sa_func.count(TestCase.id))
        .filter(TestCase.project_id == project_id)
        .group_by(TestCase.status)
        .all()
    )

    tc_ids_sub = db.query(TestCase.id).filter(TestCase.project_id == project_id).subquery()
    exec_stats = dict(
        db.query(ExecutionResult.status, sa_func.count(ExecutionResult.id))
        .filter(ExecutionResult.test_case_id.in_(tc_ids_sub))
        .group_by(ExecutionResult.status)
        .all()
    )
    exec_total = sum(exec_stats.values())
    passed = exec_stats.get("passed", 0)
    failed = exec_stats.get("failed", 0)

    return {
        "project_name": project.name,
        "domain": project.domain,
        "sub_domain": project.sub_domain,
        "requirements": req_count,
        "test_cases": tc_count,
        "test_plans": plan_count,
        "tc_by_status": tc_by_status,
        "executions_total": exec_total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round((passed / exec_total) * 100, 1) if exec_total else None,
    }


def _list_test_cases(
    project_id: uuid.UUID, db: Session, user: User, **kwargs
) -> dict:
    """List test cases with optional filters."""
    query = db.query(TestCase).filter(TestCase.project_id == project_id)

    if kwargs.get("status"):
        query = query.filter(TestCase.status == kwargs["status"])
    if kwargs.get("priority"):
        query = query.filter(TestCase.priority == kwargs["priority"])
    if kwargs.get("category"):
        query = query.filter(TestCase.category == kwargs["category"])

    limit = min(kwargs.get("limit", 20), 50)
    offset = kwargs.get("offset", 0)

    total = query.count()
    cases = query.order_by(TestCase.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "showing": len(cases),
        "test_cases": [
            {
                "test_case_id": tc.test_case_id,
                "title": tc.title,
                "status": tc.status,
                "priority": tc.priority,
                "category": tc.category,
                "execution_type": tc.execution_type,
            }
            for tc in cases
        ],
    }


def _get_test_case(
    project_id: uuid.UUID, db: Session, user: User, **kwargs
) -> dict:
    """Get full details of a test case by display ID."""
    display_id = kwargs.get("test_case_id", "")
    tc = (
        db.query(TestCase)
        .filter(
            TestCase.project_id == project_id,
            TestCase.test_case_id == display_id,
        )
        .first()
    )
    if not tc:
        return {"error": f"Test case '{display_id}' not found"}

    return {
        "test_case_id": tc.test_case_id,
        "title": tc.title,
        "description": tc.description,
        "preconditions": tc.preconditions,
        "test_steps": tc.test_steps,
        "expected_result": tc.expected_result,
        "status": tc.status,
        "priority": tc.priority,
        "category": tc.category,
        "execution_type": tc.execution_type,
        "source": tc.source,
        "rating": tc.rating,
    }


def _list_test_plans(
    project_id: uuid.UUID, db: Session, user: User, **kwargs
) -> dict:
    """List test plans in the project."""
    plans = (
        db.query(TestPlan)
        .filter(TestPlan.project_id == project_id)
        .order_by(TestPlan.created_at.desc())
        .all()
    )

    result = []
    for p in plans:
        tc_count = db.query(sa_func.count(TestCase.id)).filter(
            TestCase.test_plan_id == p.id
        ).scalar() or 0
        result.append({
            "name": p.name,
            "plan_type": p.plan_type,
            "status": p.status,
            "test_case_count": tc_count,
        })

    return {"total": len(result), "test_plans": result}


def _get_test_plan_summary(
    project_id: uuid.UUID, db: Session, user: User, **kwargs
) -> dict:
    """Get summary stats for a specific test plan."""
    plan_name = kwargs.get("plan_name", "")
    plan = (
        db.query(TestPlan)
        .filter(TestPlan.project_id == project_id, TestPlan.name.ilike(f"%{plan_name}%"))
        .first()
    )
    if not plan:
        return {"error": f"Test plan matching '{plan_name}' not found"}

    tc_count = db.query(sa_func.count(TestCase.id)).filter(
        TestCase.test_plan_id == plan.id
    ).scalar() or 0

    exec_stats = dict(
        db.query(ExecutionResult.status, sa_func.count(ExecutionResult.id))
        .filter(ExecutionResult.test_plan_id == plan.id)
        .group_by(ExecutionResult.status)
        .all()
    )
    total_exec = sum(exec_stats.values())
    passed = exec_stats.get("passed", 0)

    return {
        "name": plan.name,
        "plan_type": plan.plan_type,
        "status": plan.status,
        "test_case_count": tc_count,
        "executions_total": total_exec,
        "passed": passed,
        "failed": exec_stats.get("failed", 0),
        "pass_rate": round((passed / total_exec) * 100, 1) if total_exec else None,
    }


def _list_requirements(
    project_id: uuid.UUID, db: Session, user: User, **kwargs
) -> dict:
    """List requirements in the project."""
    query = db.query(Requirement).filter(Requirement.project_id == project_id)

    if kwargs.get("priority"):
        query = query.filter(Requirement.priority == kwargs["priority"])
    if kwargs.get("status"):
        query = query.filter(Requirement.status == kwargs["status"])

    limit = min(kwargs.get("limit", 20), 50)
    reqs = query.order_by(Requirement.created_at.desc()).limit(limit).all()

    return {
        "total": query.count(),
        "requirements": [
            {
                "req_id": r.req_id,
                "title": r.title,
                "priority": r.priority,
                "status": r.status,
                "category": r.category,
            }
            for r in reqs
        ],
    }


def _get_kb_stats(
    project_id: uuid.UUID, db: Session, user: User, **kwargs
) -> dict:
    """Get knowledge base statistics."""
    project = db.query(Project).filter(Project.id == project_id).first()
    domain = project.domain if project else None

    query = db.query(KnowledgeEntry)
    if domain:
        query = query.filter(KnowledgeEntry.domain == domain)

    total = query.count()
    by_type = dict(
        query.with_entities(
            KnowledgeEntry.entry_type,
            sa_func.count(KnowledgeEntry.id),
        )
        .group_by(KnowledgeEntry.entry_type)
        .all()
    )

    return {
        "domain": domain,
        "total_entries": total,
        "by_type": by_type,
    }


def _search_knowledge_base(
    project_id: uuid.UUID, db: Session, user: User, **kwargs
) -> dict:
    """Search the knowledge base by keyword."""
    query_text = kwargs.get("query", "")
    if not query_text:
        return {"error": "Query is required"}

    project = db.query(Project).filter(Project.id == project_id).first()
    domain = project.domain if project else None

    q = db.query(KnowledgeEntry)
    if domain:
        q = q.filter(KnowledgeEntry.domain == domain)

    # Simple keyword search
    search_filter = KnowledgeEntry.title.ilike(f"%{query_text}%") | KnowledgeEntry.content.ilike(f"%{query_text}%")
    entries = q.filter(search_filter).limit(10).all()

    return {
        "query": query_text,
        "results": [
            {
                "title": e.title,
                "entry_type": e.entry_type,
                "content": e.content[:300],
                "tags": e.tags,
            }
            for e in entries
        ],
    }


def _get_execution_results(
    project_id: uuid.UUID, db: Session, user: User, **kwargs
) -> dict:
    """Get recent execution results."""
    limit = min(kwargs.get("limit", 10), 30)

    tc_ids_sub = db.query(TestCase.id).filter(
        TestCase.project_id == project_id
    ).subquery()

    results = (
        db.query(ExecutionResult)
        .filter(ExecutionResult.test_case_id.in_(tc_ids_sub))
        .order_by(ExecutionResult.executed_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "total": len(results),
        "results": [
            {
                "test_case_id": str(r.test_case_id),
                "status": r.status,
                "actual_result": (r.actual_result or "")[:200],
                "duration_ms": r.duration_ms,
                "executed_by": r.executed_by,
                "executed_at": r.executed_at.isoformat() if r.executed_at else None,
            }
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------
QUINN_TOOLS: List[ToolDefinition] = [
    ToolDefinition(
        name="get_project_summary",
        description="Get an overview of the current project including test case counts, execution stats, and pass rate.",
        input_schema={"type": "object", "properties": {}, "required": []},
        executor=_get_project_summary,
    ),
    ToolDefinition(
        name="list_test_cases",
        description="List test cases in the project. Can filter by status, priority, or category.",
        input_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: draft, reviewed, approved, executed, passed, failed"},
                "priority": {"type": "string", "description": "Filter by priority: P1, P2, P3, P4"},
                "category": {"type": "string", "description": "Filter by category: functional, integration, regression, smoke, e2e"},
                "limit": {"type": "integer", "description": "Max results (default 20, max 50)"},
                "offset": {"type": "integer", "description": "Pagination offset"},
            },
            "required": [],
        },
        executor=_list_test_cases,
    ),
    ToolDefinition(
        name="get_test_case",
        description="Get full details of a specific test case by its display ID (e.g., TC-001).",
        input_schema={
            "type": "object",
            "properties": {
                "test_case_id": {"type": "string", "description": "The display ID like TC-001"},
            },
            "required": ["test_case_id"],
        },
        executor=_get_test_case,
    ),
    ToolDefinition(
        name="list_test_plans",
        description="List all test plans in the project with their status and test case counts.",
        input_schema={"type": "object", "properties": {}, "required": []},
        executor=_list_test_plans,
    ),
    ToolDefinition(
        name="get_test_plan_summary",
        description="Get detailed stats for a specific test plan including execution results.",
        input_schema={
            "type": "object",
            "properties": {
                "plan_name": {"type": "string", "description": "Name or partial name of the test plan"},
            },
            "required": ["plan_name"],
        },
        executor=_get_test_plan_summary,
    ),
    ToolDefinition(
        name="list_requirements",
        description="List requirements in the project. Can filter by priority or status.",
        input_schema={
            "type": "object",
            "properties": {
                "priority": {"type": "string", "description": "Filter by priority: high, medium, low"},
                "status": {"type": "string", "description": "Filter by status: active, tested, deferred"},
                "limit": {"type": "integer", "description": "Max results (default 20)"},
            },
            "required": [],
        },
        executor=_list_requirements,
    ),
    ToolDefinition(
        name="get_kb_stats",
        description="Get knowledge base statistics for the project's domain.",
        input_schema={"type": "object", "properties": {}, "required": []},
        executor=_get_kb_stats,
    ),
    ToolDefinition(
        name="search_knowledge_base",
        description="Search the knowledge base by keyword to find patterns, best practices, and test guidance.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase"},
            },
            "required": ["query"],
        },
        executor=_search_knowledge_base,
    ),
    ToolDefinition(
        name="get_execution_results",
        description="Get recent test execution results showing pass/fail status and details.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of results (default 10, max 30)"},
            },
            "required": [],
        },
        executor=_get_execution_results,
    ),
]

# Name-to-tool lookup
_TOOL_MAP: Dict[str, ToolDefinition] = {t.name: t for t in QUINN_TOOLS}


def execute_tool(
    tool_name: str,
    project_id: uuid.UUID,
    db: Session,
    user: User,
    **kwargs,
) -> Any:
    """Execute a named tool and return its result."""
    tool = _TOOL_MAP.get(tool_name)
    if not tool:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        return tool.executor(project_id, db, user, **kwargs)
    except Exception as e:
        logger.error("Tool execution error (%s): %s", tool_name, e, exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}


def get_tool_descriptions() -> str:
    """Format tool descriptions for the system prompt."""
    if not QUINN_TOOLS:
        return ""

    lines = ["## Available Tools", "You can use the following tools to look up project data:\n"]
    for tool in QUINN_TOOLS:
        params = tool.input_schema.get("properties", {})
        param_strs = []
        for pname, pdef in params.items():
            req = "(required)" if pname in tool.input_schema.get("required", []) else "(optional)"
            param_strs.append(f"  - `{pname}` {req}: {pdef.get('description', '')}")

        lines.append(f"### `{tool.name}`")
        lines.append(f"{tool.description}")
        if param_strs:
            lines.append("**Parameters:**")
            lines.extend(param_strs)
        lines.append("")

    return "\n".join(lines)
