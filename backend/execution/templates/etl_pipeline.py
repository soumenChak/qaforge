"""
QAForge -- ETL Pipeline Validation Template.

Validates data after ETL/ELT pipeline execution:
  1. Source-target row count comparison
  2. Data transformation validation (sample rows)
  3. Schema validation (column names and types)
  4. Null propagation check (nulls not introduced by ETL)
  5. Dedup verification (no duplicates in target)

Supports two database connections: source and target.

LLM-extracted params schema:
{
  "source_table": "raw.orders",
  "target_table": "curated.fact_orders",
  "key_columns": ["order_id"],
  "transformations": [
    {"source_column": "order_date", "target_column": "order_date_key", "transform": "date_to_int"},
    {"source_column": "amount", "target_column": "total_amount", "transform": "round_2dp"}
  ],
  "expected_schema": [
    {"column": "order_id", "type": "integer"},
    {"column": "total_amount", "type": "numeric"}
  ],
  "not_null_columns": ["order_id", "total_amount"],
  "row_count_tolerance_percent": 0,
  "sample_size": 10
}
"""

import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


async def execute(
    params: Dict[str, Any],
    connection_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run ETL pipeline validation comparing source and target tables.

    Args:
        params: LLM-extracted test parameters.
        connection_config: Connection profile config. May contain:
            - db_url / database_url: primary DB connection
            - source_db_url: separate source DB (optional, falls back to db_url)
            - target_db_url: separate target DB (optional, falls back to db_url)

    Returns:
        Standardised result dict with passed, assertions, logs, details.
    """
    primary_url = connection_config.get("db_url") or connection_config.get("database_url") or ""
    source_url = connection_config.get("source_db_url") or primary_url
    target_url = connection_config.get("target_db_url") or primary_url

    source_table = params.get("source_table", "")
    target_table = params.get("target_table", "")
    key_columns: List[str] = params.get("key_columns") or []
    transformations: List[Dict] = params.get("transformations") or []
    expected_schema: List[Dict] = params.get("expected_schema") or []
    not_null_columns: List[str] = params.get("not_null_columns") or []
    tolerance_pct = params.get("row_count_tolerance_percent", 0)
    sample_size = params.get("sample_size", 10)

    assertions: List[Dict[str, Any]] = []
    logs: List[str] = []
    passed = True
    total_start = time.perf_counter()
    step_details: Dict[str, Any] = {}

    if not source_table or not target_table:
        return {
            "passed": False,
            "assertions": [{"type": "tables_provided", "expected": "non-empty", "actual": "missing", "passed": False}],
            "logs": ["source_table and target_table are required"],
            "details": {},
        }

    if not source_url:
        return {
            "passed": False,
            "assertions": [{"type": "connection", "expected": "db_url configured", "actual": "missing", "passed": False}],
            "logs": ["No database URL configured in connection"],
            "details": {},
        }

    logs.append(f"ETL Pipeline Validation: {source_table} -> {target_table}")

    try:
        import sqlalchemy
        from sqlalchemy import create_engine, text, inspect

        source_engine = create_engine(source_url, pool_pre_ping=True)
        target_engine = create_engine(target_url, pool_pre_ping=True) if target_url != source_url else source_engine

        # -- Step 1: Row count comparison --
        logs.append("[1/5] Row count comparison")
        start = time.perf_counter()
        with source_engine.connect() as conn:
            src_count = conn.execute(text(f"SELECT COUNT(*) FROM {source_table}")).scalar() or 0
        with target_engine.connect() as conn:
            tgt_count = conn.execute(text(f"SELECT COUNT(*) FROM {target_table}")).scalar() or 0
        latency = (time.perf_counter() - start) * 1000

        diff_pct = abs(src_count - tgt_count) / max(src_count, 1) * 100
        count_ok = diff_pct <= tolerance_pct

        assertions.append({
            "type": "row_count_comparison",
            "source_count": src_count,
            "target_count": tgt_count,
            "difference_percent": round(diff_pct, 2),
            "tolerance_percent": tolerance_pct,
            "passed": count_ok,
        })
        logs.append(f"  Source: {src_count} rows, Target: {tgt_count} rows ({latency:.0f}ms)")
        if not count_ok:
            passed = False
            logs.append(f"  FAIL: Row count diff {diff_pct:.1f}% exceeds tolerance {tolerance_pct}%")
        else:
            logs.append(f"  PASS: Row counts within tolerance")
        step_details["row_count"] = {"source": src_count, "target": tgt_count, "diff_pct": round(diff_pct, 2)}

        # -- Step 2: Transformation validation (sample rows) --
        if transformations and key_columns:
            logs.append(f"[2/5] Transformation validation (sample_size={sample_size})")
            key_cols_str = ", ".join(key_columns)

            with source_engine.connect() as conn:
                src_rows_result = conn.execute(text(
                    f"SELECT * FROM {source_table} ORDER BY {key_cols_str} LIMIT {sample_size}"
                ))
                src_sample = [dict(r._mapping) for r in src_rows_result.fetchall()]

            with target_engine.connect() as conn:
                tgt_rows_result = conn.execute(text(
                    f"SELECT * FROM {target_table} ORDER BY {key_cols_str} LIMIT {sample_size}"
                ))
                tgt_sample = [dict(r._mapping) for r in tgt_rows_result.fetchall()]

            # Build target lookup by key
            tgt_lookup: Dict[str, Dict] = {}
            for row in tgt_sample:
                key = tuple(str(row.get(k)) for k in key_columns)
                tgt_lookup[key] = row

            transform_pass = 0
            transform_fail = 0
            for src_row in src_sample:
                key = tuple(str(src_row.get(k)) for k in key_columns)
                tgt_row = tgt_lookup.get(key)
                if tgt_row is None:
                    transform_fail += 1
                    continue

                for t in transformations:
                    src_col = t.get("source_column", "")
                    tgt_col = t.get("target_column", "")
                    if tgt_col in tgt_row:
                        transform_pass += 1
                    else:
                        transform_fail += 1

            t_ok = transform_fail == 0
            assertions.append({
                "type": "transformation_validation",
                "sample_size": len(src_sample),
                "checks_passed": transform_pass,
                "checks_failed": transform_fail,
                "passed": t_ok,
            })
            if not t_ok:
                passed = False
                logs.append(f"  FAIL: {transform_fail} transformation checks failed")
            else:
                logs.append(f"  PASS: {transform_pass} transformation checks passed")
            step_details["transformation"] = {"passed": transform_pass, "failed": transform_fail}
        else:
            logs.append("[2/5] Transformation validation — skipped (no transformations or key_columns)")
            step_details["transformation"] = {"status": "skipped"}

        # -- Step 3: Schema validation --
        if expected_schema:
            logs.append("[3/5] Schema validation")
            try:
                inspector = inspect(target_engine)
                # Parse schema.table
                parts = target_table.split(".")
                tgt_schema = parts[0] if len(parts) > 1 else None
                tgt_tbl = parts[-1]

                actual_columns = inspector.get_columns(tgt_tbl, schema=tgt_schema)
                actual_col_map = {c["name"].lower(): str(c["type"]).lower() for c in actual_columns}

                schema_ok = True
                for expected_col in expected_schema:
                    col_name = expected_col.get("column", "").lower()
                    expected_type = expected_col.get("type", "").lower()

                    col_exists = col_name in actual_col_map
                    type_matches = True
                    actual_type_str = actual_col_map.get(col_name, "N/A")

                    if col_exists and expected_type:
                        # Fuzzy type match (e.g., "integer" matches "INTEGER", "int4")
                        type_matches = expected_type in actual_type_str or actual_type_str.startswith(expected_type)

                    col_ok = col_exists and type_matches
                    assertions.append({
                        "type": "schema_validation",
                        "column": col_name,
                        "expected_type": expected_type,
                        "actual_type": actual_type_str,
                        "exists": col_exists,
                        "type_matches": type_matches,
                        "passed": col_ok,
                    })
                    if not col_ok:
                        schema_ok = False
                        logs.append(f"  FAIL: Column '{col_name}' — exists={col_exists}, type={actual_type_str} (expected {expected_type})")
                    else:
                        logs.append(f"  PASS: Column '{col_name}' type={actual_type_str}")

                if not schema_ok:
                    passed = False
            except Exception as exc:
                passed = False
                logs.append(f"  ERROR: Schema inspection failed: {exc}")
                assertions.append({"type": "schema_validation", "error": str(exc)[:200], "passed": False})
            step_details["schema"] = {"columns_checked": len(expected_schema)}
        else:
            logs.append("[3/5] Schema validation — skipped (no expected_schema)")
            step_details["schema"] = {"status": "skipped"}

        # -- Step 4: Null propagation check --
        if not_null_columns:
            logs.append(f"[4/5] Null propagation check — columns: {not_null_columns}")
            null_ok = True
            for col in not_null_columns:
                with target_engine.connect() as conn:
                    null_count = conn.execute(text(
                        f"SELECT COUNT(*) FROM {target_table} WHERE {col} IS NULL"
                    )).scalar() or 0

                col_ok = null_count == 0
                assertions.append({
                    "type": "null_propagation",
                    "column": col,
                    "null_count": null_count,
                    "passed": col_ok,
                })
                if not col_ok:
                    null_ok = False
                    logs.append(f"  FAIL: Column '{col}' has {null_count} NULLs in target")
                else:
                    logs.append(f"  PASS: Column '{col}' has no NULLs in target")
            if not null_ok:
                passed = False
            step_details["null_propagation"] = {"columns_checked": len(not_null_columns)}
        else:
            logs.append("[4/5] Null propagation check — skipped (no not_null_columns)")
            step_details["null_propagation"] = {"status": "skipped"}

        # -- Step 5: Dedup verification --
        if key_columns:
            logs.append(f"[5/5] Dedup verification — key: {key_columns}")
            key_cols_str = ", ".join(key_columns)
            with target_engine.connect() as conn:
                dup_result = conn.execute(text(
                    f"SELECT {key_cols_str}, COUNT(*) as cnt FROM {target_table} "
                    f"GROUP BY {key_cols_str} HAVING COUNT(*) > 1"
                ))
                dup_rows = dup_result.fetchall()
                dup_count = len(dup_rows)

            dedup_ok = dup_count == 0
            assertions.append({
                "type": "dedup_verification",
                "key_columns": key_columns,
                "duplicate_groups": dup_count,
                "passed": dedup_ok,
            })
            if not dedup_ok:
                passed = False
                logs.append(f"  FAIL: {dup_count} duplicate key groups in target")
            else:
                logs.append(f"  PASS: No duplicates on key columns")
            step_details["dedup"] = {"duplicate_groups": dup_count}
        else:
            logs.append("[5/5] Dedup verification — skipped (no key_columns)")
            step_details["dedup"] = {"status": "skipped"}

        # Cleanup
        source_engine.dispose()
        if target_engine is not source_engine:
            target_engine.dispose()

    except ImportError:
        passed = False
        logs.append("sqlalchemy not available — cannot execute SQL tests")
        assertions.append({"type": "dependency", "expected": "sqlalchemy", "actual": "missing", "passed": False})
    except Exception as exc:
        passed = False
        logs.append(f"ETL validation error: {type(exc).__name__}: {exc}")
        assertions.append({
            "type": "execution",
            "expected": "success",
            "actual": str(exc)[:200],
            "passed": False,
        })

    total_ms = (time.perf_counter() - total_start) * 1000
    return {
        "passed": passed,
        "assertions": assertions,
        "logs": logs,
        "details": {
            "template": "etl_pipeline",
            "source_table": source_table,
            "target_table": target_table,
            "total_duration_ms": round(total_ms, 1),
            "steps": step_details,
        },
    }
