"""
QAForge -- Test Execution Engine Package.

Provides the core orchestrator and pre-built execution templates for
running test cases against external systems.

Templates:
    api_smoke  -- HTTP request → status check → field validation
    api_crud   -- Full CRUD lifecycle (POST → GET → PUT → DELETE)

Fallback:
    sandbox    -- LLM-generated Python executed in a subprocess
"""

from execution.engine import run_execution  # noqa: F401
