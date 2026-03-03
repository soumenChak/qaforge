"""
QAForge -- Base QA Agent
=========================
Abstract base class that all domain-specific QA agents inherit from.
Provides the common pipeline: build prompt -> call LLM -> parse response ->
format output. Domain agents only need to implement ``generate_test_cases``
and ``get_domain_patterns``.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from core.llm_provider import LLMProvider, LLMResponse, get_llm_provider
from core.prompt_guard import sanitize_for_prompt
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test-case schema reference (each dict returned by agents)
# ---------------------------------------------------------------------------
TEST_CASE_FIELDS = [
    "test_case_id",
    "title",
    "description",
    "preconditions",
    "test_steps",       # list[{step_number, action, expected_result}]
    "expected_result",
    "priority",         # High / Medium / Low
    "category",         # Functional / Negative / Edge Case / Boundary / etc.
    "domain_tags",      # list[str]
]

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are QAForge, an expert QA test-case generation engine.
Your job is to produce high-quality, detailed test cases in JSON format.

RULES:
1. Return ONLY a JSON array (no markdown fences, no commentary).
2. Each element must be an object with these exact keys:
   - test_case_id   (string, e.g. "TC-001")
   - title          (string, concise)
   - description    (string, 1-3 sentences)
   - preconditions  (string, what must be true before the test — list all system access needed)
   - test_steps     (array of step objects — see format below)
   - expected_result (string, overall expected outcome)
   - priority       (string: "High", "Medium", or "Low")
   - category       (string: e.g. "Functional", "Negative", "Edge Case", "Boundary", "Integration", "Performance", "Data Quality", "Migration")
   - domain_tags    (array of strings relevant to the domain)
   - test_data      (optional object: structured metadata like table names, entity types, column mappings)
   - execution_type (optional string: "api", "ui", "sql", "manual", "mdm")
3. TEST STEP FORMAT — each step object MUST have:
   - step_number    (int)
   - action         (string, concrete and actionable)
   - expected_result (string, verifiable outcome for this specific step)
   And OPTIONALLY:
   - step_type      (string: "sql", "snowflake", "databricks", "oracle", "reltio_ui", "reltio_api", "data_validation", "manual")
   - sql_script     (string: actual SQL query to execute — include when step_type is sql/snowflake/databricks/oracle)
   - system         (string: which system this step targets, e.g. "Snowflake", "Reltio", "Databricks", "Oracle")
4. Cover positive, negative, edge-case, and boundary scenarios.
5. Test steps must be concrete, actionable, and verifiable.
6. Assign priorities realistically: not everything is High.
7. Each test case must be independent and self-contained.
8. When the domain involves multiple systems (e.g. Snowflake + Reltio), create multi-step test cases that validate data flow ACROSS systems.
"""

_USER_PROMPT_TEMPLATE = """\
Generate {count} test cases for the following requirement.

=== REQUIREMENT ===
{description}

=== DOMAIN KNOWLEDGE ===
{domain_patterns}

{additional_section}
{examples_section}
Return the JSON array now.
"""


