"""
QAForge Core
=============
Shared infrastructure: LLM provider abstraction, prompt injection guard,
and retry helpers.
"""

from .llm_provider import (
    LLMProvider,
    LLMResponse,
    get_llm_provider,
    get_provider_by_name,
    list_providers,
)
from .prompt_guard import check_injection, is_safe, sanitize_for_prompt
from .retry import retry_with_backoff, async_retry_with_backoff

__all__ = [
    # LLM
    "LLMProvider",
    "LLMResponse",
    "get_llm_provider",
    "get_provider_by_name",
    "list_providers",
    # Prompt guard
    "check_injection",
    "is_safe",
    "sanitize_for_prompt",
    # Retry
    "retry_with_backoff",
    "async_retry_with_backoff",
]
