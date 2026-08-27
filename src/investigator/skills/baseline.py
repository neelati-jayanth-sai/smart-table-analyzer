"""Reuse snapshot-scoped Legacy Analyzer measurements as check evidence."""

from __future__ import annotations

from typing import Any


def result_for(check_id: str, metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a normalized cached result when the baseline already measured it."""
    metadata = metadata or {}
    raw = metadata.get("deterministic_metrics") or {}
    rows = _rows(check_id, raw, metadata)
    if rows is None:
        return None
    return {"success": True, "rows": [rows], "row_count": 1, "truncated": False}


def _rows(check_id: str, raw: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any] | None:
    files = max(int(raw.get("num_data_files") or 0), 1)
    if check_id == "empty_table":
        return {"file_count": raw.get("num_data_files", 0), "row_count": raw.get("row_count", 0)}
    if check_id == "file_size" and raw:
        total = int(raw.get("total_data_file_bytes") or 0)
        return {"file_count": raw.get("num_data_files", 0), "avg_bytes": total / files}
    if check_id == "skew" and raw.get("partition_stats"):
        return {"partition_count": raw.get("partition_count", 0), **raw["partition_stats"]}
    if check_id == "partitioning" and raw.get("partition_storage"):
        return {"partition_count": raw.get("partition_count", 0), **raw["partition_storage"]}
    if check_id == "sort" and raw:
        return {"file_count": raw.get("num_data_files", 0), "sort_orders": raw.get("distinct_sort_orders", 0)}
    if check_id == "delete_overhead" and raw:
        return {"delete_bytes": raw.get("delete_bytes", 0)}
    if check_id == "snapshot_retention" and raw:
        return {"snapshot_count": raw.get("snapshot_count", 0)}
    if check_id == "table_properties":
        return metadata.get("table_properties") or None
    if check_id == "scan_efficiency":
        return metadata.get("query_patterns") or None
    if check_id == "partition_suggestions":
        analysis = metadata.get("column_analysis") or {}
        return analysis if analysis.get("status") in {"completed", "partial"} else None
    return None
