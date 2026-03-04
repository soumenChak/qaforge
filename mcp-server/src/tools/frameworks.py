"""QAForge MCP Tools — Testing Frameworks

Retrieve domain-specific testing frameworks and check test coverage
against framework standards.
"""
import logging

from src.api_client import agent_get

logger = logging.getLogger("qaforge.mcp.tools.frameworks")


async def get_frameworks_impl(domain: str = "") -> list:
    """Fetch testing frameworks from the Knowledge Base.

    Returns framework_pattern entries with title, content (the testing
    standard), domain, version, and tags.
    """
    params = {}
    if domain:
        params["domain"] = domain
    return await agent_get("/frameworks", params=params or None)


async def check_framework_coverage_impl(domain: str = "") -> dict:
    """Compare existing test cases against framework sections to find gaps.

    Fetches frameworks for the domain, then fetches all test cases, and
    reports which framework sections are covered vs missing.
    """
    # 1. Fetch frameworks
    params = {}
    if domain:
        params["domain"] = domain
    frameworks = await agent_get("/frameworks", params=params or None)

    if not frameworks:
        return {
            "status": "no_frameworks",
            "message": f"No testing frameworks found{' for domain: ' + domain if domain else ''}. "
                       "Add frameworks via the Frameworks page first.",
            "coverage": [],
        }

    # 2. Fetch all test cases
    test_cases = await agent_get("/test-cases")
    tc_text_blob = ""
    if test_cases:
        for tc in test_cases:
            parts = [
                tc.get("title", ""),
                tc.get("description", ""),
                tc.get("expected_result", ""),
                tc.get("category", ""),
            ]
            # Include step details
            for step in tc.get("test_steps", []) or []:
                if isinstance(step, dict):
                    parts.append(step.get("action", ""))
                    parts.append(step.get("expected_result", ""))
            tc_text_blob += " ".join(parts).lower() + "\n"

    # 3. Analyze coverage per framework
    coverage_results = []
    total_sections = 0
    covered_sections = 0

    for fw in frameworks:
        content = fw.get("content", "")
        fw_result = {
            "framework_id": fw.get("id"),
            "framework_title": fw.get("title"),
            "domain": fw.get("domain"),
            "version": fw.get("version"),
            "sections": [],
        }

        # Parse numbered sections from framework content
        lines = content.split("\n")
        current_section = None
        current_items = []

        for line in lines:
            stripped = line.strip()
            # Detect section headers: "1. ENTITY LIFECYCLE", "2. MATCH & MERGE", etc.
            if stripped and len(stripped) > 2 and stripped[0].isdigit() and ". " in stripped[:5]:
                # Save previous section
                if current_section:
                    section_covered, section_items = _analyze_section(
                        current_section, current_items, tc_text_blob
                    )
                    fw_result["sections"].append({
                        "section": current_section,
                        "items_total": len(current_items),
                        "items_covered": section_covered,
                        "coverage_pct": round(section_covered / max(len(current_items), 1) * 100),
                        "missing_items": [
                            item for item, hit in zip(current_items, _item_hits(current_items, tc_text_blob))
                            if not hit
                        ],
                    })
                    total_sections += 1
                    if section_covered > 0:
                        covered_sections += 1

                # Start new section
                current_section = stripped.split(". ", 1)[1] if ". " in stripped else stripped
                current_items = []
            elif stripped.startswith("- ") and current_section:
                current_items.append(stripped[2:].strip())

        # Don't forget last section
        if current_section:
            section_covered, section_items = _analyze_section(
                current_section, current_items, tc_text_blob
            )
            fw_result["sections"].append({
                "section": current_section,
                "items_total": len(current_items),
                "items_covered": section_covered,
                "coverage_pct": round(section_covered / max(len(current_items), 1) * 100),
                "missing_items": [
                    item for item, hit in zip(current_items, _item_hits(current_items, tc_text_blob))
                    if not hit
                ],
            })
            total_sections += 1
            if section_covered > 0:
                covered_sections += 1

        coverage_results.append(fw_result)

    return {
        "status": "ok",
        "total_test_cases": len(test_cases) if test_cases else 0,
        "frameworks_checked": len(frameworks),
        "total_sections": total_sections,
        "sections_with_coverage": covered_sections,
        "overall_coverage_pct": round(covered_sections / max(total_sections, 1) * 100),
        "coverage": coverage_results,
    }


def _item_hits(items: list, tc_text: str) -> list:
    """Return list of booleans — True if item keywords appear in test case text."""
    hits = []
    for item in items:
        # Extract key terms (3+ char words) from item
        keywords = [w.lower() for w in item.split() if len(w) >= 3]
        # Require at least 40% of keywords to match
        if not keywords:
            hits.append(False)
            continue
        matched = sum(1 for kw in keywords if kw in tc_text)
        hits.append(matched / len(keywords) >= 0.4)
    return hits


def _analyze_section(section: str, items: list, tc_text: str) -> tuple:
    """Count how many items in a section are covered by test cases."""
    if not items:
        # Check section title itself
        keywords = [w.lower() for w in section.split() if len(w) >= 3]
        if keywords and any(kw in tc_text for kw in keywords):
            return (1, [])
        return (0, [])

    hits = _item_hits(items, tc_text)
    return (sum(hits), items)
