"""
QAForge -- Agent API routes.

Endpoints for AI agents (Claude Code, Codex, Gemini CLI) to submit
test cases, execution results, and proof artifacts.

Auth: X-Agent-Key header (project-scoped API key, no JWT needed).
"""

import hashlib
import json as _json
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from db_models import (
    AgentSession,
    ExecutionResult,
    KnowledgeEntry,
    ProofArtifact,
    TestCase,
    TestPlan,
    Project,
    User,
)
from db_session import get_db
from dependencies import get_agent_project
from models import (
    AgentExecutionBatchSubmit,
    AgentSessionCreate,
    AgentSessionResponse,
    AgentSummaryResponse,
    AgentTestCaseBatchSubmit,
    ExecutionResultResponse,
    ProofArtifactResponse,
    ProofArtifactSubmit,
    TestCaseResponse,
    TestPlanCreate,
    TestPlanResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Bootstrap Token — Admin sets QAFORGE_BOOTSTRAP_TOKEN env var.
# Agents use it ONCE to create a project + get an agent API key.
# This is a gatekeeper: limited scope, no admin access, project-create only.
# ---------------------------------------------------------------------------
_BOOTSTRAP_TOKEN = os.environ.get("QAFORGE_BOOTSTRAP_TOKEN", "")


def _verify_bootstrap_token(x_bootstrap_token: str = Header(...)):
    """Verify the bootstrap token for agent onboarding."""
    if not _BOOTSTRAP_TOKEN:
        raise HTTPException(
            403,
            "Bootstrap onboarding is not enabled. "
            "Admin must set QAFORGE_BOOTSTRAP_TOKEN env var.",
        )
    if x_bootstrap_token != _BOOTSTRAP_TOKEN:
        raise HTTPException(401, "Invalid bootstrap token")
    return True


@router.post("/bootstrap")
def bootstrap_agent(
    body: dict,
    db: Session = Depends(get_db),
    _: bool = Depends(_verify_bootstrap_token),
):
    """
    Agent onboarding — create project + generate API key in one step.

    Gatekeeper: requires X-Bootstrap-Token header (admin-controlled).
    Scope: can ONLY create projects and generate keys.
    Cannot: delete, modify, access admin features, or read other projects.

    Body:
      - project_name: str (required)
      - domain: str (default "mdm") — mdm | ai | data_eng | integration | digital
      - sub_domain: str (default "general")
      - description: str (optional)

    Returns: { project_id, project_name, agent_api_key }
    """
    project_name = body.get("project_name", "").strip()
    if not project_name:
        raise HTTPException(400, "project_name is required")

    domain = body.get("domain", "mdm")
    sub_domain = body.get("sub_domain", "general")
    description = body.get("description", "")

    # Validate domain
    valid_domains = {"mdm", "ai", "data_eng", "integration", "digital"}
    if domain not in valid_domains:
        raise HTTPException(400, f"Invalid domain. Must be one of: {valid_domains}")

    # Get admin user (first admin in DB — bootstrap operations attributed to admin)
    admin = db.query(User).filter(User.roles.contains(["admin"])).first()
    if not admin:
        raise HTTPException(500, "No admin user found in system")

    # Check if project already exists (return existing key if so)
    existing = db.query(Project).filter(Project.name == project_name).first()
    if existing:
        # Project exists — generate new key for it
        raw_key = f"qf_{secrets.token_urlsafe(48)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        existing.agent_api_key_hash = key_hash
        db.commit()
        logger.info(
            "Bootstrap: regenerated key for existing project '%s'", project_name
        )
        return {
            "project_id": str(existing.id),
            "project_name": existing.name,
            "agent_api_key": raw_key,
            "created": False,
            "message": f"Project '{project_name}' already exists. New agent key generated.",
        }

    # Create new project
    project = Project(
        name=project_name,
        domain=domain,
        sub_domain=sub_domain,
        description=description or f"Created via agent bootstrap",
        created_by=admin.id,
    )
    db.add(project)
    db.flush()

    # Generate agent API key
    raw_key = f"qf_{secrets.token_urlsafe(48)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    project.agent_api_key_hash = key_hash
    db.commit()

    logger.info(
        "Bootstrap: created project '%s' (%s/%s) with agent key",
        project_name, domain, sub_domain,
    )

    return {
        "project_id": str(project.id),
        "project_name": project.name,
        "agent_api_key": raw_key,
        "created": True,
        "message": f"Project '{project_name}' created with agent API key.",
    }


# ---------------------------------------------------------------------------
# Project metadata (agent can populate app profile, description, BRD/PRD)
# ---------------------------------------------------------------------------
@router.put("/project", response_model=dict)
def update_project_metadata(
    body: dict,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """
    Update the authenticated project's metadata.
    Agents can set: app_profile, description, brd_prd_text.
    """
    allowed_fields = {"app_profile", "description", "brd_prd_text"}
    updated = []

    for field in allowed_fields:
        if field in body:
            setattr(project, field, body[field])
            updated.append(field)

    if updated:
        project.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Agent updated project %s fields: %s", project.name, updated)

    return {
        "project_id": str(project.id),
        "project_name": project.name,
        "updated_fields": updated,
    }


# ---------------------------------------------------------------------------
# BRD-aware KB retrieval helper
# ---------------------------------------------------------------------------
# Stop-words excluded from keyword extraction (common words that add noise)
_STOP_WORDS = frozenset(
    "the a an and or is in on to of for by at as it this that with from be "
    "are was were has have had will can should not all any each no yes "
    "test case step verify check ensure result expected actual data "
    "table column row record field value status name type description "
    "select from where insert update delete count distinct group order limit "
    "into values set null true false between like join left right inner "
    "pre requisite prerequisites preconditions given when then should "
    "1 2 3 4 5 6 7 8 9 0 none n/a na".split()
)


def _extract_brd_keywords(brd_text: str, max_keywords: int = 30) -> List[str]:
    """
    Extract meaningful keywords from BRD text for KB matching.

    Prioritises domain-specific terms: entity names, table names,
    system names, technical terms — things that distinguish one
    BRD from another.
    """
    import re

    text = brd_text.lower()

    # Extract ALL_CAPS or CamelCase terms (table names, entity names)
    tech_terms = set()
    # UPPER_SNAKE_CASE (e.g. TITLE_NETWORK_LANDING, MDM_NETWORK_C)
    for m in re.finditer(r"\b[A-Z][A-Z0-9_]{3,}\b", brd_text):
        tech_terms.add(m.group().lower())
    # CamelCase terms (e.g. NetworkEntity, ReltioUI)
    for m in re.finditer(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", brd_text):
        tech_terms.add(m.group().lower())

    # Extract regular words (3+ chars, not stop words)
    words = re.findall(r"\b[a-z][a-z0-9_]{2,}\b", text)
    word_freq: dict = {}
    for w in words:
        if w not in _STOP_WORDS and len(w) >= 3:
            word_freq[w] = word_freq.get(w, 0) + 1

    # Prioritise: tech terms first, then by frequency
    # Tech terms get a frequency boost
    for t in tech_terms:
        word_freq[t] = word_freq.get(t, 0) + 5

    # Sort by frequency descending, take top N
    sorted_kw = sorted(word_freq.items(), key=lambda x: -x[1])
    return [kw for kw, _ in sorted_kw[:max_keywords]]


def _retrieve_kb_for_brd(
    db: "Session",
    brd_text: str,
    domain: str,
    sub_domain: str,
    limit: int = 10,
) -> list:
    """
    Retrieve KB entries relevant to a specific BRD document.

    Strategy:
      1. Extract keywords from the BRD text
      2. Fetch all domain-relevant KB test_case entries
      3. Score each entry by how many BRD keywords appear in its content
      4. Return top entries sorted by relevance score + usage_count
    """
    keywords = _extract_brd_keywords(brd_text)
    if not keywords:
        # Fallback: just return domain-matched entries
        return (
            db.query(KnowledgeEntry)
            .filter(
                KnowledgeEntry.entry_type == "test_case",
                or_(
                    KnowledgeEntry.domain == domain,
                    KnowledgeEntry.domain == "general",
                ),
            )
            .order_by(
                KnowledgeEntry.usage_count.desc(),
                KnowledgeEntry.created_at.desc(),
            )
            .limit(limit)
            .all()
        )

    # Fetch all candidate KB entries for this domain (broader pool)
    candidates = (
        db.query(KnowledgeEntry)
        .filter(
            KnowledgeEntry.entry_type == "test_case",
            or_(
                KnowledgeEntry.domain == domain,
                KnowledgeEntry.domain == "general",
            ),
        )
        .order_by(KnowledgeEntry.created_at.desc())
        .limit(100)  # Broad pool to score from
        .all()
    )

    if not candidates:
        return []

    # Score each entry by keyword overlap with BRD
    scored = []
    for entry in candidates:
        content_lower = entry.content.lower()
        title_lower = entry.title.lower()
        # Keyword hits (content match = 1 point, title match = 3 points)
        score = 0
        for kw in keywords:
            if kw in title_lower:
                score += 3
            elif kw in content_lower:
                score += 1
        # Bonus for sub_domain match
        if sub_domain and entry.sub_domain == sub_domain:
            score += 5
        # Small boost for usage (popular entries are likely good)
        score += min(entry.usage_count, 5) * 0.5
        scored.append((score, entry))

    # Sort by score descending, return top N
    scored.sort(key=lambda x: -x[0])

    # Only return entries with score > 0 (at least some relevance)
    relevant = [entry for score, entry in scored if score > 0]
    if not relevant:
        # No keyword overlap at all — return top by usage as fallback
        relevant = [entry for _, entry in scored]

    result = relevant[:limit]
    if result:
        top_kw = keywords[:10]
        logger.info(
            "BRD keywords: %s → matched %d/%d KB entries",
            top_kw, len(result), len(candidates),
        )
    return result


# ---------------------------------------------------------------------------
# Generate from BRD (enterprise test case generation)
# ---------------------------------------------------------------------------
@router.post("/generate-from-brd", response_model=List[TestCaseResponse])
def generate_from_brd(
    body: dict,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """
    Generate enterprise-grade test cases from BRD text + optional reference TCs.

    Body fields:
      - brd_text: str (required) — the requirement / BRD document text
      - domain: str (default "mdm") — mdm, data_engineering, api, ui
      - sub_domain: str (default "") — reltio, snowflake, databricks, etc.
      - reference_test_cases: list[dict] (optional) — parsed reference TCs from Excel
      - count: int (default 10) — number of test cases to generate
      - test_plan_id: str (optional) — UUID of test plan to bind generated TCs to
    """
    import asyncio
    from pipeline.orchestrator import Orchestrator, GenerateRequest

    brd_text = body.get("brd_text", "")
    if not brd_text or len(brd_text) < 10:
        raise HTTPException(400, "brd_text is required (min 10 chars)")

    domain = body.get("domain", "mdm")
    sub_domain = body.get("sub_domain", "")
    count = min(body.get("count", 10), 50)
    ref_tcs = body.get("reference_test_cases", [])
    test_plan_id_str = body.get("test_plan_id")
    save_to_kb = body.get("save_to_kb", True)  # Auto-save references to KB

    # Build reference TC context text
    ref_text = ""
    kb_retrieved = 0
    if ref_tcs:
        ref_lines = []
        for tc in ref_tcs[:5]:
            ref_lines.append(f"--- {tc.get('test_case_id', 'TC-REF')}: {tc.get('title', '')} ---")
            for step in tc.get("test_steps", [])[:6]:
                step_info = f"  Step {step.get('step_number', '?')}: {step.get('action', '')}"
                if step.get("step_type"):
                    step_info += f" [{step['step_type']}]"
                if step.get("sql_script"):
                    step_info += f"\n    SQL: {step['sql_script'][:150]}"
                step_info += f"\n    Expected: {step.get('expected_result', '')}"
                ref_lines.append(step_info)
        ref_text = "\n".join(ref_lines)[:3000]
    else:
        # --- AUTO-RETRIEVE from KB — BRD-aware keyword matching ---
        kb_entries = _retrieve_kb_for_brd(db, brd_text, domain, sub_domain)

        if kb_entries:
            ref_lines = [
                f"=== KNOWLEDGE BASE REFERENCE TEST CASES "
                f"({len(kb_entries)} entries, matched to your BRD) ==="
            ]
            for entry in kb_entries:
                ref_lines.append(f"\n{entry.content[:600]}")
                entry.usage_count += 1
            ref_text = "\n".join(ref_lines)[:3000]
            kb_retrieved = len(kb_entries)
            db.flush()
            logger.info(
                "Auto-retrieved %d KB reference TCs for domain=%s sub=%s "
                "(BRD-aware keyword matching)",
                kb_retrieved, domain, sub_domain,
            )

    # Build generation request
    gen_request = GenerateRequest(
        description=brd_text[:6000],
        domain=domain,
        sub_domain=sub_domain,
        count=count,
        brd_prd_context=brd_text,
        reference_tc_context=ref_text,
        example_test_cases=ref_tcs[:3] if ref_tcs else None,
        skip_review=True,  # Agent-driven, no review loop needed
        temperature=0.3,
        max_tokens=16384,  # Enterprise TCs (4-10 steps each) need more tokens
    )

    # Run the orchestrator
    orchestrator = Orchestrator()
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(orchestrator.run(gen_request))
        loop.close()
    except Exception as exc:
        logger.error("Generation failed: %s", exc, exc_info=True)
        raise HTTPException(500, f"Generation failed: {str(exc)[:200]}")

    if not result.test_cases:
        raise HTTPException(422, "No test cases generated. Try a more detailed BRD.")

    # Validate test_plan_id
    plan_id = None
    if test_plan_id_str:
        try:
            plan_id = uuid.UUID(test_plan_id_str)
        except ValueError:
            raise HTTPException(400, f"Invalid test_plan_id: {test_plan_id_str}")
        plan = db.query(TestPlan).filter(
            TestPlan.id == plan_id,
            TestPlan.project_id == project.id,
        ).first()
        if not plan:
            raise HTTPException(404, f"Test plan {plan_id} not found in this project")

    # Save generated TCs to DB
    saved: List[TestCase] = []
    for tc_data in result.test_cases:
        tc_id = tc_data.get("test_case_id", f"TC-GEN-{uuid.uuid4().hex[:6].upper()}")

        # Check for duplicate
        existing = db.query(TestCase).filter(
            TestCase.project_id == project.id,
            TestCase.test_case_id == tc_id,
        ).first()
        if existing:
            tc_id = f"{tc_id}-{uuid.uuid4().hex[:4].upper()}"

        # Map enterprise priority names to QAForge P1-P4
        raw_pri = str(tc_data.get("priority", "P2")).strip().lower()
        if raw_pri in ("p1", "critical", "blocker"):
            priority = "P1"
        elif raw_pri in ("p2", "high"):
            priority = "P2"
        elif raw_pri in ("p3", "medium"):
            priority = "P3"
        elif raw_pri in ("p4", "low"):
            priority = "P4"
        elif raw_pri.startswith("p") and raw_pri[1:].isdigit():
            priority = raw_pri.upper()[:2]
        else:
            priority = "P2"

        # Map enterprise category names to valid QAForge categories
        raw_cat = str(tc_data.get("category", "functional")).strip().lower()
        category_map = {
            "functional": "functional",
            "integration": "integration",
            "regression": "regression",
            "smoke": "smoke",
            "e2e": "e2e",
            "data_quality": "data_quality",
            "match_rule": "match_rule",
            "migration": "migration",
            # Enterprise category aliases
            "schema/table changes": "functional",
            "entity load validation": "functional",
            "relationship load": "functional",
            "data mapping": "functional",
            "count reconciliation": "functional",
            "rdm/lookup validation": "functional",
            "odl/incremental changes": "functional",
            "schema validation": "functional",
            "data comparison": "functional",
            "aggregate validation": "functional",
            "freshness check": "functional",
            "scd type 2": "migration",
            "incremental load": "migration",
            "duplicate detection": "data_quality",
            "null pk validation": "data_quality",
        }
        category = category_map.get(raw_cat, "functional")

        # Map execution_type to valid QAForge values
        raw_exec = str(tc_data.get("execution_type", "manual")).strip().lower()
        valid_exec_types = {"api", "ui", "sql", "manual", "mdm"}
        execution_type = raw_exec if raw_exec in valid_exec_types else "manual"

        tc = TestCase(
            id=uuid.uuid4(),
            project_id=project.id,
            test_plan_id=plan_id,
            test_case_id=tc_id,
            title=tc_data.get("title", "Generated TC")[:500],
            description=tc_data.get("description", ""),
            preconditions=tc_data.get("preconditions", ""),
            test_steps=tc_data.get("test_steps", []),
            expected_result=tc_data.get("expected_result", ""),
            test_data=tc_data.get("test_data"),
            priority=priority,
            category=category,
            domain_tags=tc_data.get("domain_tags", []),
            execution_type=execution_type,
            source="ai_generated",
            status="draft",
            created_by=project.created_by,
            generated_by_model=result.metadata.get("model") if result.metadata else None,
            generation_metadata=result.metadata,
        )
        db.add(tc)
        saved.append(tc)

    # --- AUTO-SAVE reference TCs to Knowledge Base ---
    kb_saved = 0
    if save_to_kb and ref_tcs:
        for tc in ref_tcs[:10]:  # Limit to 10 KB entries per upload
            tc_id = tc.get("test_case_id", "TC-REF")
            tc_title = tc.get("title", "Reference TC")[:200]

            # Check if already exists in KB (by title + domain)
            existing_kb = db.query(KnowledgeEntry).filter(
                KnowledgeEntry.domain == domain,
                KnowledgeEntry.title == f"[REF] {tc_title}",
            ).first()
            if existing_kb:
                continue

            # Build rich content from the TC for KB storage
            content_parts = [f"Test Case: {tc_id} — {tc_title}"]
            if tc.get("description"):
                content_parts.append(f"Description: {tc['description'][:300]}")
            if tc.get("preconditions"):
                content_parts.append(f"Prerequisites: {tc['preconditions'][:200]}")
            for step in tc.get("test_steps", [])[:8]:
                if isinstance(step, dict):
                    step_line = f"Step {step.get('step_number', '?')}: {step.get('action', '')}"
                    if step.get("step_type"):
                        step_line += f" [{step['step_type']}]"
                    if step.get("sql_script"):
                        step_line += f"\n  SQL: {step['sql_script'][:200]}"
                    step_line += f"\n  Expected: {step.get('expected_result', '')}"
                    content_parts.append(step_line)
            if tc.get("expected_result"):
                content_parts.append(f"Overall Expected: {tc['expected_result'][:200]}")

            kb_entry = KnowledgeEntry(
                domain=domain,
                sub_domain=sub_domain or None,
                entry_type="test_case",
                title=f"[REF] {tc_title}",
                content="\n".join(content_parts),
                tags=[domain, sub_domain, "reference", "enterprise"]
                     if sub_domain else [domain, "reference", "enterprise"],
                source_project_id=project.id,
                created_by=project.created_by,
            )
            db.add(kb_entry)
            kb_saved += 1

    db.commit()
    for tc in saved:
        db.refresh(tc)

    logger.info(
        "Generated %d test cases from BRD for project %s (domain=%s, sub=%s), "
        "KB: %d retrieved, %d saved",
        len(saved), project.name, domain, sub_domain, kb_retrieved, kb_saved,
    )
    return saved


# ---------------------------------------------------------------------------
# Upload Reference TCs to Knowledge Base
# ---------------------------------------------------------------------------
@router.post("/upload-reference")
def upload_reference_to_kb(
    body: dict,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """
    Upload reference test cases to the Knowledge Base for future generation.

    Agents upload parsed reference TCs (from Excel, JSON, etc.) and QAForge
    stores them as KB entries. Future generate-from-brd calls automatically
    retrieve these as context — no need to re-upload samples.

    Body fields:
      - reference_test_cases: list[dict] (required) — parsed reference TCs
      - domain: str (required) — mdm, data_engineering, api, ui
      - sub_domain: str (optional) — reltio, snowflake, databricks, etc.
      - source_name: str (optional) — human-readable source (e.g. "MDM Network Entity Load.xlsx")
    """
    ref_tcs = body.get("reference_test_cases", [])
    if not ref_tcs:
        raise HTTPException(400, "reference_test_cases is required (non-empty list)")

    domain = body.get("domain", "mdm")
    sub_domain = body.get("sub_domain", "")
    source_name = body.get("source_name", "agent-upload")

    created = 0
    skipped = 0
    for tc in ref_tcs[:50]:  # Max 50 per upload
        tc_id = tc.get("test_case_id", "TC-REF")
        tc_title = tc.get("title", "Reference TC")[:200]
        kb_title = f"[REF] {tc_title}"

        # Skip duplicates (by title + domain)
        existing = db.query(KnowledgeEntry).filter(
            KnowledgeEntry.domain == domain,
            KnowledgeEntry.title == kb_title,
        ).first()
        if existing:
            skipped += 1
            continue

        # Build rich content from the TC
        content_parts = [f"Test Case: {tc_id} — {tc_title}"]
        if tc.get("description"):
            content_parts.append(f"Description: {tc['description'][:300]}")
        if tc.get("category"):
            content_parts.append(f"Category: {tc['category']}")
        if tc.get("preconditions"):
            content_parts.append(f"Prerequisites: {tc['preconditions'][:200]}")
        for step in tc.get("test_steps", [])[:10]:
            if isinstance(step, dict):
                step_line = f"Step {step.get('step_number', '?')}: {step.get('action', '')}"
                if step.get("step_type"):
                    step_line += f" [{step['step_type']}]"
                if step.get("sql_script"):
                    step_line += f"\n  SQL: {step['sql_script'][:250]}"
                step_line += f"\n  Expected: {step.get('expected_result', '')}"
                content_parts.append(step_line)
        if tc.get("expected_result"):
            content_parts.append(f"Overall Expected: {tc['expected_result'][:200]}")

        tags = [domain, "reference", "enterprise", f"source:{source_name}"]
        if sub_domain:
            tags.insert(1, sub_domain)

        kb_entry = KnowledgeEntry(
            domain=domain,
            sub_domain=sub_domain or None,
            entry_type="test_case",
            title=kb_title,
            content="\n".join(content_parts),
            tags=tags,
            source_project_id=project.id,
            created_by=project.created_by,
        )
        db.add(kb_entry)
        created += 1

    db.commit()

    # Count total KB entries for this domain
    total_domain = db.query(KnowledgeEntry).filter(
        KnowledgeEntry.domain == domain,
        KnowledgeEntry.entry_type == "test_case",
    ).count()

    logger.info(
        "Agent uploaded %d reference TCs to KB for project %s (domain=%s, sub=%s, skipped=%d)",
        created, project.name, domain, sub_domain, skipped,
    )

    return {
        "message": f"Uploaded {created} reference TCs to knowledge base"
                   + (f" ({skipped} duplicates skipped)" if skipped else ""),
        "created": created,
        "skipped": skipped,
        "total_domain_kb_entries": total_domain,
        "domain": domain,
        "sub_domain": sub_domain,
    }


# ---------------------------------------------------------------------------
# KB Stats for Agent (lightweight, no JWT needed)
# ---------------------------------------------------------------------------
@router.get("/kb-stats")
def get_kb_stats_for_agent(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """
    Get knowledge base statistics for the agent.
    Shows how many reference TCs are available per domain.
    """
    from sqlalchemy import func

    query = db.query(
        KnowledgeEntry.domain,
        KnowledgeEntry.sub_domain,
        KnowledgeEntry.entry_type,
        func.count(KnowledgeEntry.id).label("count"),
    ).group_by(
        KnowledgeEntry.domain,
        KnowledgeEntry.sub_domain,
        KnowledgeEntry.entry_type,
    )

    if domain:
        query = query.filter(KnowledgeEntry.domain == domain)

    rows = query.all()
    stats = {}
    total = 0
    for row in rows:
        key = f"{row.domain}/{row.sub_domain or 'general'}"
        if key not in stats:
            stats[key] = {"domain": row.domain, "sub_domain": row.sub_domain, "entries": {}}
        stats[key]["entries"][row.entry_type] = row.count
        total += row.count

    return {
        "total_kb_entries": total,
        "by_domain": list(stats.values()),
    }


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
@router.post("/sessions", response_model=AgentSessionResponse)
def create_agent_session(
    body: AgentSessionCreate,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Start a new agent session for the authenticated project."""
    session = AgentSession(
        id=uuid.uuid4(),
        project_id=project.id,
        agent_name=body.agent_name,
        agent_version=body.agent_version,
        submission_mode=body.submission_mode,
        session_meta=body.session_meta,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    logger.info(
        "Agent session started: %s (%s) for project %s [%s mode]",
        body.agent_name,
        session.id,
        project.name,
        body.submission_mode,
    )
    return session


# ---------------------------------------------------------------------------
# Test Plans (agent can create plans to group test cases + results)
# ---------------------------------------------------------------------------
@router.post("/test-plans", response_model=TestPlanResponse)
def create_test_plan(
    body: TestPlanCreate,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Create a test plan so agent can group test cases and execution results."""
    plan = TestPlan(
        id=uuid.uuid4(),
        project_id=project.id,
        name=body.name,
        description=body.description,
        plan_type=body.plan_type,
        status="active",
        created_by=project.created_by,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    logger.info(
        "Agent created test plan '%s' (%s) for project %s",
        body.name,
        plan.id,
        project.name,
    )
    return plan


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
@router.post("/test-cases", response_model=List[TestCaseResponse])
def submit_test_cases(
    body: AgentTestCaseBatchSubmit,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """
    Submit one or more test cases. They are stored with status=draft
    and source=ai_generated, pending human QA review.
    """
    created = []
    for tc in body.test_cases:
        plan_id = tc.test_plan_id or body.test_plan_id

        # Validate test_plan belongs to this project if specified
        if plan_id:
            plan = db.query(TestPlan).filter(
                TestPlan.id == plan_id,
                TestPlan.project_id == project.id,
            ).first()
            if not plan:
                raise HTTPException(400, f"Test plan {plan_id} not found in project")

        # Check for duplicate test_case_id within project
        existing = db.query(TestCase).filter(
            TestCase.project_id == project.id,
            TestCase.test_case_id == tc.test_case_id,
        ).first()
        if existing:
            raise HTTPException(
                409,
                f"Test case ID '{tc.test_case_id}' already exists in project",
            )

        test_case = TestCase(
            id=uuid.uuid4(),
            project_id=project.id,
            test_plan_id=plan_id,
            requirement_id=tc.requirement_id,
            test_case_id=tc.test_case_id,
            title=tc.title,
            description=tc.description,
            preconditions=tc.preconditions,
            test_steps=[s.model_dump() for s in tc.test_steps] if tc.test_steps else None,
            expected_result=tc.expected_result,
            test_data=tc.test_data,
            priority=tc.priority,
            category=tc.category,
            domain_tags=tc.domain_tags,
            execution_type=tc.execution_type,
            source="ai_generated",
            status="draft",
            created_by=project.created_by,  # attribute to project owner
        )
        db.add(test_case)
        created.append(test_case)

    db.commit()
    for tc in created:
        db.refresh(tc)

    logger.info(
        "Agent submitted %d test cases for project %s",
        len(created),
        project.name,
    )
    return created


@router.get("/test-cases", response_model=List[TestCaseResponse])
def get_test_cases(
    status: Optional[str] = Query(None, description="Filter by status"),
    test_plan_id: Optional[uuid.UUID] = Query(None),
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Get test cases for the authenticated project, optionally filtered."""
    q = db.query(TestCase).filter(TestCase.project_id == project.id)
    if status:
        q = q.filter(TestCase.status == status)
    if test_plan_id:
        q = q.filter(TestCase.test_plan_id == test_plan_id)
    return q.order_by(TestCase.created_at).all()


# ---------------------------------------------------------------------------
# Execution Results
# ---------------------------------------------------------------------------
@router.post("/executions", response_model=List[ExecutionResultResponse])
def submit_executions(
    body: AgentExecutionBatchSubmit,
    session_id: Optional[uuid.UUID] = Query(None, description="Agent session ID"),
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """
    Submit one or more execution results with proof artifacts.
    Each result is linked to a test case.
    """
    # Validate session if provided
    agent_session = None
    if session_id:
        agent_session = db.query(AgentSession).filter(
            AgentSession.id == session_id,
            AgentSession.project_id == project.id,
        ).first()
        if not agent_session:
            raise HTTPException(400, f"Agent session {session_id} not found")
        # Update last_active_at
        agent_session.last_active_at = datetime.now(timezone.utc)

    created = []
    for ex in body.executions:
        # Validate test case belongs to this project
        test_case = db.query(TestCase).filter(
            TestCase.id == ex.test_case_id,
            TestCase.project_id == project.id,
        ).first()
        if not test_case:
            raise HTTPException(
                400,
                f"Test case {ex.test_case_id} not found in project",
            )

        result = ExecutionResult(
            id=uuid.uuid4(),
            test_case_id=ex.test_case_id,
            test_plan_id=ex.test_plan_id or test_case.test_plan_id,
            status=ex.status,
            actual_result=ex.actual_result,
            duration_ms=ex.duration_ms,
            error_message=ex.error_message,
            environment=ex.environment,
            executed_by=agent_session.agent_name if agent_session else "agent",
            agent_session_id=session_id,
            review_status="pending",
        )
        db.add(result)
        db.flush()  # get result.id for proof artifacts

        # Add proof artifacts
        if ex.proof_artifacts:
            for pa in ex.proof_artifacts:
                artifact = ProofArtifact(
                    id=uuid.uuid4(),
                    execution_result_id=result.id,
                    proof_type=pa.proof_type,
                    title=pa.title,
                    content=pa.content,
                    file_path=pa.file_path,
                )
                db.add(artifact)

        # Update test case status to reflect execution
        test_case.status = "executed" if ex.status in ("passed", "failed") else ex.status
        if ex.status == "passed":
            test_case.status = "passed"
        elif ex.status == "failed":
            test_case.status = "failed"

        created.append(result)

    db.commit()
    for r in created:
        db.refresh(r)

    logger.info(
        "Agent submitted %d execution results for project %s",
        len(created),
        project.name,
    )
    return created


@router.post("/executions/{execution_id}/proof", response_model=ProofArtifactResponse)
def add_proof_artifact(
    execution_id: uuid.UUID,
    body: ProofArtifactSubmit,
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Add a proof artifact to an existing execution result."""
    result = db.query(ExecutionResult).join(TestCase).filter(
        ExecutionResult.id == execution_id,
        TestCase.project_id == project.id,
    ).first()
    if not result:
        raise HTTPException(404, "Execution result not found")

    artifact = ProofArtifact(
        id=uuid.uuid4(),
        execution_result_id=execution_id,
        proof_type=body.proof_type,
        title=body.title,
        content=body.content,
        file_path=body.file_path,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
@router.get("/summary", response_model=AgentSummaryResponse)
def get_summary(
    test_plan_id: Optional[uuid.UUID] = Query(None),
    project: Project = Depends(get_agent_project),
    db: Session = Depends(get_db),
):
    """Get progress summary for the project (or a specific test plan)."""
    tc_query = db.query(TestCase).filter(TestCase.project_id == project.id)
    ex_query = db.query(ExecutionResult).join(TestCase).filter(
        TestCase.project_id == project.id
    )

    if test_plan_id:
        tc_query = tc_query.filter(TestCase.test_plan_id == test_plan_id)
        ex_query = ex_query.filter(ExecutionResult.test_plan_id == test_plan_id)

    test_cases = tc_query.all()
    executions = ex_query.all()

    by_status = {}
    for tc in test_cases:
        by_status[tc.status] = by_status.get(tc.status, 0) + 1

    passed = sum(1 for e in executions if e.status == "passed")
    failed = sum(1 for e in executions if e.status == "failed")
    pending_review = sum(1 for e in executions if e.review_status == "pending")

    total_exec = len(executions)
    pass_rate = (passed / total_exec * 100) if total_exec > 0 else None

    return AgentSummaryResponse(
        project_name=project.name,
        test_plan_id=test_plan_id,
        total_test_cases=len(test_cases),
        by_status=by_status,
        total_executions=total_exec,
        passed=passed,
        failed=failed,
        pending_review=pending_review,
        pass_rate=round(pass_rate, 1) if pass_rate is not None else None,
    )
