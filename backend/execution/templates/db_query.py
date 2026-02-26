"""
QAForge -- Database Query Test Template.

Executes SQL queries against a database connection and validates:
  1. Query executes successfully
  2. Row count matches expected
  3. Expected columns exist in results
  4. Value assertions (specific field = expected value)
  5. Data quality checks (null counts, distinct counts)

LLM-extracted params schema:
{
  "query": "SELECT * FROM users WHERE status = 'active'",
  "expected_row_count": 10,
  "row_count_operator": "gte",
  "expected_columns": ["id", "name", "email", "status"],
  "value_assertions": [
    {"column": "status", "row": 0, "expected": "active", "operator": "eq"}
  ],
  "null_check_columns": ["id", "email"],
  "max_query_time_ms": 5000
}
"""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Row count comparison operators
_OPERATORS = {
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
}


async def execute(
    params: Dict[str, Any],
    connection_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run a SQL query test against a database.

    Args:
        params: LLM-extracted test parameters.
        connection_config: Connection profile config (db_url, db_type, etc.).

    Returns:
        Standardised result dict with passed, assertions, logs, details.
    """
    db_url = connection_config.get("db_url") or connection_config.get("database_url") or ""
    db_type = connection_config.get("db_type", "postgresql")

    query = params.get("query", "")
    expected_row_count = params.get("expected_row_count")
    row_count_operator = params.get("row_count_operator", "eq")
    expected_columns: List[str] = params.get("expected_columns") or []
    value_assertions: List[Dict] = params.get("value_assertions") or []
    null_check_columns: List[str] = params.get("null_check_columns") or []
    max_query_time_ms = params.get("max_query_time_ms", 10000)

    assertions: List[Dict[str, Any]] = []
    logs: List[str] = []
    passed = True
    rows = []
    columns = []
    row_count = 0
    latency_ms = 0.0
    response_preview = None

    if not query:
        return {
            "passed": False,
            "assertions": [{"type": "query_provided", "expected": "non-empty", "actual": "empty", "passed": False}],
            "logs": ["No SQL query provided"],
            "details": {},
        }

    if not db_url:
        return {
            "passed": False,
            "assertions": [{"type": "connection", "expected": "db_url configured", "actual": "missing", "passed": False}],
            "logs": ["No database URL configured in connection"],
            "details": {},
        }

    logs.append(f"Executing SQL ({db_type})")
    logs.append(f"  Query: {query[:200]}{'...' if len(query) > 200 else ''}")

    try:
        import sqlalchemy
        from sqlalchemy import create_engine, text

        engine = create_engine(db_url, pool_pre_ping=True)

        start = time.perf_counter()
        with engine.connect() as conn:
            result = conn.execute(text(query))
            latency_ms = (time.perf_counter() - start) * 1000

            # Fetch results for SELECT-type queries
            if result.returns_rows:
                columns = list(result.keys())
                rows = [dict(row._mapping) for row in result.fetchall()]
                row_count = len(rows)
                # Preview first 5 rows
                preview_rows = rows[:5]
                response_preview = str(preview_rows)[:500]
            else:
                row_count = result.rowcount
                logs.append(f"  Non-SELECT query: {row_count} rows affected")

        engine.dispose()
        logs.append(f"  Result: {row_count} rows ({latency_ms:.0f}ms)")

        # -- Assertion 1: Query execution success --
        assertions.append({
            "type": "query_execution",
            "expected": "success",
            "actual": "success",
            "passed": True,
        })

        # -- Assertion 2: Row count --
        if expected_row_count is not None:
            op_fn = _OPERATORS.get(row_count_operator, _OPERATORS["eq"])
            count_ok = op_fn(row_count, expected_row_count)
            assertions.append({
                "type": "row_count",
                "operator": row_count_operator,
                "expected": expected_row_count,
                "actual": row_count,
                "passed": count_ok,
            })
            if not count_ok:
                passed = False
                logs.append(f"  FAIL: Expected row count {row_count_operator} {expected_row_count}, got {row_count}")

        # -- Assertion 3: Expected columns --
        if expected_columns and columns:
            for col in expected_columns:
                col_exists = col.lower() in [c.lower() for c in columns]
                assertions.append({
                    "type": "column_exists",
                    "column": col,
                    "passed": col_exists,
                })
                if not col_exists:
                    passed = False
                    logs.append(f"  FAIL: Expected column '{col}' not in result columns: {columns}")

        # -- Assertion 4: Value assertions --
        for va in value_assertions:
            col_name = va.get("column", "")
            row_idx = va.get("row", 0)
            expected_val = va.get("expected")
            operator = va.get("operator", "eq")

            if row_idx < len(rows) and col_name in rows[row_idx]:
                actual_val = rows[row_idx][col_name]
                # Convert for comparison
                actual_str = str(actual_val) if actual_val is not None else None
                expected_str = str(expected_val) if expected_val is not None else None
                val_ok = actual_str == expected_str if operator == "eq" else actual_str != expected_str
                assertions.append({
                    "type": "value_check",
                    "column": col_name,
                    "row": row_idx,
                    "expected": expected_val,
                    "actual": actual_val,
                    "operator": operator,
                    "passed": val_ok,
                })
                if not val_ok:
                    passed = False
                    logs.append(f"  FAIL: Row {row_idx} column '{col_name}' expected {operator} '{expected_val}', got '{actual_val}'")
            else:
                assertions.append({
                    "type": "value_check",
                    "column": col_name,
                    "row": row_idx,
                    "expected": expected_val,
                    "actual": "N/A (row/column not found)",
                    "passed": False,
                })
                passed = False
                logs.append(f"  FAIL: Cannot check row {row_idx} column '{col_name}' — not found in results")

        # -- Assertion 5: Null checks --
        if null_check_columns and rows:
            for col in null_check_columns:
                null_count = sum(1 for row in rows if row.get(col) is None)
                no_nulls = null_count == 0
                assertions.append({
                    "type": "null_check",
                    "column": col,
                    "null_count": null_count,
                    "total_rows": row_count,
                    "passed": no_nulls,
                })
                if not no_nulls:
                    passed = False
                    logs.append(f"  FAIL: Column '{col}' has {null_count} NULL values out of {row_count} rows")

        # -- Assertion 6: Query time --
        time_ok = latency_ms <= max_query_time_ms
        assertions.append({
            "type": "query_time",
            "max_ms": max_query_time_ms,
            "actual_ms": round(latency_ms, 1),
            "passed": time_ok,
        })
        if not time_ok:
            passed = False
            logs.append(f"  FAIL: Query took {latency_ms:.0f}ms (max: {max_query_time_ms}ms)")

    except ImportError:
        passed = False
        logs.append("sqlalchemy not available — cannot execute SQL tests")
        assertions.append({"type": "dependency", "expected": "sqlalchemy", "actual": "missing", "passed": False})
    except Exception as exc:
        passed = False
        logs.append(f"Query execution error: {type(exc).__name__}: {exc}")
        assertions.append({
            "type": "query_execution",
            "expected": "success",
            "actual": str(exc)[:200],
            "passed": False,
        })

    return {
        "passed": passed,
        "assertions": assertions,
        "logs": logs,
        "details": {
            "template": "db_query",
            "db_type": db_type,
            "query": query[:500],
            "row_count": row_count,
            "columns": columns,
            "latency_ms": round(latency_ms, 1),
            "response_preview": response_preview,
        },
    }
