"""
QAForge -- Requirements management routes.

Prefix: /api/projects/{project_id}/requirements

Note: The main.py prefix_map has "requirements" -> "/api/requirements", but
these routes use path-based project scoping. The router itself defines the
full sub-paths including the project_id prefix.

Endpoints:
    POST   /                              — add manual requirement
    GET    /                              — list requirements for project
    PUT    /{req_id}                      — update requirement
    DELETE /{req_id}                      — delete requirement
    POST   /upload                        — upload raw BRD/PRD text
    POST   /extract                       — LLM-powered extraction
"""

import json
import logging
import os
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from db_models import Project, Requirement, User
from db_session import get_db
from dependencies import (
    audit_log,
    get_client_ip,
    get_current_user,
    sanitize_string,
    track_cost,
)
from models import (
    MessageResponse,
    RequirementCreate,
    RequirementExtractRequest,
    RequirementResponse,
    RequirementUpdate,
    UploadTextRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for uploaded BRD/PRD text, keyed by project_id.
# In production this would be persisted, but for Phase 1 this is sufficient.
_uploaded_texts: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_project_or_404(project_id: uuid.UUID, db: Session) -> Project:
    """Fetch a project by ID or raise 404."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def _get_next_req_id(project_id: uuid.UUID, db: Session) -> str:
    """Generate the next sequential REQ-NNN id for a project."""
    count = db.query(Requirement).filter(
        Requirement.project_id == project_id
    ).count()
    return f"REQ-{count + 1:03d}"


# ---------------------------------------------------------------------------
# POST /{project_id}/requirements/
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/requirements",
    response_model=RequirementResponse,
    summary="Add a manual requirement",
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    project_id: uuid.UUID,
    body: RequirementCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a requirement to a project."""
    _get_project_or_404(project_id, db)

    # Check for duplicate req_id within this project
    existing = db.query(Requirement).filter(
        Requirement.project_id == project_id,
        Requirement.req_id == body.req_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Requirement '{body.req_id}' already exists in this project",
        )

    req = Requirement(
        project_id=project_id,
        req_id=body.req_id,
        title=sanitize_string(body.title) or body.title,
        description=sanitize_string(body.description) if body.description else None,
        priority=body.priority,
        category=sanitize_string(body.category) if body.category else None,
        source=body.source,
    )
    db.add(req)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="create_requirement",
        entity_type="requirement",
        entity_id=str(req.id),
        details={"project_id": str(project_id), "req_id": req.req_id},
        ip_address=get_client_ip(request),
    )

    return RequirementResponse.model_validate(req)


# ---------------------------------------------------------------------------
# GET /{project_id}/requirements/
# ---------------------------------------------------------------------------
@router.get(
    "/{project_id}/requirements",
    response_model=list[RequirementResponse],
    summary="List requirements for a project",
)
def list_requirements(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all requirements belonging to a project."""
    _get_project_or_404(project_id, db)

    reqs = (
        db.query(Requirement)
        .filter(Requirement.project_id == project_id)
        .order_by(Requirement.created_at.asc())
        .all()
    )
    return [RequirementResponse.model_validate(r) for r in reqs]


# ---------------------------------------------------------------------------
# PUT /{project_id}/requirements/{req_id}
# ---------------------------------------------------------------------------
@router.put(
    "/{project_id}/requirements/{requirement_id}",
    response_model=RequirementResponse,
    summary="Update a requirement",
)
def update_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    body: RequirementUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update fields of an existing requirement."""
    _get_project_or_404(project_id, db)

    req = db.query(Requirement).filter(
        Requirement.id == requirement_id,
        Requirement.project_id == project_id,
    ).first()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requirement not found",
        )

    if body.title is not None:
        req.title = sanitize_string(body.title) or body.title
    if body.description is not None:
        req.description = sanitize_string(body.description)
    if body.priority is not None:
        req.priority = body.priority
    if body.category is not None:
        req.category = sanitize_string(body.category)
    if body.status is not None:
        req.status = body.status

    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="update_requirement",
        entity_type="requirement",
        entity_id=str(req.id),
        details=body.model_dump(exclude_none=True),
        ip_address=get_client_ip(request),
    )

    return RequirementResponse.model_validate(req)


