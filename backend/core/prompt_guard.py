"""
QAForge -- Prompt Injection Guard
===================================
Detects common prompt injection patterns in user input before sending
to the LLM. Used by QA agents to sanitize descriptions, context, and
any user-supplied text that gets embedded into prompts.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_INJECTION_PATTERNS = [
    (
        "system_override",
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
            re.I,
        ),
    ),
    (
        "role_hijack",
        re.compile(r"you\s+are\s+now\s+(a|an|my)\s+", re.I),
    ),
    (
        "prompt_leak",
        re.compile(
            r"(show|reveal|print|output|repeat)\s+(your|the|system)\s+(prompt|instructions|rules)",
            re.I,
        ),
    ),
    (
        "jailbreak_dan",
        re.compile(r"\bDAN\b.*\b(do\s+anything\s+now|jailbreak)", re.I),
    ),
    (
        "token_smuggle",
        re.compile(r"<\|?(system|im_start|im_end|endoftext)\|?>", re.I),
    ),
    (
        "base64_inject",
        re.compile(r"base64[:\s]+(decode|eval|execute)", re.I),
    ),
    (
        "markdown_inject",
        re.compile(r"!\[.*?\]\(https?://", re.I),
    ),
    (
        "context_reset",
        re.compile(r"(forget|disregard|reset)\s+(everything|all|context)", re.I),
    ),
    (
        "sudo_mode",
        re.compile(r"(sudo|admin|root)\s+mode", re.I),
    ),
    (
        "instruction_inject",
        re.compile(
            r"(new\s+instructions?|updated?\s+prompt|override\s+system)", re.I
        ),
    ),
    (
        "delimiter_attack",
        re.compile(r"(```|---|\*\*\*)\s*(system|instructions|prompt)", re.I),
    ),
    (
        "persona_switch",
        re.compile(r"(act\s+as|pretend\s+to\s+be|roleplay\s+as)\s+", re.I),
    ),
    (
        "encoding_bypass",
        re.compile(
            r"(hex|octal|unicode|rot13)\s*(encode|decode|convert)", re.I
        ),
    ),
]


def check_injection(text: str) -> Optional[str]:
    """
    Scan text for prompt injection patterns.

    Args:
        text: The input text to scan.

    Returns:
        The matched pattern name if injection detected, None otherwise.
    """
    if not text:
        return None
    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning("Prompt injection detected: pattern=%s", name)
            return name
    return None


def is_safe(text: str) -> bool:
    """
    Returns True if the text passes all injection checks.

    Args:
        text: The input text to validate.

    Returns:
        True if no injection patterns are found.
    """
    return check_injection(text) is None


def sanitize_for_prompt(text: str, max_length: int = 10000) -> str:
    """
    Sanitize user input before embedding it in an LLM prompt.
    Truncates to max_length and checks for injection.

    Args:
        text: Raw user input.
        max_length: Maximum allowed character length.

    Returns:
        Sanitized text.

    Raises:
        ValueError: If prompt injection is detected.
    """
    if not text:
        return ""
    truncated = text[:max_length]
    pattern_name = check_injection(truncated)
    if pattern_name:
        raise ValueError(
            f"Prompt injection detected (pattern: {pattern_name}). "
            "Input has been rejected."
        )
    return truncated
