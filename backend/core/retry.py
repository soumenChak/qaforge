"""
QAForge -- Exponential Backoff Retry Helper
=============================================
Provides both synchronous and asynchronous retry logic with exponential
backoff, jitter, and fast-fail on client errors (4xx).
"""

from __future__ import annotations

import asyncio
import random
import time
import logging
from typing import TypeVar, Callable, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    fast_fail_on_4xx: bool = True,
    **kwargs: Any,
) -> T:
    """
    Call *fn* with exponential backoff on failure.

    Args:
        fn: The callable to execute.
        *args: Positional arguments forwarded to *fn*.
        max_retries: Number of retry attempts (total calls = max_retries + 1).
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum cap on delay between retries.
        fast_fail_on_4xx: If True, immediately re-raise on 4xx HTTP errors.
        **kwargs: Keyword arguments forwarded to *fn*.

    Returns:
        The return value of *fn* on success.

    Raises:
        The last exception encountered after all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            # Fast-fail on client errors (4xx)
            if fast_fail_on_4xx:
                status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
                if status and 400 <= int(status) < 500:
                    logger.error("Client error (status=%s), not retrying: %s", status, exc)
                    raise
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                # Add jitter to prevent thundering herd
                delay = delay * (0.5 + random.random() * 0.5)
                logger.warning(
                    "Attempt %d/%d failed: %s -- retrying in %.1fs",
                    attempt + 1, max_retries + 1, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "All %d attempts failed. Last error: %s", max_retries + 1, exc
                )
    raise last_exc  # type: ignore[misc]


async def async_retry_with_backoff(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    fast_fail_on_4xx: bool = True,
    **kwargs: Any,
) -> Any:
    """
    Async version: call *fn* (sync or async) with exponential backoff.

    Args:
        fn: The callable to execute. Can be sync or async.
        *args: Positional arguments forwarded to *fn*.
        max_retries: Number of retry attempts (total calls = max_retries + 1).
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum cap on delay between retries.
        fast_fail_on_4xx: If True, immediately re-raise on 4xx HTTP errors.
        **kwargs: Keyword arguments forwarded to *fn*.

    Returns:
        The return value of *fn* on success.

    Raises:
        The last exception encountered after all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            result = fn(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as exc:
            last_exc = exc
            # Fast-fail on client errors (4xx)
            if fast_fail_on_4xx:
                status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
                if status and 400 <= int(status) < 500:
                    logger.error("Client error (status=%s), not retrying: %s", status, exc)
                    raise
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                delay = delay * (0.5 + random.random() * 0.5)
                logger.warning(
                    "Async attempt %d/%d failed: %s -- retrying in %.1fs",
                    attempt + 1, max_retries + 1, exc, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "All %d async attempts failed. Last error: %s",
                    max_retries + 1, exc,
                )
    raise last_exc  # type: ignore[misc]
