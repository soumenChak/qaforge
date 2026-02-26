"""
QAForge -- Execution Templates.

Each template exposes an async `execute(params, connection_config)` function
that returns a standardised result dict.

Template types:
  - API:    api_smoke (single HTTP call), api_crud (CRUD lifecycle)
  - SQL:    db_query (single query + assertions), db_reconciliation (source-vs-target ETL validation)
  - UI:     ui_playwright (browser-based Playwright tests)
"""

from execution.templates.api_smoke import execute as execute_api_smoke  # noqa: F401
from execution.templates.api_crud import execute as execute_api_crud  # noqa: F401
from execution.templates.db_query import execute as execute_db_query  # noqa: F401
from execution.templates.db_reconciliation import execute as execute_db_reconciliation  # noqa: F401
from execution.templates.ui_playwright import execute as execute_ui_playwright  # noqa: F401

TEMPLATE_REGISTRY = {
    # API templates
    "api_smoke": execute_api_smoke,
    "api_crud": execute_api_crud,
    # SQL / Database templates
    "db_query": execute_db_query,
    "db_reconciliation": execute_db_reconciliation,
    # UI / Playwright templates
    "ui_playwright": execute_ui_playwright,
}
