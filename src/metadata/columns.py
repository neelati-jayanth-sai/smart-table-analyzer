"""Bounded, deterministic profiling for every primitive table column."""

from __future__ import annotations

import os
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any

_BATCH_SIZE = max(1, int(os.getenv("COL_ANALYSIS_BATCH_SIZE", "8")))
_RANGE_TYPES = {
    "byte", "short", "int", "integer", "bigint", "long", "float", "double",
    "decimal", "date", "timestamp", "timestamp_ntz",
}
_NON_PRIMITIVE_TYPES = {"array", "map", "struct", "binary", "variant", "void", "null"}


def analyze_columns(
    spark, table_name: str, columns: list[dict[str, str]], row_count: int
) -> dict[str, Any]:
    """Profile every primitive column with bounded aggregate scans.

    Batches bound statement width. A failed batch falls back to individual
    columns so one unsupported expression does not hide other column outcomes.
    """
    column_stats = _skipped_columns(columns)
    profileable = [col for col in columns if _type_name(col["type"]) not in _NON_PRIMITIVE_TYPES]
    if row_count <= 0:
        for col in profileable:
            column_stats[col["name"]] = _skipped(col, "empty_table")
        return _result(column_stats, len(columns), 0)

    batches = _batches(profileable, _BATCH_SIZE)
    for batch in batches:
        _profile_batch(spark, table_name, batch, row_count, column_stats)
    return _result(column_stats, len(columns), len(batches))

def _profile_batch(spark, table_name: str, columns: list[dict[str, str]], row_count: int,
                   column_stats: dict[str, dict[str, Any]]) -> None:
    try:
        row = spark.sql(_query(table_name, columns)).first()
    except Exception:
        for col in columns:
            _profile_one(spark, table_name, col, row_count, column_stats)
        return
    for index, col in enumerate(columns):
        column_stats[col["name"]] = _completed(col, row, index, row_count)


def _profile_one(spark, table_name: str, col: dict[str, str], row_count: int,
                 column_stats: dict[str, dict[str, Any]]) -> None:
    try:
        row = spark.sql(_query(table_name, [col])).first()
        column_stats[col["name"]] = _completed(col, row, 0, row_count)
    except FuturesTimeoutError:
        column_stats[col["name"]] = _failed(col, "timeout", timeout=True)
    except Exception as exc:
        column_stats[col["name"]] = _failed(col, str(exc))


def _query(table_name: str, columns: list[dict[str, str]]) -> str:
    expressions = ["COUNT(*) AS profile_row_count"]
    for index, col in enumerate(columns):
        name = _identifier(col["name"])
        expressions += [
            f"COUNT(DISTINCT {name}) AS c{index}_cardinality",
            f"COUNT(*) - COUNT({name}) AS c{index}_null_count",
        ]
        if _type_name(col["type"]) in _RANGE_TYPES:
            expressions += [f"MIN({name}) AS c{index}_min", f"MAX({name}) AS c{index}_max"]
    return f"SELECT {', '.join(expressions)} FROM {table_name}"


def _completed(col: dict[str, str], row: Any, index: int, fallback_rows: int) -> dict[str, Any]:
    profiled_rows = int(_value(row, "profile_row_count", fallback_rows) or fallback_rows)
    cardinality = int(_value(row, f"c{index}_cardinality", 0) or 0)
    null_count = int(_value(row, f"c{index}_null_count", 0) or 0)
    ratio = cardinality / profiled_rows if profiled_rows else 0.0
    null_pct = (null_count / profiled_rows * 100) if profiled_rows else 0.0
    stats = {
        "type": col["type"], "status": "completed", "method": "exact_aggregate_scan",
        "profiled_row_count": profiled_rows, "cardinality": cardinality,
        "null_count": null_count, "null_percentage": round(null_pct, 2),
        "cardinality_ratio": round(ratio, 4),
        "is_high_cardinality": cardinality > 1000 or ratio > 0.1,
        "is_partition_candidate": 100 < cardinality < 10000 and null_pct < 5 and 0.001 < ratio < 0.5,
    }
    if _type_name(col["type"]) in _RANGE_TYPES:
        stats["distribution_hint"] = {
            "kind": "range", "min": _value(row, f"c{index}_min"), "max": _value(row, f"c{index}_max"),
        }
    else:
        stats["distribution_hint"] = {"kind": "not_assessed", "reason": "type_has_no_low_cost_range"}
    return stats


def _skipped_columns(columns: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    return {
        col["name"]: _skipped(col, "non_primitive_type")
        for col in columns if _type_name(col["type"]) in _NON_PRIMITIVE_TYPES
    }


def _skipped(col: dict[str, str], reason: str) -> dict[str, Any]:
    return {"type": col["type"], "status": "skipped", "skipped": True, "reason": reason}


def _failed(col: dict[str, str], reason: str, timeout: bool = False) -> dict[str, Any]:
    return {"type": col["type"], "status": "failed", "error": reason, "timeout": timeout}


def _result(column_stats: dict[str, dict[str, Any]], declared: int, batch_count: int) -> dict[str, Any]:
    stats = list(column_stats.values())
    candidates = [
        {"column": name, "cardinality": stat["cardinality"], "null_percentage": stat["null_percentage"], "type": stat["type"]}
        for name, stat in column_stats.items() if stat.get("is_partition_candidate")
    ]
    candidates.sort(key=lambda candidate: candidate["cardinality"])
    failed = sum(stat.get("status") == "failed" for stat in stats)
    return {
        "status": "completed" if not failed else "partial", "profile_method": "exact_aggregate_scan",
        "column_stats": column_stats, "partition_candidates": candidates[:10],
        "total_columns_declared": declared, "total_columns_analyzed": sum(stat.get("status") == "completed" for stat in stats),
        "total_columns_skipped": sum(stat.get("status") == "skipped" for stat in stats),
        "total_columns_failed": failed, "batch_size": _BATCH_SIZE, "batch_count": batch_count,
    }


def _batches(columns: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [columns[index:index + size] for index in range(0, len(columns), size)]


def _identifier(name: str) -> str:
    return f"`{name.replace('`', '``')}`"


def _type_name(type_name: str) -> str:
    return type_name.lower().split("(", 1)[0].split("<", 1)[0].strip()


def _value(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default
