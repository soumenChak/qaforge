"""
QAForge -- Execution Templates.

Each template exposes an async `execute(params, connection_config)` function
that returns a standardised result dict.

Template types:
  - API:    api_smoke (single HTTP call), api_crud (CRUD lifecycle)
  - SQL:    db_query (single query + assertions), db_reconciliation (source-vs-target ETL validation)
  - UI:     ui_playwright (browser-based Playwright tests)
  - MDM:    mdm_entity (Reltio/Semarchy entity CRUD + match/merge)
  - DQ:     data_quality (null, uniqueness, referential integrity, range, format, freshness, row count)
  - ETL:    etl_pipeline (source-target row count, schema, transformation, dedup validation)
  - LLM:    llm_evaluation (prompt testing, latency, hallucination, guardrails)
  - Agent:  agent_workflow (multi-step AI agent conversation testing)
"""

from execution.templates.api_smoke import execute as execute_api_smoke  # noqa: F401
from execution.templates.api_crud import execute as execute_api_crud  # noqa: F401
from execution.templates.db_query import execute as execute_db_query  # noqa: F401
from execution.templates.db_reconciliation import execute as execute_db_reconciliation  # noqa: F401
from execution.templates.ui_playwright import execute as execute_ui_playwright  # noqa: F401
from execution.templates.mdm_entity import execute as execute_mdm_entity  # noqa: F401
from execution.templates.data_quality import execute as execute_data_quality  # noqa: F401
from execution.templates.etl_pipeline import execute as execute_etl_pipeline  # noqa: F401
from execution.templates.llm_evaluation import execute as execute_llm_evaluation  # noqa: F401
from execution.templates.agent_workflow import execute as execute_agent_workflow  # noqa: F401

TEMPLATE_REGISTRY = {
    # API templates
    "api_smoke": execute_api_smoke,
    "api_crud": execute_api_crud,
    # SQL / Database templates
    "db_query": execute_db_query,
    "db_reconciliation": execute_db_reconciliation,
    # UI / Playwright templates
    "ui_playwright": execute_ui_playwright,
    # MDM templates
    "mdm_entity": execute_mdm_entity,
    # Data Quality templates
    "data_quality": execute_data_quality,
    # ETL / Pipeline templates
    "etl_pipeline": execute_etl_pipeline,
    # LLM / GenAI templates
    "llm_evaluation": execute_llm_evaluation,
    # AI Agent templates
    "agent_workflow": execute_agent_workflow,
}
