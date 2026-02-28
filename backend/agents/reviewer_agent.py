"""
QAForge -- Reviewer Agent
===========================
Reviews generated test cases against requirements for coverage, quality,
duplicates, and gaps. Uses LLM analysis to produce a structured review report.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from core.llm_provider import LLMProvider, LLMResponse, get_llm_provider
from core.prompt_guard import sanitize_for_prompt
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Review report schema
# ---------------------------------------------------------------------------
REVIEW_REPORT_FIELDS = [
    "coverage_score",   # int 0-100
    "gaps",             # list[str] — requirements not covered
    "duplicates",       # list[{tc_ids: list[str], reason: str}]
    "quality_issues",   # list[{tc_id: str, issue: str}]
    "suggestions",      # list[str] — additional test cases to add
]

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_REVIEWER_SYSTEM_PROMPT = """\
You are QAForge Reviewer, an expert QA review engine.
Your job is to analyse a set of generated test cases against requirements
and produce a structured review report.

RULES:
1. Return ONLY a JSON object (no markdown fences, no commentary).
2. The JSON object must have these exact keys:
   - coverage_score   (integer, 0 to 100, where 100 = full coverage)
   - gaps             (array of strings: requirements or scenarios NOT covered)
   - duplicates       (array of objects: {tc_ids: [string], reason: string})
   - quality_issues   (array of objects: {tc_id: string, issue: string})
   - suggestions      (array of strings: additional test cases that should be added)
3. Be thorough and critical but fair.
4. A coverage_score of 100 means every stated requirement has at least one test case.
5. Flag test cases that are vague, missing expected results, or have unclear steps.
6. Identify test cases with significantly overlapping scenarios as duplicates.
"""

_REVIEWER_USER_PROMPT = """\
Review the following test cases against the requirements.

=== REQUIREMENTS ===
{requirements}

=== TEST CASES ===
{test_cases_json}

{additional_context}

