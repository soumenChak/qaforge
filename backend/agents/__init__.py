"""
QAForge Agents
===============
Domain-specific QA agents for test-case generation and review.

Available agents:
  - BaseQAAgent:    Abstract base class
  - MDMAgent:       Master Data Management (Reltio, Semarchy)
  - ReviewerAgent:  Test case review and coverage analysis
"""

from .base_qa_agent import BaseQAAgent, TEST_CASE_FIELDS
from .mdm_agent import MDMAgent
from .reviewer_agent import ReviewerAgent, ReviewReport

# Registry: domain name -> agent class
DOMAIN_AGENTS = {
    "mdm": MDMAgent,
}

# Sub-domain aliases for convenience
SUB_DOMAIN_ALIASES = {
    "reltio": ("mdm", "reltio"),
    "semarchy": ("mdm", "semarchy"),
}


def get_agent_for_domain(
    domain: str, sub_domain: str = "", **kwargs
) -> BaseQAAgent:
    """
    Factory: return the appropriate agent for a given domain.

    Args:
        domain: Top-level domain (e.g. "mdm").
        sub_domain: Optional sub-domain (e.g. "reltio", "semarchy").
        **kwargs: Forwarded to the agent constructor.

    Returns:
        An instantiated domain agent.

    Raises:
        ValueError: If the domain is not recognised.
    """
    domain_lower = domain.lower().strip()

    # Check aliases first
    if domain_lower in SUB_DOMAIN_ALIASES:
        resolved_domain, resolved_sub = SUB_DOMAIN_ALIASES[domain_lower]
        domain_lower = resolved_domain
        if not sub_domain:
            sub_domain = resolved_sub

    agent_cls = DOMAIN_AGENTS.get(domain_lower)
    if agent_cls is None:
        available = ", ".join(sorted(DOMAIN_AGENTS.keys()))
        raise ValueError(
            f"Unknown domain '{domain}'. Available domains: {available}"
        )

    # Pass sub_domain if the agent supports it
    if sub_domain:
        return agent_cls(sub_domain=sub_domain, **kwargs)
    return agent_cls(**kwargs)


__all__ = [
    "BaseQAAgent",
    "TEST_CASE_FIELDS",
    "MDMAgent",
    "ReviewerAgent",
    "ReviewReport",
    "DOMAIN_AGENTS",
    "get_agent_for_domain",
]
