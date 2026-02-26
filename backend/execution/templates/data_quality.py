"""
QAForge -- Data Quality Checks Template.

Runs data quality validations against a database table:
  1. Null check: verify required columns have no nulls
  2. Uniqueness check: verify unique columns have no duplicates
  3. Referential integrity: verify FK relationships exist
  4. Range/format validation: verify values in expected ranges
  5. Freshness check: verify latest data is within expected window
  6. Row count check: verify table has expected number of rows

LLM-extracted params schema:
{
  "table_name": "public.customers",
  "checks": [
    {"type": "null_check", "columns": ["id", "email", "name"]},
    {"type": "uniqueness", "columns": ["email"]},
    {"type": "referential_integrity", "column": "order_id", "ref_table": "public.orders", "ref_column": "id"},
    {"type": "range", "column": "age", "min": 0, "max": 150},
    {"type": "format", "column": "email", "pattern": "^[^@]+@[^@]+\\.[^@]+$"},
    {"type": "freshness", "column": "updated_at", "max_age_hours": 24},
    {"type": "row_count", "expected": 1000, "operator": "gte"}
  ],
  "max_query_time_ms": 30000
}
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

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
    Run data quality checks against a database table.

    Args:
        params: LLM-extracted test parameters.
        connection_config: Connection profile config (db_url, db_type, etc.).

    Returns:
        Standardised result dict with passed, assertions, logs, details.
    """
    db_url = connection_config.get("db_url") or connection_config.get("database_url") or ""
    db_type = connection_config.get("db_type", "postgresql")

    table_name = params.get("table_name", "")
    checks: List[Dict[str, Any]] = params.get("checks") or []
    max_query_time_ms = params.get("max_query_time_ms", 30000)

    assertions: List[Dict[str, Any]] = []
    logs: List[str] = []
    passed = True
    total_start = time.perf_counter()
    check_results: Dict[str, Any] = {}

    if not table_name:
        return {
            "passed": False,
            "assertions": [{"type": "table_provided", "expected": "non-empty", "actual": "empty", "passed": False}],
            "logs": ["No table_name provided"],
            "details": {},
        }

    if not db_url:
        return {
            "passed": False,
            "assertions": [{"type": "connection", "expected": "db_url configured", "actual": "missing", "passed": False}],
            "logs": ["No database URL configured in connection"],
            "details": {},
        }

    if not checks:
        return {
            "passed": False,
            "assertions": [{"type": "checks_provided", "expected": "non-empty", "actual": "empty", "passed": False}],
            "logs": ["No checks provided — nothing to validate"],
            "details": {},
        }

    logs.append(f"Running data quality checks on {table_name} ({db_type})")
    logs.append(f"  Checks to run: {len(checks)}")

    try:
        import sqlalchemy
        from sqlalchemy import create_engine, text

        engine = create_engine(db_url, pool_pre_ping=True)

        for i, check in enumerate(checks):
            check_type = check.get("type", "unknown")
            check_label = f"[Check {i + 1}/{len(checks)}] {check_type}"

            try:
                if check_type == "null_check":
                    _ok = _run_null_check(engine, text, table_name, check, assertions, logs, check_label)
                    if not _ok:
                        passed = False

                elif check_type == "uniqueness":
                    _ok = _run_uniqueness_check(engine, text, table_name, check, assertions, logs, check_label)
                    if not _ok:
                        passed = False

                elif check_type == "referential_integrity":
                    _ok = _run_referential_integrity(engine, text, table_name, check, assertions, logs, check_label)
                    if not _ok:
                        passed = False

                elif check_type == "range":
                    _ok = _run_range_check(engine, text, table_name, check, assertions, logs, check_label)
                    if not _ok:
                        passed = False

                elif check_type == "format":
                    _ok = _run_format_check(engine, text, table_name, check, assertions, logs, check_label)
                    if not _ok:
                        passed = False

                elif check_type == "freshness":
                    _ok = _run_freshness_check(engine, text, table_name, check, assertions, logs, check_label)
                    if not _ok:
                        passed = False

                elif check_type == "row_count":
                    _ok = _run_row_count_check(engine, text, table_name, check, assertions, logs, check_label)
                    if not _ok:
                        passed = False

                else:
                    logs.append(f"{check_label} — SKIP: Unknown check type '{check_type}'")
                    assertions.append({
                        "type": check_type,
                        "expected": "known check type",
                        "actual": check_type,
                        "passed": False,
                    })
                    passed = False

            except Exception as exc:
                passed = False
                logs.append(f"{check_label} — ERROR: {type(exc).__name__}: {exc}")
                assertions.append({
                    "type": check_type,
                    "error": str(exc)[:200],
                    "passed": False,
                })

        # -- Total query time assertion --
        total_ms = (time.perf_counter() - total_start) * 1000
        time_ok = total_ms <= max_query_time_ms
        assertions.append({
            "type": "total_query_time",
            "max_ms": max_query_time_ms,
            "actual_ms": round(total_ms, 1),
            "passed": time_ok,
        })
        if not time_ok:
            passed = False
            logs.append(f"FAIL: Total query time {total_ms:.0f}ms exceeds max {max_query_time_ms}ms")

        engine.dispose()

    except ImportError:
        passed = False
        logs.append("sqlalchemy not available — cannot execute SQL tests")
        assertions.append({"type": "dependency", "expected": "sqlalchemy", "actual": "missing", "passed": False})
    except Exception as exc:
        passed = False
        logs.append(f"Data quality check error: {type(exc).__name__}: {exc}")
        assertions.append({
            "type": "execution",
            "expected": "success",
            "actual": str(exc)[:200],
            "passed": False,
        })

    total_ms = (time.perf_counter() - total_start) * 1000
    checks_passed = sum(1 for a in assertions if a.get("passed"))
    checks_total = len(assertions)

    return {
        "passed": passed,
        "assertions": assertions,
        "logs": logs,
        "details": {
            "template": "data_quality",
            "table_name": table_name,
            "db_type": db_type,
            "total_duration_ms": round(total_ms, 1),
            "checks_passed": checks_passed,
            "checks_total": checks_total,
        },
    }