Provide the review report as a JSON object now.
"""


class ReviewReport:
    """Structured review report returned by the ReviewerAgent."""

    def __init__(
        self,
        coverage_score: int = 0,
        gaps: Optional[List[str]] = None,
        duplicates: Optional[List[Dict[str, Any]]] = None,
        quality_issues: Optional[List[Dict[str, Any]]] = None,
        suggestions: Optional[List[str]] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        self.coverage_score = coverage_score
        self.gaps = gaps or []
        self.duplicates = duplicates or []
        self.quality_issues = quality_issues or []
        self.suggestions = suggestions or []
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "coverage_score": self.coverage_score,
            "gaps": self.gaps,
            "duplicates": self.duplicates,
            "quality_issues": self.quality_issues,
            "suggestions": self.suggestions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], **kwargs: Any) -> "ReviewReport":
        """Construct from a parsed dict (e.g. from LLM response)."""
        return cls(
            coverage_score=int(data.get("coverage_score", 0)),
            gaps=data.get("gaps", []),
            duplicates=data.get("duplicates", []),
            quality_issues=data.get("quality_issues", []),
            suggestions=data.get("suggestions", []),
            **kwargs,
        )

    @property
    def is_passing(self) -> bool:
        """True if coverage is above 70 and no critical quality issues."""
        return self.coverage_score >= 70 and len(self.quality_issues) == 0

    def __repr__(self) -> str:
        return (
            f"ReviewReport(score={self.coverage_score}, "
            f"gaps={len(self.gaps)}, duplicates={len(self.duplicates)}, "
            f"quality_issues={len(self.quality_issues)}, "
            f"suggestions={len(self.suggestions)})"
        )


class ReviewerAgent:
    """
    Reviews generated test cases against a set of requirements.

    Usage::

        reviewer = ReviewerAgent()
        report = reviewer.review(
            test_cases=[...],
            requirements=["Req 1: ...", "Req 2: ..."],
        )
        print(report.coverage_score)
        print(report.gaps)
    """

    DEFAULT_MAX_TOKENS: int = 2048
    DEFAULT_TEMPERATURE: float = 0.3

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self._provider = provider

    @property
    def provider(self) -> LLMProvider:
        """Lazy-initialise provider on first access."""
        if self._provider is None:
            self._provider = get_llm_provider()
        return self._provider

    def review(
        self,
        test_cases: List[Dict[str, Any]],
        requirements: List[str],
        additional_context: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> ReviewReport:
        """
        Review test cases against requirements and return a structured report.

        Args:
            test_cases: The generated test cases to review.
            requirements: List of requirement strings to check coverage against.
            additional_context: Optional extra context for the reviewer.
            config: Optional overrides (max_tokens, temperature, model).

        Returns:
            A ReviewReport instance.
        """
        config = config or {}

        if not test_cases:
            logger.warning("ReviewerAgent called with empty test_cases list.")
            return ReviewReport(
                coverage_score=0,
                gaps=requirements[:],
                suggestions=["Generate test cases first before requesting a review."],
            )

        if not requirements:
            logger.warning("ReviewerAgent called with empty requirements list.")
            return ReviewReport(
                coverage_score=100,
                suggestions=["Provide requirements for meaningful coverage analysis."],
            )

        # Sanitize
        sanitized_reqs = [
            sanitize_for_prompt(r, max_length=2000) for r in requirements
        ]
        sanitized_ctx = sanitize_for_prompt(additional_context, max_length=3000)

        # Build prompt
        requirements_text = "\n".join(
            f"  {i+1}. {r}" for i, r in enumerate(sanitized_reqs)
        )
        tc_json = json.dumps(test_cases, indent=2, ensure_ascii=False)

        # Truncate TC JSON if excessively long
        if len(tc_json) > 15000:
            tc_json = tc_json[:15000] + "\n... (truncated for review)"

        additional_section = ""
        if sanitized_ctx:
            additional_section = f"=== ADDITIONAL CONTEXT ===\n{sanitized_ctx}"

        prompt = _REVIEWER_USER_PROMPT.format(
            requirements=requirements_text,
            test_cases_json=tc_json,
            additional_context=additional_section,
        )

        # Call LLM
        provider_config = {
            k: v for k, v in config.items()
            if k in ("max_tokens", "temperature", "model")
        }
        provider_config.setdefault("max_tokens", self.DEFAULT_MAX_TOKENS)
        provider_config.setdefault("temperature", self.DEFAULT_TEMPERATURE)

        response = self._call_llm(prompt, provider_config)

        # Parse the report
        report = self._parse_review(response)
        report.tokens_in = response.tokens_in
        report.tokens_out = response.tokens_out

        logger.info(
            "ReviewerAgent complete: score=%d, gaps=%d, duplicates=%d, "
            "quality_issues=%d, suggestions=%d | tokens_in=%d tokens_out=%d",
            report.coverage_score,
            len(report.gaps),
            len(report.duplicates),
            len(report.quality_issues),
            len(report.suggestions),
            report.tokens_in,
            report.tokens_out,
        )
        return report

    def _call_llm(
        self, prompt: str, provider_config: Dict[str, Any]
    ) -> LLMResponse:
        """Call the LLM with retry logic."""
        max_tokens = provider_config.get("max_tokens", self.DEFAULT_MAX_TOKENS)
        temperature = provider_config.get("temperature", self.DEFAULT_TEMPERATURE)
        model = provider_config.get("model")

        kwargs: Dict[str, Any] = {}
        if model:
            kwargs["model"] = model

        def _do_call() -> LLMResponse:
            return self.provider.complete(
                system=_REVIEWER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

        return retry_with_backoff(_do_call, max_retries=2, base_delay=1.5)

    def _parse_review(self, response: LLMResponse) -> ReviewReport:
        """Parse the LLM response into a ReviewReport."""
        text = response.text.strip()

        # Strip markdown fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
            text = text.strip()

        # Find JSON object
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            text = text[brace_start : brace_end + 1]

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Try fixing trailing commas
            cleaned = re.sub(r",\s*([}\]])", r"\1", text)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse reviewer response: %s", exc)
                logger.debug("Raw reviewer response:\n%s", response.text[:500])
                return ReviewReport(
                    coverage_score=0,
                    quality_issues=[
                        {"tc_id": "SYSTEM", "issue": "Review parsing failed"}
                    ],
                    suggestions=["Re-run the review -- LLM returned unparseable output."],
                )

        return ReviewReport.from_dict(parsed)
