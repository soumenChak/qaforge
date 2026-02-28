"""
QAForge Agents
===============
Domain-specific QA agents for test-case generation and review.

Available agents:
  - BaseQAAgent:    Abstract base class
  - MDMAgent:       Master Data Management (Reltio, Semarchy)
  - APIAgent:       REST API / HTTP service testing
  - UIAgent:        Browser-based UI testing (Playwright)
  - ReviewerAgent:  Test case review and coverage analysis
"""

import logging

from .base_qa_agent import BaseQAAgent, TEST_CASE_FIELDS
from .mdm_agent import MDMAgent
from .api_agent import APIAgent
from .ui_agent import UIAgent
from .reviewer_agent import ReviewerAgent, ReviewReport

logger = logging.getLogger(__name__)

# Registry: domain name -> agent class
DOMAIN_AGENTS = {
    "mdm": MDMAgent,
    "api": APIAgent,
    "ui": UIAgent,
    # Aliases for common domain names used in the frontend
    "digital": APIAgent,        # Digital/web apps → API testing by default
    "data_engineering": APIAgent,  # Data eng APIs
    "cloud_devops": APIAgent,   # Cloud/DevOps APIs
    "integration": APIAgent,    # Integration APIs
}

# Sub-domain aliases for convenience
SUB_DOMAIN_ALIASES = {
    "reltio": ("mdm", "reltio"),
    "semarchy": ("mdm", "semarchy"),
    "fastapi": ("api", "fastapi"),
    "react": ("ui", "react"),
    "angular": ("ui", "generic"),
    "playwright": ("ui", "generic"),
}


def get_agent_for_domain(
    domain: str, sub_domain: str = "", **kwargs
) -> BaseQAAgent:
    """
    Factory: return the appropriate agent for a given domain.

    Args:
        domain: Top-level domain (e.g. "mdm", "api", "ui").
        sub_domain: Optional sub-domain (e.g. "reltio", "fastapi", "react").
        **kwargs: Forwarded to the agent constructor.

    Returns:
        An instantiated domain agent. Falls back to APIAgent for unknown
        domains (instead of raising ValueError) since API testing is the
        most common and generic testing pattern.
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
        # Graceful fallback to APIAgent for unknown domains
        logger.warning(
            "Unknown domain '%s' — falling back to APIAgent. "
            "Available domains: %s",
            domain, ", ".join(sorted(DOMAIN_AGENTS.keys())),
        )
        agent_cls = APIAgent

    # Pass sub_domain if the agent supports it
    if sub_domain:
        return agent_cls(sub_domain=sub_domain, **kwargs)
    return agent_cls(**kwargs)


__all__ = [
    "BaseQAAgent",
    "TEST_CASE_FIELDS",
    "MDMAgent",
    "APIAgent",
    "UIAgent",
    "ReviewerAgent",
    "ReviewReport",
    "DOMAIN_AGENTS",
    "get_agent_for_domain",
]
