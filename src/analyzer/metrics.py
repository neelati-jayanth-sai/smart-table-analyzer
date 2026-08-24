"""Deterministic metric collection: one parallel pass over Iceberg metadata.

Reads only. No interpretation of what the numbers mean lives here.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

logger = logging.getLogger(__name__)


class MetadataUnavailable(RuntimeError):
    """The table's metadata could not be read at all.

    Distinct from an empty table: a table with no rows answers its metadata
    queries with zeros, whereas an unreachable one answers nothing. Reporting
    the second as the first would let an outage look like a clean, empty table.
    """


_FAILED = object()


def _scalar(spark, query: str) -> Any:
    """Run one read-only aggregate, returning `_FAILED` if the query errors."""
    try:
        row = spark.sql(query).first()
        return row[0] if row is not None and row[0] is not None else 0
    except Exception as exc:
        logger.info("Metric query failed (%s): %s", query, exc)
        return _FAILED


def _row(spark, query: str) -> dict[str, Any]:
    try:
        row = spark.sql(query).first()
        return row.asDict() if row is not None else {}
    except Exception as exc:
        logger.info("Metric query failed (%s): %s", query, exc)
        return {}


def collect_raw_metrics(spark, table_name: str) -> dict[str, Any]:
    """Read the deterministic table metrics. One parallel pass, no retries."""
    queries = {
        "row_count": f"SELECT COUNT(*) FROM {table_name}",
        "num_data_files": f"SELECT COUNT(*) FROM {table_name}.files WHERE content = 0",
        "total_data_file_bytes": (
            f"SELECT COALESCE(SUM(file_size_in_bytes),0) FROM {table_name}.files WHERE content=0"
        ),
        "delete_bytes": (
            f"SELECT COALESCE(SUM(file_size_in_bytes),0) FROM {table_name}.files WHERE content!=0"
        ),
        "partition_count": f"SELECT COUNT(*) FROM {table_name}.partitions",
        "snapshot_count": f"SELECT COUNT(*) FROM {table_name}.snapshots",
        "distinct_sort_orders": (
            f"SELECT COUNT(DISTINCT sort_order_id) FROM {table_name}.files WHERE content=0"
        ),
    }

    results: dict[str, int] = {key: 0 for key in queries}
    failed: set[str] = set()
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        futures = {pool.submit(_scalar, spark, q): k for k, q in queries.items()}
        for future in as_completed(futures):
            key = futures[future]
            value = future.result()
            if value is _FAILED:
                failed.add(key)
            else:
                results[key] = int(value or 0)

    if len(failed) == len(queries):
        raise MetadataUnavailable(
            f"Every Iceberg metadata query failed for {table_name}; "
            "the table is unreachable, not empty."
        )
    if failed:
        logger.warning(
            "%d of %d metric queries failed for %s: %s",
            len(failed), len(queries), table_name, ", ".join(sorted(failed)),
        )

    results["partition_stats"] = _row(
        spark,
        f"SELECT MAX(record_count) AS max_rows, MIN(record_count) AS min_rows,"
        f" AVG(record_count) AS avg_rows, MAX(file_count) AS max_files"
        f" FROM {table_name}.partitions",
    )
    results["failed_metrics"] = sorted(failed)
    # Only a table that actually answered both counts can be called empty.
    results["is_empty"] = (
        not {"row_count", "num_data_files"} & failed
        and results["row_count"] == 0
        and results["num_data_files"] == 0
    )
    return results


def extract_query_patterns(spark, table_name: str) -> dict[str, Any] | None:
    """Read the IOMETE query log workload profile; None when unavailable."""
    try:
        from src.metadata.query_patterns import IOMETEQueryPatternAdapter

        adapter = IOMETEQueryPatternAdapter(spark)
        if not adapter.is_available():
            return None
        metrics_table = os.getenv("IOMETE_QUERY_METRICS_TABLE", table_name)
        patterns = adapter.extract_patterns(metrics_table)
        return {
            "avg_cpu_time_ns": patterns.avg_cpu_time_ns,
            "avg_input_bytes": patterns.avg_input_bytes,
            "total_queries_analyzed": patterns.total_queries_analyzed,
            "scan_queries_analyzed": patterns.scan_queries_analyzed,
            "column_usage": patterns.column_usage,
            "order_by_columns": patterns.order_by_columns or [],
            "group_by_columns": patterns.group_by_columns or [],
        }
    except Exception as exc:
        logger.info("Query pattern extraction unavailable: %s", exc)
        return None