# ---------------------------------------------------------------------------
# DELETE /{project_id}/requirements/{req_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{project_id}/requirements/{requirement_id}",
    response_model=MessageResponse,
    summary="Delete a requirement",
)
def delete_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a requirement from a project."""
    _get_project_or_404(project_id, db)

    req = db.query(Requirement).filter(
        Requirement.id == requirement_id,
        Requirement.project_id == project_id,
    ).first()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requirement not found",
        )

    req_display = req.req_id
    db.delete(req)
    db.flush()

    audit_log(
        db,
        user_id=current_user.id,
        action="delete_requirement",
        entity_type="requirement",
        entity_id=str(requirement_id),
        details={"project_id": str(project_id), "req_id": req_display},
        ip_address=get_client_ip(request),
    )

    return MessageResponse(message=f"Requirement '{req_display}' deleted")


# ---------------------------------------------------------------------------
# POST /{project_id}/requirements/upload
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/requirements/upload",
    response_model=MessageResponse,
    summary="Upload BRD/PRD text",
    status_code=status.HTTP_201_CREATED,
)
def upload_text(
    project_id: uuid.UUID,
    body: UploadTextRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accept raw BRD/PRD text for a project.

    The text is stored temporarily and can be used by the /extract endpoint
    to perform LLM-powered requirement extraction.
    """
    _get_project_or_404(project_id, db)

    _uploaded_texts[str(project_id)] = {
        "text": body.document_text,
        "type": body.document_type,
        "uploaded_by": str(current_user.id),
    }

    audit_log(
        db,
        user_id=current_user.id,
        action="upload_requirements_text",
        entity_type="requirement",
        entity_id=str(project_id),
        details={
            "document_type": body.document_type,
            "text_length": len(body.document_text),
        },
        ip_address=get_client_ip(request),
    )

    return MessageResponse(
        message="Document text uploaded successfully",
        detail=f"Stored {len(body.document_text)} characters of {body.document_type.upper()} text",
    )