# ---------------------------------------------------------------------------
# Individual check runners
# ---------------------------------------------------------------------------

def _run_null_check(engine, text, table_name, check, assertions, logs, label):
    """Verify required columns have no NULL values."""
    columns = check.get("columns") or []
    logs.append(f"{label} — columns: {columns}")
    all_ok = True

    for col in columns:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name} WHERE {col} IS NULL"))
            null_count = result.scalar() or 0

        col_ok = null_count == 0
        assertions.append({
            "type": "null_check",
            "column": col,
            "null_count": null_count,
            "passed": col_ok,
        })
        if not col_ok:
            all_ok = False
            logs.append(f"  FAIL: Column '{col}' has {null_count} NULL values")
        else:
            logs.append(f"  PASS: Column '{col}' has no NULLs")
    return all_ok


def _run_uniqueness_check(engine, text, table_name, check, assertions, logs, label):
    """Verify columns contain only unique values (no duplicates)."""
    columns = check.get("columns") or []
    logs.append(f"{label} — columns: {columns}")
    all_ok = True

    for col in columns:
        with engine.connect() as conn:
            result = conn.execute(text(
                f"SELECT {col}, COUNT(*) as cnt FROM {table_name} "
                f"GROUP BY {col} HAVING COUNT(*) > 1"
            ))
            duplicates = result.fetchall()
            dup_count = len(duplicates)

        col_ok = dup_count == 0
        assertions.append({
            "type": "uniqueness",
            "column": col,
            "duplicate_groups": dup_count,
            "passed": col_ok,
        })
        if not col_ok:
            all_ok = False
            logs.append(f"  FAIL: Column '{col}' has {dup_count} duplicate value groups")
        else:
            logs.append(f"  PASS: Column '{col}' has all unique values")
    return all_ok


def _run_referential_integrity(engine, text, table_name, check, assertions, logs, label):
    """Verify FK column values exist in referenced table."""
    column = check.get("column", "")
    ref_table = check.get("ref_table", "")
    ref_column = check.get("ref_column", "id")
    logs.append(f"{label} — {table_name}.{column} -> {ref_table}.{ref_column}")

    with engine.connect() as conn:
        result = conn.execute(text(
            f"SELECT COUNT(*) FROM {table_name} t "
            f"LEFT JOIN {ref_table} r ON t.{column} = r.{ref_column} "
            f"WHERE t.{column} IS NOT NULL AND r.{ref_column} IS NULL"
        ))
        orphan_count = result.scalar() or 0

    ri_ok = orphan_count == 0
    assertions.append({
        "type": "referential_integrity",
        "column": column,
        "ref_table": ref_table,
        "ref_column": ref_column,
        "orphan_count": orphan_count,
        "passed": ri_ok,
    })
    if not ri_ok:
        logs.append(f"  FAIL: {orphan_count} orphan records (FK values missing in {ref_table})")
    else:
        logs.append(f"  PASS: All FK values exist in {ref_table}")
    return ri_ok


