"""Analyze column statistics for partitioning and optimization recommendations."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

# Tuning knobs — override via env vars
_COL_TIMEOUT = int(os.getenv("COL_ANALYSIS_TIMEOUT_SECONDS", "15"))
_COL_WORKERS = int(os.getenv("COL_ANALYSIS_WORKERS", "1"))
_COL_MAX = int(os.getenv("COL_ANALYSIS_MAX_COLUMNS", "8"))

# Column types most likely to be partition candidates — analysed first
_PRIORITY_TYPES = {"date", "timestamp", "string", "int", "bigint", "long", "smallint", "short", "decimal"}
_SKIP_TYPES = {"array", "map", "struct", "binary"}


def _priority_columns(columns: list[dict[str, str]], cap: int) -> list[dict[str, str]]:
    """Return up to `cap` columns, prioritising date/timestamp/string/int types.
    Deprioritizes flag/indicator columns as they usually have cardinality 2.
    """
    priority, rest = [], []
    for col in columns:
        name = col["name"].lower()
        t = col["type"].lower().split("(")[0].strip()
        is_priority_type = t in _PRIORITY_TYPES
        is_flag = name.endswith("_flg") or name.endswith("_ind") or name.startswith("is_")

        if is_priority_type and not is_flag:
            priority.append(col)
        else:
            rest.append(col)
    return (priority + rest)[:cap]


def _analyze_one_column(
    spark, table_name: str, col: dict[str, str], row_count: int
) -> tuple[str, dict[str, Any]]:
    """Fetch cardinality + null count for one column in a single combined SQL."""
    col_name = col["name"]
    col_type = col["type"]

    if any(t in col_type.lower() for t in _SKIP_TYPES):
        return col_name, {"type": col_type, "skipped": True,
                          "reason": "Complex type not suitable for cardinality analysis"}

    query = (
        f"SELECT COUNT(DISTINCT {col_name}), "
        f"COUNT(*) - COUNT({col_name}) "
        f"FROM {table_name}"
    )
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(lambda: spark.sql(query).first())
    try:
        row = future.result(timeout=_COL_TIMEOUT)
    except FuturesTimeoutError:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        return col_name, {
            "type": col_type,
            "timeout": True,
            "cancellation_status": "unconfirmed",
        }
    except Exception as exc:
        executor.shutdown(wait=False, cancel_futures=True)
        return col_name, {"type": col_type, "error": str(exc)}
    else:
        executor.shutdown(wait=False, cancel_futures=True)

    cardinality = int(row[0] or 0)
    null_count = int(row[1] or 0)
    null_pct = round((null_count / row_count) * 100, 2) if row_count > 0 else 0.0
    cardinality_ratio = cardinality / row_count if row_count > 0 else 0

    is_high_cardinality = cardinality > 1000 or cardinality_ratio > 0.1
    is_partition_candidate = (
        100 < cardinality < 10000
        and null_pct < 5
        and 0.001 < cardinality_ratio < 0.5
    )

    return col_name, {
        "type": col_type,
        "cardinality": cardinality,
        "null_percentage": null_pct,
        "is_high_cardinality": is_high_cardinality,
        "is_partition_candidate": is_partition_candidate,
        "cardinality_ratio": round(cardinality_ratio, 4),
    }


def analyze_columns(
    spark, table_name: str, columns: list[dict[str, str]], row_count: int
) -> dict[str, Any]:
    """Analyze column statistics for partitioning recommendations.

    Runs at most the configured capped set of combined SQL statements. The
    default is one worker and eight columns because each statement may scan the
    base table. A timeout returns promptly, but Spark cancellation is reported
    as unconfirmed because the connector may continue running server-side.
    """
    if row_count == 0:
        return {"error": "Cannot analyze columns for empty table"}

    columns_to_analyze = _priority_columns(columns, _COL_MAX)
    column_stats: dict[str, Any] = {}
    partition_candidates: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, _COL_WORKERS)) as pool:
        futures = {
            pool.submit(_analyze_one_column, spark, table_name, col, row_count): col["name"]
            for col in columns_to_analyze
        }
        for future in futures:
            col_name = futures[future]
            try:
                name, stats = future.result()
                column_stats[name] = stats
                if stats.get("is_partition_candidate"):
                    partition_candidates.append({
                        "column": name,
                        "cardinality": stats["cardinality"],
                        "null_percentage": stats["null_percentage"],
                        "type": stats["type"],
                    })
            except Exception as exc:
                column_stats[col_name] = {"error": str(exc)}

    partition_candidates.sort(key=lambda x: x["cardinality"])
    timed_out_columns = [
        name for name, stats in column_stats.items() if stats.get("timeout")
    ]
    return {
        "column_stats": column_stats,
        "partition_candidates": partition_candidates[:10],
        "total_columns_analyzed": len(columns_to_analyze),
        "collection_status": "partial" if timed_out_columns else "complete",
        "timed_out_columns": timed_out_columns,
        "cancellation_status": "unconfirmed" if timed_out_columns else "not_needed",
    }
