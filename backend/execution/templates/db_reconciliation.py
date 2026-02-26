"""
QAForge -- Database Reconciliation / ETL Validation Template.

Validates data pipeline integrity by comparing source and target:
  1. Row count reconciliation (source vs target)
  2. Column mapping validation (source column maps to target column)
  3. Aggregate reconciliation (SUM, COUNT, AVG match between source and target)
  4. Sample data comparison (spot-check rows)
  5. Freshness check (latest record timestamp within threshold)

Supports two connections: source_db and target_db.

LLM-extracted params schema:
{
  "source_query": "SELECT COUNT(*) as cnt FROM source_schema.orders WHERE date >= '2026-01-01'",
  "target_query": "SELECT COUNT(*) as cnt FROM target_schema.fact_orders WHERE order_date >= '2026-01-01'",
  "reconciliation_type": "row_count",
  "tolerance_percent": 0,
  "column_mappings": [
    {"source": "customer_name", "target": "cust_name"},
    {"source": "order_total", "target": "total_amount"}
  ],
  "aggregate_checks": [
    {"source_query": "SELECT SUM(amount) FROM src.orders", "target_query": "SELECT SUM(total_amount) FROM tgt.fact_orders", "tolerance_percent": 0.01}
  ],
  "freshness_query": "SELECT MAX(updated_at) FROM target_schema.fact_orders",
  "freshness_max_hours": 24
}
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


async def execute(
    params: Dict[str, Any],
    connection_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run a data reconciliation / ETL validation test.

    Args:
        params: LLM-extracted test parameters.
        connection_config: Connection profile config. May contain:
            - db_url / database_url: primary DB connection
            - source_db_url: separate source DB (optional, falls back to db_url)
            - target_db_url: separate target DB (optional, falls back to db_url)

    Returns:
        Standardised result dict with passed, assertions, logs, details.
    """
    # Support separate source/target connections or single connection
    primary_url = connection_config.get("db_url") or connection_config.get("database_url") or ""
    source_url = connection_config.get("source_db_url") or primary_url
    target_url = connection_config.get("target_db_url") or primary_url

    source_query = params.get("source_query", "")
    target_query = params.get("target_query", "")
    recon_type = params.get("reconciliation_type", "row_count")
    tolerance_pct = params.get("tolerance_percent", 0)
    column_mappings = params.get("column_mappings") or []
    aggregate_checks = params.get("aggregate_checks") or []
    freshness_query = params.get("freshness_query", "")
    freshness_max_hours = params.get("freshness_max_hours", 24)

    assertions: List[Dict[str, Any]] = []
    logs: List[str] = []
    passed = True
    total_start = time.perf_counter()
    step_details = {}

    if not source_url:
        return {
            "passed": False,
            "assertions": [{"type": "connection", "expected": "db_url configured", "actual": "missing", "passed": False}],
            "logs": ["No database URL configured"],
            "details": {},
        }

    try:
        import sqlalchemy
        from sqlalchemy import create_engine, text

        source_engine = create_engine(source_url, pool_pre_ping=True)
        target_engine = create_engine(target_url, pool_pre_ping=True) if target_url != source_url else source_engine

        # ── Row Count Reconciliation ──
        if source_query and target_query:
            logs.append("[Reconciliation] Comparing source vs target")
            logs.append(f"  Source: {source_query[:150]}...")
            logs.append(f"  Target: {target_query[:150]}...")

            start = time.perf_counter()
            with source_engine.connect() as conn:
                src_result = conn.execute(text(source_query))
                src_rows = [dict(r._mapping) for r in src_result.fetchall()]
            src_ms = (time.perf_counter() - start) * 1000

            start = time.perf_counter()
            with target_engine.connect() as conn:
                tgt_result = conn.execute(text(target_query))
                tgt_rows = [dict(r._mapping) for r in tgt_result.fetchall()]
            tgt_ms = (time.perf_counter() - start) * 1000

            logs.append(f"  Source: {len(src_rows)} rows ({src_ms:.0f}ms)")
            logs.append(f"  Target: {len(tgt_rows)} rows ({tgt_ms:.0f}ms)")

            if recon_type == "row_count":
                src_count = len(src_rows)
                tgt_count = len(tgt_rows)
                # Check if counts have a single 'cnt' or 'count' column
                if src_rows and len(src_rows) == 1:
                    first_row = src_rows[0]
                    for key in ["cnt", "count", "row_count", "total"]:
                        if key in first_row:
                            src_count = int(first_row[key])
                            break
                if tgt_rows and len(tgt_rows) == 1:
                    first_row = tgt_rows[0]
                    for key in ["cnt", "count", "row_count", "total"]:
                        if key in first_row:
                            tgt_count = int(first_row[key])
                            break

                diff_pct = abs(src_count - tgt_count) / max(src_count, 1) * 100
                count_ok = diff_pct <= tolerance_pct

                assertions.append({
                    "type": "row_count_reconciliation",
                    "source_count": src_count,
                    "target_count": tgt_count,
                    "difference_percent": round(diff_pct, 2),
                    "tolerance_percent": tolerance_pct,
                    "passed": count_ok,
                })
                if not count_ok:
                    passed = False
                    logs.append(f"  FAIL: Row count mismatch — source={src_count} target={tgt_count} (diff={diff_pct:.1f}%, tolerance={tolerance_pct}%)")
                else:
                    logs.append(f"  PASS: Row counts match — source={src_count} target={tgt_count}")

                step_details["row_count"] = {"source": src_count, "target": tgt_count, "diff_pct": round(diff_pct, 2)}

            elif recon_type == "data_compare":
                # Compare actual data row by row
                src_set = {str(sorted(r.items())) for r in src_rows}
                tgt_set = {str(sorted(r.items())) for r in tgt_rows}
                missing_in_target = len(src_set - tgt_set)
                extra_in_target = len(tgt_set - src_set)
                data_ok = missing_in_target == 0 and extra_in_target == 0

                assertions.append({
                    "type": "data_comparison",
                    "missing_in_target": missing_in_target,
                    "extra_in_target": extra_in_target,
                    "passed": data_ok,
                })
                if not data_ok:
                    passed = False
                    logs.append(f"  FAIL: Data mismatch — {missing_in_target} rows missing in target, {extra_in_target} extra rows")
                else:
                    logs.append(f"  PASS: All {len(src_rows)} rows match between source and target")

        # ── Column Mapping Validation ──
        if column_mappings and source_query and target_query:
            logs.append("[Column Mapping] Validating field mappings")
            # We already have src_rows and tgt_rows from above
            if src_rows and tgt_rows:
                src_cols = set(src_rows[0].keys()) if src_rows else set()
                tgt_cols = set(tgt_rows[0].keys()) if tgt_rows else set()

                for mapping in column_mappings:
                    src_col = mapping.get("source", "")
                    tgt_col = mapping.get("target", "")
                    src_exists = src_col.lower() in {c.lower() for c in src_cols}
                    tgt_exists = tgt_col.lower() in {c.lower() for c in tgt_cols}
                    map_ok = src_exists and tgt_exists

                    assertions.append({
                        "type": "column_mapping",
                        "source_column": src_col,
                        "target_column": tgt_col,
                        "source_exists": src_exists,
                        "target_exists": tgt_exists,
                        "passed": map_ok,
                    })
                    if not map_ok:
                        passed = False
                        logs.append(f"  FAIL: Mapping {src_col} -> {tgt_col}: source_exists={src_exists} target_exists={tgt_exists}")
                    else:
                        logs.append(f"  PASS: Mapping {src_col} -> {tgt_col}")

        # ── Aggregate Checks ──
        for i, agg in enumerate(aggregate_checks):
            src_q = agg.get("source_query", "")
            tgt_q = agg.get("target_query", "")
            tol = agg.get("tolerance_percent", 0.01)

            if src_q and tgt_q:
                logs.append(f"[Aggregate Check {i + 1}]")
                try:
                    with source_engine.connect() as conn:
                        src_val = conn.execute(text(src_q)).scalar()
                    with target_engine.connect() as conn:
                        tgt_val = conn.execute(text(tgt_q)).scalar()

                    src_num = float(src_val) if src_val is not None else 0
                    tgt_num = float(tgt_val) if tgt_val is not None else 0
                    diff_pct = abs(src_num - tgt_num) / max(abs(src_num), 1) * 100
                    agg_ok = diff_pct <= tol

                    assertions.append({
                        "type": "aggregate_reconciliation",
                        "check_index": i,
                        "source_value": src_num,
                        "target_value": tgt_num,
                        "difference_percent": round(diff_pct, 4),
                        "tolerance_percent": tol,
                        "passed": agg_ok,
                    })
                    if not agg_ok:
                        passed = False
                        logs.append(f"  FAIL: source={src_num} target={tgt_num} diff={diff_pct:.4f}%")
                    else:
                        logs.append(f"  PASS: source={src_num} target={tgt_num} diff={diff_pct:.4f}%")
                except Exception as exc:
                    passed = False
                    logs.append(f"  ERROR: {exc}")
                    assertions.append({
                        "type": "aggregate_reconciliation",
                        "check_index": i,
                        "error": str(exc),
                        "passed": False,
                    })

        # ── Freshness Check ──
        if freshness_query:
            logs.append("[Freshness Check]")
            try:
                with target_engine.connect() as conn:
                    latest = conn.execute(text(freshness_query)).scalar()

                if latest is not None:
                    if isinstance(latest, datetime):
                        if latest.tzinfo is None:
                            latest = latest.replace(tzinfo=timezone.utc)
                        age_hours = (datetime.now(timezone.utc) - latest).total_seconds() / 3600
                    else:
                        # Try parsing as string
                        latest_dt = datetime.fromisoformat(str(latest))
                        if latest_dt.tzinfo is None:
                            latest_dt = latest_dt.replace(tzinfo=timezone.utc)
                        age_hours = (datetime.now(timezone.utc) - latest_dt).total_seconds() / 3600

                    fresh_ok = age_hours <= freshness_max_hours
                    assertions.append({
                        "type": "freshness",
                        "latest_record": str(latest),
                        "age_hours": round(age_hours, 1),
                        "max_hours": freshness_max_hours,
                        "passed": fresh_ok,
                    })
                    if not fresh_ok:
                        passed = False
                        logs.append(f"  FAIL: Data is {age_hours:.1f} hours old (max: {freshness_max_hours}h)")
                    else:
                        logs.append(f"  PASS: Data is {age_hours:.1f} hours old (max: {freshness_max_hours}h)")
                else:
                    passed = False
                    logs.append("  FAIL: Freshness query returned NULL")
                    assertions.append({
                        "type": "freshness",
                        "latest_record": None,
                        "passed": False,
                    })
            except Exception as exc:
                passed = False
                logs.append(f"  ERROR: Freshness check failed: {exc}")
                assertions.append({"type": "freshness", "error": str(exc), "passed": False})

        # Clean up engines
        source_engine.dispose()
        if target_engine is not source_engine:
            target_engine.dispose()

    except ImportError:
        passed = False
        logs.append("sqlalchemy not available — cannot execute SQL tests")
        assertions.append({"type": "dependency", "expected": "sqlalchemy", "actual": "missing", "passed": False})
    except Exception as exc:
        passed = False
        logs.append(f"Reconciliation error: {type(exc).__name__}: {exc}")
        assertions.append({
            "type": "reconciliation",
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
            "template": "db_reconciliation",
            "reconciliation_type": recon_type,
            "total_duration_ms": round(total_ms, 1),
            "steps": step_details,
            "response_preview": str(step_details)[:500],
        },
    }
