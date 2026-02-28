"""
QAForge -- Executable Test Generation
=======================================
Generates directly runnable Python test scripts (pytest + httpx/Playwright)
instead of JSON test case documents. These scripts can be executed without
any parameter extraction or template matching — they ARE the tests.
"""

from .executable_generator import ExecutableGenerator

__all__ = ["ExecutableGenerator"]