# ---------------------------------------------------------------------------
# POST /{project_id}/requirements/extract
# ---------------------------------------------------------------------------
@router.post(
    "/{project_id}/requirements/extract",
    response_model=list[RequirementResponse],
    summary="Extract requirements using LLM",
    status_code=status.HTTP_201_CREATED,
)
def extract_requirements(
    project_id: uuid.UUID,
    body: RequirementExtractRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Use an LLM to extract structured requirements from document text.

    Attempts to use the core LLM provider. Falls back to a simple
    heuristic extractor if the LLM is not configured or fails.
    """
    project = _get_project_or_404(project_id, db)

    document_text = body.document_text

    # Attempt LLM extraction
    extracted = _extract_via_llm(
        document_text=document_text,
        document_type=body.document_type,
        domain=body.domain or project.domain,
        sub_domain=body.sub_domain or project.sub_domain,
        project_id=project_id,
        user_id=current_user.id,
        db=db,
        focus_areas=body.focus_areas,
    )

    # Persist extracted requirements
    created_reqs = []
    base_count = db.query(Requirement).filter(
        Requirement.project_id == project_id
    ).count()

    for i, item in enumerate(extracted):
        req_id = f"REQ-{base_count + i + 1:03d}"

        # Check for duplicate req_id — keep incrementing until unique
        while db.query(Requirement).filter(
            Requirement.project_id == project_id,
            Requirement.req_id == req_id,
        ).first():
            base_count += 1
            req_id = f"REQ-{base_count + i + 1:03d}"

        # Build description with source section traceability
        description = sanitize_string(item.get("description")) or ""
        source_section = item.get("source_section", "")
        if source_section:
            description = f"[Source: {sanitize_string(source_section)}]\n\n{description}"

        req = Requirement(
            project_id=project_id,
            req_id=req_id,
            title=sanitize_string(item.get("title", "Untitled Requirement")) or "Untitled",
            description=description,
            priority=item.get("priority", "medium"),
            category=sanitize_string(item.get("category")),
            source=body.document_type,
        )
        db.add(req)
        db.flush()
        created_reqs.append(req)

    audit_log(
        db,
        user_id=current_user.id,
        action="extract_requirements",
        entity_type="requirement",
        entity_id=str(project_id),
        details={
            "document_type": body.document_type,
            "extracted_count": len(created_reqs),
        },
        ip_address=get_client_ip(request),
    )

    logger.info(
        "Extracted %d requirements for project %s by %s",
        len(created_reqs),
        project.name,
        current_user.email,
    )

    return [RequirementResponse.model_validate(r) for r in created_reqs]


# ---------------------------------------------------------------------------
# Domain-specific extraction guidance
# ---------------------------------------------------------------------------
_DOMAIN_EXTRACTION_GUIDANCE: dict[str, str] = {
    "mdm": """You are extracting requirements for a Master Data Management (MDM) system.
Pay special attention to:
- Data quality rules (completeness, uniqueness, consistency, accuracy, timeliness)
- Match/merge logic and survivorship rules — each rule is a separate requirement
- Golden record creation, hierarchy management, cross-reference integrity
- Data stewardship workflows (approval, escalation, notification)
- Integration points (inbound feeds, outbound subscriptions, real-time vs batch)
- Data governance policies (retention, archival, masking, consent)
- UI requirements for data steward workbench, search, bulk operations
- Performance: load volumes, SLA for match/merge, API response times
- Migration / initial load requirements (source mapping, transformation, reconciliation)

Categories to use: data_quality, match_merge, integration, governance, ui, performance, migration, security, workflow""",

    "ai": """You are extracting requirements for an AI / GenAI / Machine Learning system.
Pay special attention to:
- Model input/output validation (schema, format, token limits, content safety)
- Prompt engineering requirements (templates, variables, system prompts, guardrails)
- RAG pipeline requirements (retrieval accuracy, chunking, embedding, re-ranking)
- Hallucination detection and factual grounding
- Latency, throughput, and cost constraints per model call
- Fine-tuning data requirements (training data quality, format, volume)
- Evaluation metrics (BLEU, ROUGE, human evaluation, A/B testing)
- Safety: prompt injection prevention, PII filtering, content moderation
- Observability: logging, tracing, token usage tracking, cost dashboards
- Fallback and error handling (model unavailable, timeout, rate limiting)

Categories to use: model_validation, prompt_engineering, rag, safety, performance, evaluation, observability, integration, data_pipeline""",

    "data_engineering": """You are extracting requirements for a Data Engineering / Data Platform system.
Pay special attention to:
- Pipeline requirements (ETL/ELT, source-to-target mapping, transformation rules)
- Data quality checks at each pipeline stage (schema validation, null handling, type casting)
- Orchestration (DAG dependencies, scheduling, retry logic, SLA monitoring)
- Incremental vs full load strategies, CDC (Change Data Capture) patterns
- Schema evolution and backward compatibility
- Data lakehouse / warehouse requirements (partitioning, clustering, materialized views)
- Streaming vs batch processing requirements
- Data freshness SLAs and reconciliation (source-to-target row counts, checksums)
- Security (encryption at rest/transit, column-level masking, RBAC)
- Cost optimization (compute scaling, storage tiering, query optimization)

Categories to use: pipeline, data_quality, orchestration, schema, streaming, security, performance, integration, governance, cost_optimization""",

    "integration": """You are extracting requirements for a System Integration / API platform.
Pay special attention to:
- API requirements (REST/GraphQL endpoints, request/response schemas, versioning)
- Authentication and authorization (OAuth, API keys, JWT, mTLS)
- Message queue / event streaming (Kafka, RabbitMQ, event schemas, dead letter queues)
- Error handling (retry policies, circuit breakers, fallback, idempotency)
- Data transformation and mapping between systems
- Rate limiting, throttling, and backpressure
- Monitoring (health checks, latency metrics, error rates, alerting)
- Contract testing and API compatibility
- Batch integration (file-based, SFTP, scheduled jobs)
- Third-party system connectors (ERP, CRM, payment gateways)

Categories to use: api, authentication, messaging, error_handling, transformation, monitoring, performance, security, batch, connector""",

    "digital": """You are extracting requirements for a Digital / Web / Mobile application.
Pay special attention to:
- User interface requirements (layouts, components, responsive design, accessibility)
- User flows (login, registration, checkout, search, navigation)
- Form validation rules (field-level, cross-field, async validation)
- State management and data flow requirements
- Performance (page load time, Core Web Vitals, bundle size, caching)
- Browser/device compatibility requirements
- Accessibility (WCAG compliance level, screen readers, keyboard navigation)
- SEO requirements (meta tags, structured data, SSR/SSG)
- Offline capability and progressive web app features
- Analytics and tracking requirements

Categories to use: ui, user_flow, validation, performance, accessibility, compatibility, seo, analytics, security, integration""",
}

# Default guidance for domains not explicitly listed
_DEFAULT_EXTRACTION_GUIDANCE = """You are extracting requirements from a technical document.
Pay special attention to:
- Functional requirements (what the system must do)
- Non-functional requirements (performance, security, scalability, availability)
- Integration points with other systems
- Data requirements (inputs, outputs, storage, validation)
- User interface and experience requirements
- Business rules and workflow requirements
- Compliance and regulatory requirements
- Error handling and edge cases

Categories to use: functional, non_functional, integration, data, ui, business_rule, compliance, security, performance"""


# ---------------------------------------------------------------------------
# LLM extraction helper (Sonnet-powered, domain-aware)
# ---------------------------------------------------------------------------

# Maximum characters of document text to send in a single LLM call
_MAX_CHUNK_CHARS = 30_000
# Overlap between chunks to avoid losing context at boundaries
_CHUNK_OVERLAP = 2_000


def _extract_via_llm(
    document_text: str,
    document_type: str,
    domain: str,
    sub_domain: str,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
    focus_areas: str | None = None,
) -> list[dict]:
    """
    Use Sonnet (smart model) to extract testable requirements from document text.

    Features:
    - Domain-specific extraction guidance (MDM, AI, Data Eng, Integration, Digital)
    - Large context window (30K chars per chunk, with overlap for large docs)
    - Structured system + user prompt separation
    - Robust JSON parsing (handles markdown code blocks)
    - Deduplication across chunks
    - Falls back to heuristic if LLM is unavailable
    """
    try:
        from core.llm_provider import get_llm_provider  # type: ignore
        provider = get_llm_provider()
    except (ImportError, Exception) as exc:
        logger.warning("LLM provider not available for extraction: %s", exc)
        return _heuristic_extract(document_text, document_type)

    # Pick domain guidance
    domain_lower = (domain or "").lower().strip()
    domain_guidance = _DEFAULT_EXTRACTION_GUIDANCE
    for key, guidance in _DOMAIN_EXTRACTION_GUIDANCE.items():
        if key in domain_lower:
            domain_guidance = guidance
            break

    # Build system prompt
    system_prompt = f"""{domain_guidance}

IMPORTANT RULES:
1. Extract EVERY distinct testable requirement — do not summarize or combine.
   A BRD/PRD paragraph often contains 2-5 separate requirements. Split them.
2. Each requirement must be independently testable — a QA engineer should be able
   to write at least one test case from the title + description alone.
3. Titles must be specific and action-oriented (e.g., "System shall validate email
   format on registration form") — NOT vague (e.g., "Email validation").
4. Descriptions must include:
   - What the system should do (the behavior)
   - Acceptance criteria or success conditions
   - Any specific rules, thresholds, or constraints mentioned in the document
   - Edge cases or error conditions if mentioned
5. Priority assignment:
   - "high": Core business logic, security, data integrity, regulatory compliance
   - "medium": Standard functional requirements, UI behavior, integrations
   - "low": Nice-to-have, cosmetic, minor enhancements, logging
6. For each requirement, also extract a "source_section" field — the heading or
   section of the document it came from (helps with traceability).
7. Return ONLY a valid JSON array. No markdown, no explanation, no preamble.
   If the document has no extractable requirements, return an empty array: []"""

    # Add user-specified focus areas
    if focus_areas:
        system_prompt += f"\n\nADDITIONAL FOCUS AREAS (prioritize these):\n{focus_areas}"

    # Split document into chunks if needed
    doc_text = document_text.strip()
    chunks = _split_into_chunks(doc_text, _MAX_CHUNK_CHARS, _CHUNK_OVERLAP)

    all_requirements: list[dict] = []
    total_tokens_in = 0
    total_tokens_out = 0
    model_used = ""

    for chunk_idx, chunk_text in enumerate(chunks):
        chunk_label = f"(chunk {chunk_idx + 1}/{len(chunks)})" if len(chunks) > 1 else ""

        user_prompt = f"""Extract all testable requirements from this {document_type.upper()} document {chunk_label}.

Domain: {domain}
Sub-domain: {sub_domain}

Return a JSON array where each element has these fields:
- "title": string — Specific, action-oriented requirement title (max 120 chars)
- "description": string — Detailed description with acceptance criteria (50-300 words)
- "priority": string — One of "high", "medium", "low"
- "category": string — From the domain-specific categories listed in your instructions
- "source_section": string — Section/heading this came from in the document

=== DOCUMENT TEXT ===
{chunk_text}
=== END DOCUMENT TEXT ==="""

        try:
            logger.info(
                "Extracting requirements %s— domain=%s, chunk_size=%d chars, using smart model",
                chunk_label, domain, len(chunk_text),
            )

            response = provider.complete(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=8192,
                temperature=0.2,  # Low temperature for structured extraction
                model=provider.smart_model,  # Use Sonnet, not Haiku
            )

            model_used = response.model
            total_tokens_in += response.tokens_in
            total_tokens_out += response.tokens_out

            logger.info(
                "LLM response (first 500 chars): %s",
                response.text[:500].replace("\n", "\\n"),
            )

            parsed = _parse_json_response(response.text)
            if parsed:
                all_requirements.extend(parsed)
                logger.info(
                    "Extracted %d requirements from chunk %d (model=%s, tokens=%d+%d)",
                    len(parsed), chunk_idx + 1, response.model,
                    response.tokens_in, response.tokens_out,
                )

        except Exception:
            logger.warning(
                "LLM extraction failed for chunk %d; continuing with other chunks",
                chunk_idx + 1, exc_info=True,
            )

    if not all_requirements:
        logger.warning("LLM extraction yielded 0 requirements; falling back to heuristic")
        return _heuristic_extract(document_text, document_type)

    # Deduplicate by title similarity
    deduped = _deduplicate_requirements(all_requirements)

    # Track cost
    track_cost(
        db,
        user_id=user_id,
        project_id=project_id,
        operation_type="llm",
        provider=getattr(provider, "provider_name", "unknown"),
        model=model_used or getattr(provider, "smart_model", "unknown"),
    )

    logger.info(
        "Requirement extraction complete: %d raw → %d deduped (model=%s, total_tokens=%d+%d)",
        len(all_requirements), len(deduped), model_used,
        total_tokens_in, total_tokens_out,
    )

    return deduped


def _split_into_chunks(text: str, max_chars: int, overlap: int) -> list[str]:
    """
    Split text into overlapping chunks, preferring to break at paragraph
    boundaries (double newline) rather than mid-sentence.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to break at a paragraph boundary
        break_point = text.rfind("\n\n", start + max_chars - 3000, end)
        if break_point == -1:
            # Fall back to sentence boundary
            break_point = text.rfind(". ", start + max_chars - 2000, end)
            if break_point != -1:
                break_point += 1  # Include the period
        if break_point == -1:
            break_point = end

        chunks.append(text[start:break_point])
        start = max(break_point - overlap, start + 1)  # Overlap for context

    return chunks


def _parse_json_response(text: str) -> list[dict] | None:
    """
    Parse LLM response as JSON array, handling common quirks:
    - Markdown code blocks (```json ... ```)
    - Leading/trailing whitespace or text
    - Single-object response (wrap in array)
    - Trailing commas (common LLM error)
    """
    if not text or not text.strip():
        logger.warning("Empty LLM response — nothing to parse")
        return None

    cleaned = text.strip()

    # Step 1: Try to extract from markdown code blocks
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
    if md_match:
        cleaned = md_match.group(1).strip()
        logger.info("Extracted JSON from markdown code block (%d chars)", len(cleaned))

    # Step 2: Find the outermost JSON array
    arr_start = cleaned.find("[")
    arr_end = cleaned.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        cleaned = cleaned[arr_start : arr_end + 1]
    else:
        # Maybe it's a JSON object wrapping an array
        obj_start = cleaned.find("{")
        if obj_start != -1:
            logger.info("No JSON array found, trying as object")

    # Step 3: Fix common JSON errors from LLMs
    # Remove trailing commas before ] or }
    cleaned = re.sub(r",\s*(\]|\})", r"\1", cleaned)

    # Step 4: Parse
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Last resort: try to fix truncated JSON by closing open brackets
        logger.warning(
            "JSON parse error at pos %d: %s\nFirst 300 chars: %s\nLast 300 chars: %s",
            exc.pos, exc.msg, cleaned[:300], cleaned[-300:],
        )
        # Try to fix truncated response by closing brackets
        fix_suffixes = ["]", "}", "}]", "\"}]", "\"}]}", "null}]"]
        for fix_suffix in fix_suffixes:
            try:
                parsed = json.loads(cleaned + fix_suffix)
                logger.info("Fixed truncated JSON with suffix: %s", fix_suffix)
                break
            except json.JSONDecodeError:
                continue
        else:
            return None

    # Step 5: Validate and normalize
    items = []
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        # Might be {"requirements": [...]} or a single requirement
        if "requirements" in parsed and isinstance(parsed["requirements"], list):
            items = parsed["requirements"]
        elif parsed.get("title"):
            items = [parsed]
        else:
            # Try first list-valued key
            for v in parsed.values():
                if isinstance(v, list):
                    items = v
                    break

    if not items:
        logger.warning("Parsed JSON but found no requirement items")
        return None

    valid = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title or len(title) < 5:
            continue
        valid.append({
            "title": title[:200],
            "description": str(item.get("description", "")),
            "priority": item.get("priority", "medium") if item.get("priority") in ("high", "medium", "low") else "medium",
            "category": str(item.get("category", "functional")),
            "source_section": str(item.get("source_section", "")),
        })

    logger.info("Parsed %d valid requirements from LLM response", len(valid))
    return valid if valid else None


def _deduplicate_requirements(reqs: list[dict]) -> list[dict]:
    """
    Remove near-duplicate requirements based on title similarity.
    Uses normalized title comparison — two requirements with >80% word overlap
    are considered duplicates (keep the one with longer description).
    """
    if not reqs:
        return reqs

    deduped: list[dict] = []
    seen_titles: list[set[str]] = []

    for req in reqs:
        title_words = set(req.get("title", "").lower().split())
        if len(title_words) < 2:
            deduped.append(req)
            seen_titles.append(title_words)
            continue

        is_dup = False
        for i, existing_words in enumerate(seen_titles):
            if not existing_words:
                continue
            overlap = len(title_words & existing_words)
            similarity = overlap / max(len(title_words), len(existing_words))
            if similarity > 0.8:
                # Keep the one with the longer description
                existing_desc_len = len(deduped[i].get("description", ""))
                new_desc_len = len(req.get("description", ""))
                if new_desc_len > existing_desc_len:
                    deduped[i] = req
                    seen_titles[i] = title_words
                is_dup = True
                break

        if not is_dup:
            deduped.append(req)
            seen_titles.append(title_words)

    return deduped


def _heuristic_extract(document_text: str, document_type: str) -> list[dict]:
    """
    Improved heuristic fallback: split text into meaningful segments
    and produce structured requirements. Used when LLM is unavailable.
    """
    # Split on double newlines, numbered lists, or bullet points
    segments = re.split(r"\n\s*\n|\n\s*\d+\.\s+|\n\s*[-*]\s+", document_text)
    results = []

    for seg in segments:
        text = seg.strip()
        if len(text) < 30:  # Require meaningful content
            continue

        # Use first sentence or first 120 chars as title
        sentence_end = text.find(".")
        if sentence_end > 0 and sentence_end <= 120:
            title = text[: sentence_end].strip()
        else:
            title = text[:120].strip()
            # Try to break at a word boundary
            last_space = title.rfind(" ")
            if last_space > 60:
                title = title[:last_space]

        # Guess priority from keywords
        text_lower = text.lower()
        if any(kw in text_lower for kw in ("must", "critical", "mandatory", "security", "compliance", "shall")):
            priority = "high"
        elif any(kw in text_lower for kw in ("should", "expected", "required", "important")):
            priority = "medium"
        else:
            priority = "low"

        # Guess category from keywords
        category = "functional"
        if any(kw in text_lower for kw in ("performance", "latency", "throughput", "scalab")):
            category = "performance"
        elif any(kw in text_lower for kw in ("security", "auth", "encrypt", "permission", "access control")):
            category = "security"
        elif any(kw in text_lower for kw in ("integrat", "api", "endpoint", "connect")):
            category = "integration"
        elif any(kw in text_lower for kw in ("data quality", "validat", "format", "schema")):
            category = "data_quality"

        results.append({
            "title": title,
            "description": text,
            "priority": priority,
            "category": category,
        })

        # Limit to 75 requirements from heuristic extraction
        if len(results) >= 75:
            break

    return results
