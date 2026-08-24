"""The catalogue of hypotheses a signal can justify testing.

Data, not logic: which measured signal makes which question worth asking. The
fallback sequence is used only when nothing fired and the LLM is unreachable.
"""

from __future__ import annotations

from typing import Any

# Signal name -> (check_type, question). Used to seed the LLM planner and as the
# deterministic fallback when it is unavailable.
SIGNAL_HYPOTHESES: dict[str, tuple[str, str]] = {
    "empty_table": (
        "empty_table",
        "Is this table genuinely empty, and does its metadata confirm no data was "
        "ever written?",
    ),
    "small_files": (
        "file_size",
        "How are small files distributed across partitions, and how much planning "
        "overhead do they add?",
    ),
    "undersized_partitions": (
        "partitioning",
        "Does the current partition transform create partitions too small to form "
        "the target file size, and would a coarser time transform preserve the "
        "observed workload pruning?",
    ),
    "large_files": (
        "file_size",
        "Are oversized data files preventing effective parallelism on scans?",
    ),
    "partition_skew": (
        "skew",
        "Which partitions dominate the table, and does that skew make partition "
        "pruning ineffective?",
    ),
    "unpartitioned": (
        "partition_suggestions",
        "Which column would partition this table effectively, based on cardinality "
        "and the observed query predicates?",
    ),
    "missing_sort_order": (
        "sort",
        "Given the workload's ORDER BY and GROUP BY columns, would a sort order "
        "improve file pruning?",
    ),
    "delete_overhead": (
        "delete_overhead",
        "How much read amplification do the delete files add, and which partitions "
        "hold them?",
    ),
    "manifest_health": (
        "manifest_organization",
        "Is the manifest layout inflating query planning time?",
    ),
    "snapshot_retention": (
        "snapshot_retention",
        "Are retained snapshots holding storage that expiry should have released?",
    ),
    "table_property_naming": (
        "table_properties",
        "Are the non-standard table property names changing how writes or "
        "maintenance behave?",
    ),
    "poor_pruning": (
        "scan_efficiency",
        "Why does the average query read most of the table — which predicates fail "
        "to prune?",
    ),
}

# Used only when no signal fired and the LLM planner is unavailable.
FALLBACK_SEQUENCE: list[tuple[str, str]] = [
    ("table_properties", "What Iceberg table properties are configured, and are any "
                         "misconfigured for this workload?"),
    ("file_size", "Are data files sized appropriately for the target file size?"),
    ("skew", "Do some partitions hold far more data than others?"),
    ("partition_suggestions", "Which columns are the strongest partition candidates "
                              "given their cardinality and null rates?"),
    ("sort", "Would a sort order improve scan efficiency for the observed workload?"),
]



def signal_hypotheses(signals: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Map fired signals to hypotheses, strongest signal first."""
    order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    ranked = sorted(signals, key=lambda s: -order.get(s.get("severity", "LOW"), 1))
    return [
        SIGNAL_HYPOTHESES[signal["name"]]
        for signal in ranked
        if signal.get("name") in SIGNAL_HYPOTHESES
    ]