def _run_range_check(engine, text, table_name, check, assertions, logs, label):
    """Verify column values fall within expected min/max range."""
    column = check.get("column", "")
    min_val = check.get("min")
    max_val = check.get("max")
    logs.append(f"{label} — {column} in [{min_val}, {max_val}]")

    conditions = []
    if min_val is not None:
        conditions.append(f"{column} < {min_val}")
    if max_val is not None:
        conditions.append(f"{column} > {max_val}")

    if not conditions:
        logs.append("  SKIP: No min/max provided")
        return True

    where_clause = " OR ".join(conditions)
    with engine.connect() as conn:
        result = conn.execute(text(
            f"SELECT COUNT(*) FROM {table_name} WHERE {column} IS NOT NULL AND ({where_clause})"
        ))
        out_of_range = result.scalar() or 0

    range_ok = out_of_range == 0
    assertions.append({
        "type": "range_check",
        "column": column,
        "min": min_val,
        "max": max_val,
        "out_of_range_count": out_of_range,
        "passed": range_ok,
    })
    if not range_ok:
        logs.append(f"  FAIL: {out_of_range} values outside range [{min_val}, {max_val}]")
    else:
        logs.append(f"  PASS: All values within range")
    return range_ok


def _run_format_check(engine, text, table_name, check, assertions, logs, label):
    """Verify column values match a regex pattern (PostgreSQL ~ operator)."""
    column = check.get("column", "")
    pattern = check.get("pattern", "")
    logs.append(f"{label} — {column} matches '{pattern}'")

    if not pattern:
        logs.append("  SKIP: No pattern provided")
        return True

    # Use regex operator (PostgreSQL: ~, MySQL: REGEXP)
    with engine.connect() as conn:
        result = conn.execute(text(
            f"SELECT COUNT(*) FROM {table_name} "
            f"WHERE {column} IS NOT NULL AND NOT ({column} ~ :pattern)"
        ), {"pattern": pattern})
        mismatch_count = result.scalar() or 0

    fmt_ok = mismatch_count == 0
    assertions.append({
        "type": "format_check",
        "column": column,
        "pattern": pattern,
        "mismatch_count": mismatch_count,
        "passed": fmt_ok,
    })
    if not fmt_ok:
        logs.append(f"  FAIL: {mismatch_count} values do not match pattern")
    else:
        logs.append(f"  PASS: All values match pattern")
    return fmt_ok


def _run_freshness_check(engine, text, table_name, check, assertions, logs, label):
    """Verify latest data is within expected time window."""
    column = check.get("column", "updated_at")
    max_age_hours = check.get("max_age_hours", 24)
    logs.append(f"{label} — MAX({column}) within {max_age_hours}h")

    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT MAX({column}) FROM {table_name}"))
        latest = result.scalar()

    if latest is None:
        logs.append("  FAIL: No data found (NULL result)")
        assertions.append({
            "type": "freshness",
            "column": column,
            "latest": None,
            "passed": False,
        })
        return False

    if isinstance(latest, datetime):
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - latest).total_seconds() / 3600
    else:
        latest_dt = datetime.fromisoformat(str(latest))
        if latest_dt.tzinfo is None:
            latest_dt = latest_dt.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - latest_dt).total_seconds() / 3600

    fresh_ok = age_hours <= max_age_hours
    assertions.append({
        "type": "freshness",
        "column": column,
        "latest": str(latest),
        "age_hours": round(age_hours, 1),
        "max_age_hours": max_age_hours,
        "passed": fresh_ok,
    })
    if not fresh_ok:
        logs.append(f"  FAIL: Data is {age_hours:.1f}h old (max: {max_age_hours}h)")
    else:
        logs.append(f"  PASS: Data is {age_hours:.1f}h old (max: {max_age_hours}h)")
    return fresh_ok


def _run_row_count_check(engine, text, table_name, check, assertions, logs, label):
    """Verify table has expected number of rows."""
    expected = check.get("expected", 0)
    operator = check.get("operator", "gte")
    logs.append(f"{label} — row count {operator} {expected}")

    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        actual = result.scalar() or 0

    op_fn = _OPERATORS.get(operator, _OPERATORS["gte"])
    count_ok = op_fn(actual, expected)
    assertions.append({
        "type": "row_count",
        "expected": expected,
        "actual": actual,
        "operator": operator,
        "passed": count_ok,
    })
    if not count_ok:
        logs.append(f"  FAIL: Row count {actual} not {operator} {expected}")
    else:
        logs.append(f"  PASS: Row count {actual} {operator} {expected}")
    return count_ok
