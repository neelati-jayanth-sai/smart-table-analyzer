"""Investigation signals: measurements expressed against an operating standard.

A signal states what was measured and how far it sits from the standard. It
never states what to do about it — that judgement belongs to the Investigator.
"""
from __future__ import annotations
import os
from typing import Any
from src.utils import human_bytes
TARGET_FILE_BYTES = 134_217_728  # 128 MB
_SMALL_FILE_RATIO = 0.5          # avg below half the target is "small files"
_LARGE_FILE_RATIO = 2.0
_SKEW_HIGH = 20.0                # max/average partition rows
_SKEW_MEDIUM = 5.0
_MANIFEST_FILE_WARN = 10_000
_SNAPSHOT_WARN = 100
_DELETE_OVERHEAD_WARN = 0.10
def target_file_bytes() -> int:
    """Return the production target, or an explicit local-fixture scale."""
    try:
        return max(1, int(os.getenv("STA_TARGET_FILE_BYTES", str(TARGET_FILE_BYTES))))
    except ValueError:
        return TARGET_FILE_BYTES


def _signal(name: str, severity: str, detail: str, **metrics: Any) -> dict[str, Any]:
    return {"name": name, "severity": severity, "detail": detail, "metrics": metrics}


def detect_signals(
    raw: dict[str, Any], metadata: dict[str, Any], patterns: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Derive investigation signals from measured facts.

    A signal states what was measured and how far it is from the operating
    standard. It never says what to do about it.
    """
    signals: list[dict[str, Any]] = []

    if raw.get("is_empty"):
        return [_signal("empty_table", "HIGH", "Table has 0 rows and 0 data files")]

    failed_metrics = raw.get("failed_metrics") or []
    data_file_stats_available = "data_file_stats" not in failed_metrics
    partition_stats_available = "partition_stats" not in failed_metrics
    delete_file_stats_available = "delete_file_stats" not in failed_metrics
    snapshot_count_available = "snapshot_count" not in failed_metrics
    if failed_metrics:
        signals.append(
            _signal(
                "measurement_unavailable",
                "HIGH",
                f"Required metadata measurements were unavailable: {', '.join(failed_metrics)}",
                unavailable_metrics=sorted(failed_metrics),
            )
        )

    target = target_file_bytes()
    num_files = max(int(raw.get("num_data_files", 0)), 1)
    total_bytes = int(raw.get("total_data_file_bytes", 0))
    avg_bytes = total_bytes / num_files if total_bytes else 0

    if data_file_stats_available and avg_bytes and avg_bytes < target * _SMALL_FILE_RATIO:
        severity = "HIGH" if avg_bytes < target * 0.1 else "MEDIUM"
        signals.append(
            _signal(
                "small_files",
                severity,
                f"Average data file is {human_bytes(avg_bytes)} against a "
                f"{human_bytes(target)} target",
                avg_file_bytes=int(avg_bytes),
                num_data_files=num_files,
                target_file_bytes=target,
            )
        )
    elif data_file_stats_available and avg_bytes > target * _LARGE_FILE_RATIO:
        signals.append(
            _signal(
                "large_files",
                "MEDIUM",
                f"Average data file is {human_bytes(avg_bytes)}, over twice the target",
                avg_file_bytes=int(avg_bytes),
                target_file_bytes=target,
            )
        )

    storage = raw.get("partition_storage") or {}
    avg_partition_bytes = float(storage.get("avg_partition_bytes") or 0)
    if partition_stats_available and avg_partition_bytes and avg_partition_bytes < target:
        severity = "HIGH" if avg_partition_bytes < target * 0.1 else "MEDIUM"
        signals.append(
            _signal(
                "undersized_partitions",
                severity,
                f"Average partition contains {human_bytes(avg_partition_bytes)} against a "
                f"{human_bytes(target)} target file",
                avg_partition_bytes=int(avg_partition_bytes),
                partition_count=int(raw.get("partition_count", 0)),
                avg_files_per_partition=float(storage.get("avg_files_per_partition") or 0),
            )
        )

    stats = raw.get("partition_stats") or {}
    max_rows = float(stats.get("max_rows") or 0)
    avg_rows = float(stats.get("avg_rows") or 0)
    if partition_stats_available and avg_rows > 0 and max_rows > 0:
        ratio = max_rows / avg_rows
        if ratio >= _SKEW_MEDIUM:
            signals.append(
                _signal(
                    "partition_skew",
                    "HIGH" if ratio >= _SKEW_HIGH else "MEDIUM",
                    f"Largest partition holds {ratio:.1f}x the average partition's rows",
                    max_rows=int(max_rows),
                    avg_rows=int(avg_rows),
                    ratio=round(ratio, 2),
                )
            )

    partition_count = int(raw.get("partition_count", 0))
    if partition_stats_available and partition_count <= 1:
        signals.append(
            _signal("unpartitioned", "MEDIUM", "Table exposes a single partition or none",
                    partition_count=partition_count)
        )

    if data_file_stats_available and int(raw.get("distinct_sort_orders", 0)) <= 1:
        properties = (metadata.get("table_properties") or {}).get("properties") or {}
        if not properties.get("sort-order") and not properties.get("write.distribution-mode"):
            signals.append(
                _signal("missing_sort_order", "MEDIUM",
                        "No sort order is applied across the table's data files")
            )

    delete_bytes = int(raw.get("delete_bytes", 0))
    all_bytes = total_bytes + delete_bytes
    if data_file_stats_available and delete_file_stats_available and all_bytes and delete_bytes / all_bytes > _DELETE_OVERHEAD_WARN:
        signals.append(
            _signal(
                "delete_overhead",
                "HIGH" if delete_bytes / all_bytes > 0.25 else "MEDIUM",
                f"Delete files are {100 * delete_bytes / all_bytes:.1f}% of table bytes",
                delete_bytes=delete_bytes,
            )
        )

    if data_file_stats_available and num_files > _MANIFEST_FILE_WARN:
        signals.append(
            _signal("manifest_health", "MEDIUM",
                    f"{num_files:,} data files is above the {_MANIFEST_FILE_WARN:,} "
                    "planning-cost threshold", num_data_files=num_files)
        )

    snapshots = int(raw.get("snapshot_count", 0))
    if snapshot_count_available and snapshots > _SNAPSHOT_WARN:
        signals.append(
            _signal("snapshot_retention", "LOW",
                    f"{snapshots:,} snapshots retained", snapshot_count=snapshots)
        )

    caps = (metadata.get("table_properties") or {}).get("caps_warnings") or []
    known_caps = [warning for warning in caps if warning.get("is_known_configuration")]
    custom_caps = [warning for warning in caps if not warning.get("is_known_configuration")]
    if known_caps:
        signals.append(
            _signal(
                "table_property_naming",
                "HIGH",
                f"{len(known_caps)} known Iceberg configuration propert(ies) use noncanonical "
                "casing and may be ignored",
                properties=[warning["property"] for warning in known_caps],
                canonical_properties=[warning["canonical_property"] for warning in known_caps],
                collisions=[
                    warning["property"]
                    for warning in known_caps
                    if warning["has_canonical_collision"]
                ],
            )
        )
    if custom_caps:
        signals.append(
            _signal(
                "custom_property_naming",
                "LOW",
                f"{len(custom_caps)} custom table propert(ies) use noncanonical casing",
                properties=[warning["property"] for warning in custom_caps],
            )
        )

    if patterns and patterns.get("scan_queries_analyzed", 0) >= 5:
        avg_input = float(patterns.get("avg_input_bytes") or 0)
        if total_bytes and avg_input / total_bytes > 0.8:
            signals.append(
                _signal(
                    "poor_pruning",
                    "HIGH",
                    f"Average query reads {100 * avg_input / total_bytes:.0f}% of table bytes",
                    avg_input_bytes=int(avg_input),
                )
            )

    return signals
