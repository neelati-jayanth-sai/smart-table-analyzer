"""Compute baseline health score using HealthScoreCalculator (adaptive weighted).

Seam: score(raw_metrics, query_patterns) -> dict
  raw_metrics keys: num_data_files, total_data_file_bytes, delete_bytes,
                    partition_count, snapshot_count, row_count, is_empty
  query_patterns: optional dict with avg_cpu_time_ns, avg_input_bytes,
                  total_queries_analyzed, column_usage (from IOMETEQueryPatternAdapter)
"""

from __future__ import annotations

from typing import Any

from src.calculators.health_score_calculator import HealthScoreCalculator, UsageSignals

_TARGET_FILE_BYTES = 134_217_728   # 128 MB
_SCAN_THROUGHPUT_BYTES_PER_NS = 1  # 1 GB/s = 1 byte/ns
_IDEAL_CPU_NS_PER_FILE = _TARGET_FILE_BYTES // _SCAN_THROUGHPUT_BYTES_PER_NS  # 134ms in ns
_MANIFEST_FILE_THRESHOLD = 50_000  # above this, planning time grows significantly
_SKEW_MEDIUM_RATIO = 5.0
_SKEW_HIGH_RATIO = 20.0


def score(raw_metrics: dict[str, Any],
          query_patterns: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute the adaptive health score for a table.

    Returns dict: {overall: float, weakest: list[str], dimensions: dict}
    """
    signals = _derive_usage_signals(raw_metrics, query_patterns)
    result = HealthScoreCalculator().compute_health_score(signals)

    subscores = result.subscores  # dim -> float in (0, 1]
    sorted_dims = sorted(subscores, key=subscores.__getitem__)
    weakest = sorted_dims[:3]

    dims = {d: round(subscores[d] * 100.0, 2) for d in subscores}
    dims.update({
        "row_count": raw_metrics.get("row_count", 0),
        "num_data_files": raw_metrics.get("num_data_files", 0),
        "total_data_file_bytes": raw_metrics.get("total_data_file_bytes", 0),
        "partition_count": raw_metrics.get("partition_count", 0),
        "snapshot_count": raw_metrics.get("snapshot_count", 0),
        "is_empty": bool(raw_metrics.get("is_empty", False)),
        "unavailable_metrics": list(raw_metrics.get("failed_metrics") or []),
    })

    return {
        "overall": round(result.overall_health, 2),
        "weakest": weakest,
        "dimensions": dims,
    }


def _derive_usage_signals(raw_metrics: dict[str, Any],
                           query_patterns: dict[str, Any] | None) -> UsageSignals:
    num_files = max(raw_metrics.get("num_data_files", 0), 1)
    total_bytes = raw_metrics.get("total_data_file_bytes", 0)
    delete_bytes = raw_metrics.get("delete_bytes", 0)
    partition_count = raw_metrics.get("partition_count", 0)

    wp = query_patterns or {}
    avg_cpu_ns = wp.get("avg_cpu_time_ns", 0.0)
    avg_input_bytes = wp.get("avg_input_bytes", 0.0)
    # Only trust workload signals when they come from real data-scanning queries
    has_scan_workload = wp.get("scan_queries_analyzed", 0) >= 5

    # --- file_size ---
    if has_scan_workload and avg_cpu_ns > 0:
        ideal_ns = _IDEAL_CPU_NS_PER_FILE * num_files
        u_file = min(avg_cpu_ns / ideal_ns, 5.0)
    else:
        avg_file_bytes = total_bytes / num_files if total_bytes else _TARGET_FILE_BYTES
        u_file = abs(avg_file_bytes / _TARGET_FILE_BYTES - 1.0)

    # --- scan_efficiency ---
    # Only use avg_input_bytes when it comes from queries that actually scanned storage.
    # totalInputBytes=0 means the query hit a cached plan or was metadata-only — not a
    # true read-amplification signal.
    if has_scan_workload and avg_input_bytes > 0 and total_bytes > 0:
        u_scan = min(avg_input_bytes / total_bytes, 1.0)
    else:
        col_count = len(wp.get("column_usage") or {})
        u_scan = min(col_count / 20.0, 1.0) if col_count > 0 else 0.0

    # --- delete_overhead ---
    all_bytes = total_bytes + delete_bytes
    u_delete = delete_bytes / all_bytes if all_bytes > 0 else 0.0

    # --- manifest_organization ---
    u_manifest = min(num_files / _MANIFEST_FILE_THRESHOLD, 1.0)

    # --- partition_aware ---
    # When scan data is available, use avg scan ratio as a pruning proxy:
    #   ratio near 1.0 → full-table scans → poor pruning → high signal
    #   ratio near 0.0 → narrow scans   → good pruning → low signal
    # Structural fallback: partitioned=good (0.0), unpartitioned=bad (0.5).
    # A measured distribution always takes precedence over that weak proxy:
    # merely having partitions cannot compensate for one dominant partition.
    if has_scan_workload and avg_input_bytes > 0 and total_bytes > 0:
        scan_ratio = min(avg_input_bytes / total_bytes, 1.0)
        u_partition = scan_ratio if partition_count > 1 else min(scan_ratio + 0.3, 1.0)
    else:
        u_partition = 0.0 if partition_count > 1 else 0.5

    partition_stats = raw_metrics.get("partition_stats") or {}
    max_rows = float(partition_stats.get("max_rows") or 0)
    avg_rows = float(partition_stats.get("avg_rows") or 0)
    if max_rows and avg_rows:
        skew_ratio = max_rows / avg_rows
        if skew_ratio >= _SKEW_MEDIUM_RATIO:
            skew_penalty = min(skew_ratio / _SKEW_HIGH_RATIO, 1.0)
            u_partition = max(u_partition, skew_penalty)

    return UsageSignals(
        file_size=u_file,
        scan_efficiency=u_scan,
        delete_overhead=u_delete,
        manifest_organization=u_manifest,
        partition_aware=u_partition,
    )


_HEALTH_DIMENSIONS = (
    "file_size",
    "scan_efficiency",
    "delete_overhead",
    "manifest_organization",
    "partition_aware",
)

_DIMENSION_EVIDENCE = {
    "file_size": "Average data file size vs the 128 MB target",
    "scan_efficiency": "Bytes actually scanned vs table size across the query workload",
    "delete_overhead": "Delete-file bytes as a share of total bytes",
    "manifest_organization": "Data file count vs the manifest planning threshold",
    "partition_aware": "Partition pruning effectiveness for the observed workload",
}


def explain_score(dimensions: dict[str, Any]) -> dict[str, Any]:
    """Break an overall health score into per-dimension contributions.

    The adaptive weights are recovered exactly from the stored subscores:
    s = 1/(1+u) implies u = 1/s - 1, and w_adj = 1 + u, so the same numbers the
    score was built from explain where the points went. `impact` is the points
    this dimension costs the final score; contributions sum to the overall score.
    """
    subscores = {}
    for dim in _HEALTH_DIMENSIONS:
        raw = dimensions.get(dim)
        if isinstance(raw, (int, float)) and raw > 0:
            subscores[dim] = min(float(raw) / 100.0, 1.0)

    if not subscores:
        return {"overall": 0.0, "rows": []}

    adjusted = {d: 1.0 / s for d, s in subscores.items()}  # 1 + u = 1/s
    total = sum(adjusted.values())
    rows = []
    overall = 0.0
    for dim, subscore in subscores.items():
        weight = adjusted[dim] / total
        contribution = 100.0 * weight * subscore
        overall += contribution
        rows.append(
            {
                "dimension": dim,
                "subscore": round(subscore * 100.0, 1),
                "weight": round(weight, 4),
                "contribution": round(contribution, 1),
                "impact": round(contribution - 100.0 * weight, 1),
                "evidence": _DIMENSION_EVIDENCE.get(dim, ""),
            }
        )

    rows.sort(key=lambda r: r["impact"])
    return {"overall": round(overall, 2), "rows": rows}
