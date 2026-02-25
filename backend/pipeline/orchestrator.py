"""
QAForge -- Generation Pipeline Orchestrator
=============================================
The main pipeline that coordinates domain agents, reviewer, refinement,
and output formatting into a single async flow.

Usage::

    from backend.pipeline import Orchestrator, GenerateRequest

    request = GenerateRequest(
        description="Verify match rules for fuzzy name matching in Reltio",
        domain="mdm",
        sub_domain="reltio",
        count=15,
    )
    result = await Orchestrator().run(request)
    print(result.test_cases)
    print(result.review_report)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.agents import get_agent_for_domain, ReviewerAgent, ReviewReport
from backend.agents.base_qa_agent import BaseQAAgent
from backend.core.llm_provider import LLMResponse
from backend.core.retry import async_retry_with_backoff

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

@dataclass
class GenerateRequest:
    """Input to the generation pipeline."""

    description: str
    domain: str = "mdm"
    sub_domain: str = ""
    additional_context: str = ""
    template_id: str = "default"
    count: int = 10

    # Optional overrides
    requirements: Optional[List[str]] = None
    temperature: float = 0.4
    max_tokens: int = 4096
    model: Optional[str] = None
    skip_review: bool = False
    max_refinement_rounds: int = 1
    knowledge_base_context: str = ""
    example_test_cases: Optional[List[Dict[str, Any]]] = None


@dataclass
class GenerateResult:
    """Output from the generation pipeline."""

    test_cases: List[Dict[str, Any]] = field(default_factory=list)
    review_report: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.test_cases)

    @property
    def total_tokens(self) -> int:
        return self.metadata.get("total_tokens_in", 0) + self.metadata.get(
            "total_tokens_out", 0
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """
    Main generation pipeline.

    Steps:
      1. Select the right domain agent based on request.domain
      2. Retrieve context from knowledge base (if available)
      3. Call domain agent to generate test cases
      4. Call reviewer agent to review
      5. Apply refinements based on review (if needed)
      6. Format output according to template
      7. Return test cases + review report + metadata
    """

    def __init__(
        self,
        agent: Optional[BaseQAAgent] = None,
        reviewer: Optional[ReviewerAgent] = None,
    ) -> None:
        """
        Args:
            agent: Override the domain agent (useful for testing).
            reviewer: Override the reviewer agent (useful for testing).
        """
        self._agent_override = agent
        self._reviewer_override = reviewer

    async def run(self, request: GenerateRequest) -> GenerateResult:
        """
        Execute the full generation pipeline.

        Args:
            request: A GenerateRequest describing what to generate.

        Returns:
            A GenerateResult with test cases, review, and metadata.
        """
        start_time = time.monotonic()
        total_tokens_in = 0
        total_tokens_out = 0
        metadata: Dict[str, Any] = {
            "domain": request.domain,
            "sub_domain": request.sub_domain,
            "requested_count": request.count,
            "template_id": request.template_id,
        }

        # --- Step 1: Select domain agent ---
        agent = self._agent_override or self._resolve_agent(request)
        metadata["agent_class"] = agent.__class__.__name__

        # --- Step 2: Gather context ---
        context = self._gather_context(request)

        # --- Step 3: Generate test cases ---
        logger.info(
            "Pipeline: generating %d test cases for domain=%s sub_domain=%s",
            request.count, request.domain, request.sub_domain,
        )

        gen_config: Dict[str, Any] = {
            "count": request.count,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "additional_context": request.additional_context,
        }
        if request.model:
            gen_config["model"] = request.model
        if request.example_test_cases:
            gen_config["example_test_cases"] = request.example_test_cases

        test_cases = await self._async_generate(agent, request.description, context, gen_config)
        metadata["initial_count"] = len(test_cases)

        # Track tokens from generation (estimated -- actual tracking happens in agent)
        # The agent's _call_llm returns LLMResponse, but generate_test_cases
        # returns just the list. We capture via a wrapper pattern below.
        gen_tokens = self._estimate_tokens(request.description, context, test_cases)
        total_tokens_in += gen_tokens["tokens_in"]
        total_tokens_out += gen_tokens["tokens_out"]

        # --- Step 4: Review (optional) ---
        review_report: Optional[ReviewReport] = None

        if not request.skip_review and test_cases:
            requirements = request.requirements or [request.description]
            reviewer = self._reviewer_override or ReviewerAgent()

            logger.info(
                "Pipeline: reviewing %d test cases against %d requirements",
                len(test_cases), len(requirements),
            )

            review_report = await self._async_review(
                reviewer, test_cases, requirements, request.additional_context,
                {
                    "temperature": request.temperature,
                    "model": request.model,
                },
            )
            total_tokens_in += review_report.tokens_in
            total_tokens_out += review_report.tokens_out

            # --- Step 5: Refinement ---
            if (
                review_report
                and not review_report.is_passing
                and request.max_refinement_rounds > 0
            ):
                test_cases, refinement_tokens = await self._refine(
                    agent=agent,
                    test_cases=test_cases,
                    review_report=review_report,
                    request=request,
                    context=context,
                )
                total_tokens_in += refinement_tokens["tokens_in"]
                total_tokens_out += refinement_tokens["tokens_out"]
                metadata["refined"] = True

        # --- Step 6: Finalise metadata ---
        elapsed = time.monotonic() - start_time
        metadata.update({
            "final_count": len(test_cases),
            "duration_seconds": round(elapsed, 2),
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_tokens": total_tokens_in + total_tokens_out,
        })

        logger.info(
            "Pipeline complete: %d test cases in %.1fs (tokens: %d in + %d out = %d)",
            len(test_cases), elapsed, total_tokens_in, total_tokens_out,
            total_tokens_in + total_tokens_out,
        )

        return GenerateResult(
            test_cases=test_cases,
            review_report=review_report.to_dict() if review_report else None,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_agent(self, request: GenerateRequest) -> BaseQAAgent:
        """Resolve the domain agent from the request."""
        return get_agent_for_domain(
            domain=request.domain,
            sub_domain=request.sub_domain,
        )

    def _gather_context(self, request: GenerateRequest) -> str:
        """
        Gather context from the knowledge base and any additional sources.
        Returns a combined context string.
        """
        parts: List[str] = []
        if request.knowledge_base_context:
            parts.append(request.knowledge_base_context)
        # Future: query a vector store, RAG pipeline, etc.
        return "\n\n".join(parts)

    async def _async_generate(
        self,
        agent: BaseQAAgent,
        description: str,
        context: str,
        config: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Run the agent's generate_test_cases in a thread (it's sync/blocking)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, agent.generate_test_cases, description, context, config
        )

    async def _async_review(
        self,
        reviewer: ReviewerAgent,
        test_cases: List[Dict[str, Any]],
        requirements: List[str],
        additional_context: str,
        config: Dict[str, Any],
    ) -> ReviewReport:
        """Run the reviewer in a thread (it's sync/blocking)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            reviewer.review,
            test_cases,
            requirements,
            additional_context,
            config,
        )

    async def _refine(
        self,
        agent: BaseQAAgent,
        test_cases: List[Dict[str, Any]],
        review_report: ReviewReport,
        request: GenerateRequest,
        context: str,
    ) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Refine test cases based on review feedback.

        Strategy:
          - If there are gaps, generate additional test cases targeting gaps.
          - If there are duplicates, remove them.
          - If there are quality issues, leave them (flagged for human review).

        Returns:
            Tuple of (refined_test_cases, token_counts_dict).
        """
        tokens_in = 0
        tokens_out = 0
        refined = list(test_cases)

        # Remove duplicates (keep the first in each group)
        if review_report.duplicates:
            ids_to_remove: set[str] = set()
            for dup_group in review_report.duplicates:
                dup_ids = dup_group.get("tc_ids", [])
                if len(dup_ids) > 1:
                    # Keep the first, remove the rest
                    ids_to_remove.update(dup_ids[1:])
            if ids_to_remove:
                before = len(refined)
                refined = [
                    tc for tc in refined
                    if tc.get("test_case_id") not in ids_to_remove
                ]
                logger.info(
                    "Refinement: removed %d duplicate test cases",
                    before - len(refined),
                )

        # Generate additional test cases for gaps
        if review_report.gaps:
            gap_description = (
                f"Generate additional test cases to cover these gaps:\n"
                + "\n".join(f"  - {gap}" for gap in review_report.gaps)
                + f"\n\nOriginal requirement: {request.description}"
            )
            gap_config: Dict[str, Any] = {
                "count": min(len(review_report.gaps) * 2, 10),
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "additional_context": request.additional_context,
            }
            if request.model:
                gap_config["model"] = request.model

            logger.info(
                "Refinement: generating %d additional test cases for %d gaps",
                gap_config["count"], len(review_report.gaps),
            )

            additional = await self._async_generate(
                agent, gap_description, context, gap_config,
            )

            gap_tokens = self._estimate_tokens(gap_description, context, additional)
            tokens_in += gap_tokens["tokens_in"]
            tokens_out += gap_tokens["tokens_out"]

            # Re-number IDs to avoid collisions
            existing_ids = {tc.get("test_case_id") for tc in refined}
            for tc in additional:
                while tc.get("test_case_id") in existing_ids:
                    tc["test_case_id"] = tc["test_case_id"] + "-R"
                existing_ids.add(tc["test_case_id"])
            refined.extend(additional)

        return refined, {"tokens_in": tokens_in, "tokens_out": tokens_out}

    @staticmethod
    def _estimate_tokens(
        description: str, context: str, test_cases: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Rough token estimation when exact counts aren't available from the agent.
        Uses ~4 chars per token heuristic.
        """
        import json as _json
        input_chars = len(description) + len(context)
        output_chars = len(_json.dumps(test_cases, ensure_ascii=False))
        return {
            "tokens_in": max(input_chars // 4, 1),
            "tokens_out": max(output_chars // 4, 1),
        }
