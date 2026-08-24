"""Deterministic metric collection from Iceberg metadata tables.

Reads only. No interpretation of what the numbers mean lives here.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class MetadataUnavailable(RuntimeError):
    """The table's metadata could not be read at all.

    Distinct from an empty table: a table with no rows answers its metadata
    queries with zeros, whereas an unreachable one answers nothing. Reporting
    the second as the first would let an outage look like a clean, empty table.
    """


def _row(spark, query: str) -> dict[str, Any]:
    try:
        row = spark.sql(query).first()
        return row.asDict() if row is not None else {}
    except Exception as exc:
        logger.info("Metric query failed (%s): %s", query, exc)
        return {}


def collect_raw_metrics(spark, table_name: str) -> dict[str, Any]:
    """Read deterministic metrics without scanning the base table.

    ``row_count`` is the current data-file record-count estimate. Delete files
    can make it differ from the exact logical row count, so its provenance is
    returned with the result instead of presenting it as a scanned count.
    """
    queries = {
        "data_file_stats": (
            f"SELECT COALESCE(SUM(record_count),0) AS row_count,"
            f" COUNT(*) AS num_data_files,"
            f" COALESCE(SUM(file_size_in_bytes),0) AS total_data_file_bytes,"
            f" COUNT(DISTINCT sort_order_id) AS distinct_sort_orders"
            f" FROM {table_name}.files WHERE content=0"
        ),
        "delete_file_stats": (
            f"SELECT COALESCE(SUM(file_size_in_bytes),0) AS delete_bytes"
            f" FROM {table_name}.files WHERE content!=0"
        ),
        "partition_stats": (
            f"SELECT COUNT(*) AS num_partitions, MAX(record_count) AS max_rows,"
            f" MIN(record_count) AS min_rows, AVG(record_count) AS avg_rows,"
            f" MAX(file_count) AS max_files,"
            f" AVG(total_data_file_size_in_bytes) AS avg_partition_bytes,"
            f" MIN(total_data_file_size_in_bytes) AS min_partition_bytes,"
            f" MAX(total_data_file_size_in_bytes) AS max_partition_bytes,"
            f" AVG(file_count) AS avg_files_per_partition,"
            f" MAX(file_count) AS max_files_per_partition"
            f" FROM {table_name}.partitions"
        ),
        "snapshot_count": f"SELECT COUNT(*) AS snapshot_count FROM {table_name}.snapshots",
    }

    results: dict[str, Any] = {
        "row_count": 0,
        "num_data_files": 0,
        "total_data_file_bytes": 0,
        "delete_bytes": 0,
        "partition_count": 0,
        "snapshot_count": 0,
        "distinct_sort_orders": 0,
        "row_count_source": "iceberg_data_file_record_counts",
        "row_count_is_exact": False,
    }
    failed: set[str] = set()
    for key, query in queries.items():
        value = _row(spark, query)
        if not value:
            failed.add(key)
        else:
            if key == "partition_stats":
                results["partition_count"] = int(value.get("num_partitions", 0) or 0)
                results["partition_stats"] = {
                    name: value.get(name, 0)
                    for name in ("max_rows", "min_rows", "avg_rows", "max_files")
                }
                results["partition_storage"] = {
                    name: value.get(name, 0)
                    for name in (
                        "avg_partition_bytes", "min_partition_bytes", "max_partition_bytes",
                        "avg_files_per_partition", "max_files_per_partition",
                    )
                }
            else:
                for name, metric in value.items():
                    results[name] = int(metric or 0)

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
    results["failed_metrics"] = sorted(failed)
    # Only a table that answered both metadata metrics can be called empty.
    results["is_empty"] = (
        "data_file_stats" not in failed
        and results["row_count"] == 0
        and results["num_data_files"] == 0
    )
    return results


def extract_query_patterns(
    spark, table_name: str, query_metrics_table: str | None = None
) -> dict[str, Any] | None:
    """Read the IOMETE query log workload profile; None when unavailable."""
    try:
        from src.metadata.query_patterns import IOMETEQueryPatternAdapter

        adapter = IOMETEQueryPatternAdapter(spark)
        if not adapter.is_available():
            return None
        metrics_table = query_metrics_table or os.getenv("IOMETE_QUERY_METRICS_TABLE", table_name)
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
