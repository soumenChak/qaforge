"""
Quinn -- System prompt builder for the QAForge AI assistant.

Assembles a context-rich system prompt from the project's metadata,
requirements, test cases, and execution stats.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from db_models import (
    Project, Requirement, TestCase, TestPlan, ExecutionResult,
    ExecutionRun, KnowledgeEntry,
)

logger = logging.getLogger(__name__)

QUINN_PERSONA = """\
You are **Quinn**, the AI assistant built into QAForge -- FreshGravity's intelligent QA platform.

## Personality
- Warm, confident, and precise. You balance approachability with deep technical expertise.
- You speak like a senior QA engineer who genuinely cares about quality.
- You proactively suggest next steps and surface insights the user might miss.
- You use markdown for readability: tables, bullet lists, code blocks, bold for emphasis.

## Expertise
- Test case design (functional, integration, regression, smoke, e2e, data quality)
- Test planning and execution strategy
- MDM/data platforms (Reltio, Semarchy, Informatica)
- API testing, SQL validation, UI testing
- BRD/PRD analysis and requirement extraction
- Coverage analysis and gap identification

## Rules
- Always be project-aware: reference project name, domain, stats naturally.
- Never fabricate data. If you don't have information, say so and suggest how to get it.
- Keep responses concise unless the user asks for detail.
- When discussing test cases, use their display IDs (e.g., TC-001).
- When the user's request is ambiguous, ask a clarifying question rather than guessing.
"""


def build_quinn_system_prompt(project: Project, db: Session) -> str:
    """Build the full system prompt with project context."""
    sections = [QUINN_PERSONA]

    # -- Project context --
    sections.append(_build_project_context(project, db))

    # -- Available tools (Phase 2) --
    try:
        from core.quinn_tools import get_tool_descriptions
        tool_desc = get_tool_descriptions()
        if tool_desc:
            sections.append(tool_desc)
    except ImportError:
        pass

    return "\n\n".join(sections)


def _build_project_context(project: Project, db: Session) -> str:
    """Gather live stats from the DB and format as context block."""
    try:
        # Counts
        req_count = db.query(sa_func.count(Requirement.id)).filter(
            Requirement.project_id == project.id
        ).scalar() or 0

        tc_count = db.query(sa_func.count(TestCase.id)).filter(
            TestCase.project_id == project.id
        ).scalar() or 0

        plan_count = db.query(sa_func.count(TestPlan.id)).filter(
            TestPlan.project_id == project.id
        ).scalar() or 0

        # Test case status breakdown
        tc_status = dict(
            db.query(TestCase.status, sa_func.count(TestCase.id))
            .filter(TestCase.project_id == project.id)
            .group_by(TestCase.status)
            .all()
        )

        # Execution stats
        exec_total = 0
        exec_passed = 0
        exec_failed = 0
        tc_ids = db.query(TestCase.id).filter(TestCase.project_id == project.id).subquery()
        exec_stats = dict(
            db.query(ExecutionResult.status, sa_func.count(ExecutionResult.id))
            .filter(ExecutionResult.test_case_id.in_(tc_ids))
            .group_by(ExecutionResult.status)
            .all()
        )
        exec_total = sum(exec_stats.values())
        exec_passed = exec_stats.get("passed", 0)
        exec_failed = exec_stats.get("failed", 0)
        pass_rate = round((exec_passed / exec_total) * 100, 1) if exec_total else None

        # Recent execution runs
        recent_runs = (
            db.query(ExecutionRun)
            .filter(ExecutionRun.project_id == project.id)
            .order_by(ExecutionRun.created_at.desc())
            .limit(3)
            .all()
        )

        lines = [
            "## Current Project Context",
            f"- **Project:** {project.name}",
            f"- **Domain:** {project.domain} / {project.sub_domain}",
        ]
        if project.description:
            lines.append(f"- **Description:** {project.description[:200]}")
        lines.extend([
            f"- **Requirements:** {req_count}",
            f"- **Test Cases:** {tc_count}",
            f"- **Test Plans:** {plan_count}",
        ])
        if tc_status:
            status_str = ", ".join(f"{k}: {v}" for k, v in sorted(tc_status.items()))
            lines.append(f"- **TC Status Breakdown:** {status_str}")
        if exec_total:
            lines.append(f"- **Executions:** {exec_total} total, {exec_passed} passed, {exec_failed} failed")
            lines.append(f"- **Pass Rate:** {pass_rate}%")
        if recent_runs:
            run_strs = []
            for r in recent_runs:
                status = r.status
                tc_count_run = len(r.test_case_ids or [])
                run_strs.append(f"{status} ({tc_count_run} TCs)")
            lines.append(f"- **Recent Runs:** {', '.join(run_strs)}")

        if project.app_profile:
            profile = project.app_profile
            if profile.get("base_url"):
                lines.append(f"- **App Base URL:** {profile['base_url']}")
            endpoint_count = len(profile.get("api_endpoints", []))
            if endpoint_count:
                lines.append(f"- **Known API Endpoints:** {endpoint_count}")
            page_count = len(profile.get("ui_pages", []))
            if page_count:
                lines.append(f"- **Known UI Pages:** {page_count}")

        return "\n".join(lines)
    except Exception:
        logger.error("Failed to build project context for Quinn", exc_info=True)
        return f"## Current Project Context\n- **Project:** {project.name}\n- **Domain:** {project.domain} / {project.sub_domain}"