class BaseQAAgent(ABC):
    """
    Abstract base for all QAForge domain agents.

    Subclasses MUST implement:
      - ``generate_test_cases()``
      - ``get_domain_patterns()``
    """

    # Subclasses may override for default token budget
    DEFAULT_MAX_TOKENS: int = 4096
    DEFAULT_TEMPERATURE: float = 0.4

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self._provider = provider

    @property
    def provider(self) -> LLMProvider:
        """Lazy-initialise provider on first access."""
        if self._provider is None:
            self._provider = get_llm_provider()
        return self._provider

    # ------------------------------------------------------------------
    # Abstract methods (domain agents MUST implement)
    # ------------------------------------------------------------------

    @abstractmethod
    def generate_test_cases(
        self,
        description: str,
        context: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate test cases for the given requirement description.

        Args:
            description: The requirement / feature description to test.
            context: Additional context from the knowledge base.
            config: Optional configuration overrides (count, temperature, etc.).

        Returns:
            A list of test-case dicts conforming to TEST_CASE_FIELDS.
        """
        ...

    @abstractmethod
    def get_domain_patterns(self) -> str:
        """
        Return domain-specific knowledge that will be injected into the
        LLM prompt to guide test-case generation.
        """
        ...

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def build_prompt(
        self,
        description: str,
        context: str = "",
        domain_patterns: str = "",
        additional_context: str = "",
        example_test_cases: Optional[List[Dict[str, Any]]] = None,
        count: int = 10,
    ) -> str:
        """
        Construct the full user-prompt string sent to the LLM.

        Args:
            description: Requirement text.
            context: Knowledge-base context.
            domain_patterns: Domain-specific prompt additions.
            additional_context: Any extra user-supplied context.
            example_test_cases: Optional few-shot examples.
            count: Number of test cases to request.

        Returns:
            The fully assembled prompt string.
        """
        # Sanitize all user-supplied text
        description = sanitize_for_prompt(description, max_length=8000)
        context = sanitize_for_prompt(context, max_length=5000)
        additional_context = sanitize_for_prompt(additional_context, max_length=5000)

        # Additional context section
        additional_section = ""
        if context or additional_context:
            parts = []
            if context:
                parts.append(f"Knowledge base context:\n{context}")
            if additional_context:
                parts.append(f"Additional context:\n{additional_context}")
            additional_section = "=== ADDITIONAL CONTEXT ===\n" + "\n\n".join(parts)

        # Examples section
        examples_section = ""
        if example_test_cases:
            examples_section = (
                "=== EXAMPLE TEST CASES (follow this format) ===\n"
                + json.dumps(example_test_cases[:2], indent=2)
            )

        return _USER_PROMPT_TEMPLATE.format(
            count=count,
            description=description,
            domain_patterns=domain_patterns or "No specific domain patterns.",
            additional_section=additional_section,
            examples_section=examples_section,
        )

    def _call_llm(
        self,
        prompt: str,
        provider_config: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """
        Call the LLM via the core provider with retry logic.

        Args:
            prompt: The user-role prompt text.
            provider_config: Optional overrides (max_tokens, temperature, model).

        Returns:
            LLMResponse with text and token counts.
        """
        config = provider_config or {}
        max_tokens = config.get("max_tokens", self.DEFAULT_MAX_TOKENS)
        temperature = config.get("temperature", self.DEFAULT_TEMPERATURE)
        model = config.get("model")

        kwargs: Dict[str, Any] = {}
        if model:
            kwargs["model"] = model

        def _do_call() -> LLMResponse:
            return self.provider.complete(
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

        return retry_with_backoff(_do_call, max_retries=2, base_delay=1.5)

    def _parse_response(self, raw_response: str) -> List[Dict[str, Any]]:
        """
        Parse the raw LLM response text into a list of test-case dicts.

        Handles common LLM quirks: markdown fences, trailing commas,
        partial JSON, etc.

        Args:
            raw_response: The raw text from the LLM.

        Returns:
            A list of test-case dicts. Returns empty list on parse failure.
        """
        text = raw_response.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
            text = text.strip()

        # Try to find JSON array in the text
        bracket_start = text.find("[")
        bracket_end = text.rfind("]")
        if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
            text = text[bracket_start : bracket_end + 1]

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Attempt to fix trailing commas
            cleaned = re.sub(r",\s*([}\]])", r"\1", text)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse LLM response as JSON: %s", exc)
                logger.debug("Raw response:\n%s", raw_response[:500])
                return []

        if not isinstance(parsed, list):
            parsed = [parsed]

        # Validate and normalise each test case
        valid_cases: List[Dict[str, Any]] = []
        for i, tc in enumerate(parsed):
            if not isinstance(tc, dict):
                logger.warning("Skipping non-dict item at index %d", i)
                continue
            normalised = self._normalise_test_case(tc, i + 1)
            valid_cases.append(normalised)

        return valid_cases

    def _normalise_test_case(
        self, tc: Dict[str, Any], index: int
    ) -> Dict[str, Any]:
        """
        Ensure a test case dict has all required fields with sensible defaults.

        Args:
            tc: The raw test-case dict from the LLM.
            index: The 1-based index for generating fallback IDs.

        Returns:
            A normalised test-case dict.
        """
        short_id = uuid.uuid4().hex[:6].upper()
        return {
            "test_case_id": tc.get("test_case_id", f"TC-{index:03d}-{short_id}"),
            "title": tc.get("title", f"Test Case {index}"),
            "description": tc.get("description", ""),
            "preconditions": tc.get("preconditions", "None"),
            "test_steps": self._normalise_steps(tc.get("test_steps", [])),
            "expected_result": tc.get("expected_result", ""),
            "priority": self._normalise_priority(tc.get("priority", "Medium")),
            "category": tc.get("category", "Functional"),
            "domain_tags": tc.get("domain_tags", []),
        }

    @staticmethod
    def _normalise_steps(steps: Any) -> List[Dict[str, Any]]:
        """Normalise test steps into the canonical format.

        Preserves extra fields beyond the canonical three (step_number,
        action, expected_result) so that enterprise test cases can carry
        rich metadata: step_type, sql_script, system, verification_type, etc.
        """
        if not isinstance(steps, list):
            return [{"step_number": 1, "action": str(steps), "expected_result": ""}]
        normalised: List[Dict[str, Any]] = []
        for i, step in enumerate(steps):
            if isinstance(step, dict):
                base = {
                    "step_number": step.get("step_number", i + 1),
                    "action": step.get("action", ""),
                    "expected_result": step.get("expected_result", ""),
                }
                # Preserve extra fields (step_type, sql_script, system, etc.)
                for k, v in step.items():
                    if k not in base:
                        base[k] = v
                normalised.append(base)
            elif isinstance(step, str):
                normalised.append({
                    "step_number": i + 1,
                    "action": step,
                    "expected_result": "",
                })
        return normalised

    @staticmethod
    def _normalise_priority(priority: Any) -> str:
        """Normalise priority to High / Medium / Low.

        Accepts both textual (High/Medium/Low/Critical) and coded (P1-P4)
        formats, since the route-level prompt asks for P1-P4 while the
        base agent schema uses High/Medium/Low.
        """
        if not isinstance(priority, str):
            return "Medium"
        p = priority.strip().upper()
        # Direct match (case-insensitive)
        _MAP = {
            "HIGH": "High", "MEDIUM": "Medium", "LOW": "Low",
            "CRITICAL": "High", "BLOCKER": "High",
            "MINOR": "Low", "TRIVIAL": "Low",
            "P1": "High", "P2": "Medium", "P3": "Low", "P4": "Low",
        }
        return _MAP.get(p, "Medium")

    def format_output(
        self,
        test_cases: List[Dict[str, Any]],
        template: Optional[str] = None,
    ) -> Any:
        """
        Format test cases according to a template name.

        Args:
            test_cases: List of test-case dicts.
            template: Template identifier ("json", "excel", "markdown", or None for raw).

        Returns:
            Formatted output (JSON string, or the raw list if no template).
        """
        if template == "json":
            return json.dumps(test_cases, indent=2, ensure_ascii=False)
        if template == "markdown":
            return self._format_markdown(test_cases)
        # Default: return raw list (caller handles formatting)
        return test_cases

    @staticmethod
    def _format_markdown(test_cases: List[Dict[str, Any]]) -> str:
        """Render test cases as a Markdown document."""
        lines: List[str] = ["# Test Cases\n"]
        for tc in test_cases:
            lines.append(f"## {tc['test_case_id']}: {tc['title']}")
            lines.append(f"**Priority:** {tc['priority']}  ")
            lines.append(f"**Category:** {tc['category']}  ")
            if tc.get("domain_tags"):
                lines.append(f"**Tags:** {', '.join(tc['domain_tags'])}  ")
            lines.append(f"\n**Description:** {tc['description']}\n")
            lines.append(f"**Preconditions:** {tc['preconditions']}\n")
            lines.append("**Steps:**\n")
            for step in tc.get("test_steps", []):
                lines.append(
                    f"  {step['step_number']}. {step['action']}  "
                    f"\n     *Expected:* {step['expected_result']}"
                )
            lines.append(f"\n**Expected Result:** {tc['expected_result']}\n")
            lines.append("---\n")
        return "\n".join(lines)
