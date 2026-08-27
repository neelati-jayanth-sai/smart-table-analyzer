"""Evidence-backed candidate checks for Investigator selection."""

from __future__ import annotations

from typing import Any

SIGNAL_CHECKS = {
    "empty_table": ("empty_table", "Does the metadata confirm this table is empty?"),
    "small_files": ("file_size", "How are small data files distributed?"),
    "large_files": ("file_size", "Are large data files limiting scan parallelism?"),
    "undersized_partitions": ("partitioning", "Are partitions too small for target files?"),
    "partition_skew": ("skew", "Do partitions have material row-count skew?"),
    "unpartitioned": ("partition_suggestions", "Which columns are viable partition candidates?"),
    "missing_sort_order": ("sort", "Is file sort order absent for this workload?"),
    "delete_overhead": ("delete_overhead", "How much overhead do delete files add?"),
    "snapshot_retention": ("snapshot_retention", "Does retained snapshot history need maintenance?"),
    "table_property_naming": ("table_properties", "Are table properties configured with canonical names?"),
    "poor_pruning": ("scan_efficiency", "Does workload evidence show poor data pruning?"),
}

_FALLBACKS = (
    ("table_properties", "What table properties are configured?"),
    ("file_size", "Are data files near the target size?"),
    ("skew", "Do partitions have material skew?"),
)


def candidates(signals: list[dict[str, Any]], used: set[str]) -> list[tuple[str, str]]:
    """Return remaining candidates in deterministic severity order."""
    severity = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    ranked = sorted(signals, key=lambda signal: -severity.get(signal.get("severity", "LOW"), 1))
    selected = [SIGNAL_CHECKS[item["name"]] for item in ranked if item.get("name") in SIGNAL_CHECKS]
    options = selected or list(_FALLBACKS)
    return [item for item in options if item[0] not in used]
