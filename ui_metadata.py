"""Presentation metadata for the Streamlit dashboard.

Display labels only. Verdicts, priorities, and recommendations come from the
Investigator; nothing here decides whether a table has a problem.
"""

CHECK_METADATA_DEFAULT = {
    "title": "Investigation Check",
    "priority": "Medium",
    "expected": "No anomaly against Iceberg operating guidance.",
    "risk": "Unreviewed table behaviour.",
    "benefit": "Confirms or rules out a suspected problem.",
}

CHECK_METADATA = {
    "table_properties": {
        "title": "Table Properties",
        "priority": "Medium",
        "expected": "Iceberg properties set to team standards, names lowercase.",
        "risk": "Misconfigured properties silently disable compaction or retention.",
        "benefit": "Correct write targets and maintenance behaviour.",
    },
    "column_analysis": {
        "title": "Column Cardinality",
        "priority": "Low",
        "expected": "Partition candidates have moderate cardinality and few nulls.",
        "risk": "Partitioning on the wrong column fragments or skews the table.",
        "benefit": "Grounds partition choices in real distribution data.",
    },
    "partition_suggestions": {
        "title": "Partition Strategy",
        "priority": "High",
        "expected": "Partition columns match the dominant query predicates.",
        "risk": "Queries scan the whole table because pruning never applies.",
        "benefit": "Fewer files scanned per query.",
    },
    "skew": {
        "title": "Partition Skew",
        "priority": "High",
        "expected": "Partition sizes within one order of magnitude of each other.",
        "risk": "A few huge partitions dominate runtime and stall parallelism.",
        "benefit": "Balanced scan times and predictable query cost.",
    },
    "file_size": {
        "title": "File Sizing",
        "priority": "High",
        "expected": "Average data file size near the 128 MB target.",
        "risk": "Small files inflate planning time and manifest size.",
        "benefit": "Lower planning overhead and faster scans.",
    },
    "sort": {
        "title": "Sort Order",
        "priority": "Medium",
        "expected": "Sort order aligned with common ORDER BY / GROUP BY columns.",
        "risk": "Poor data clustering forces wide scans.",
        "benefit": "Better file pruning through min/max statistics.",
    },
    "delete_overhead": {
        "title": "Delete Files",
        "priority": "Medium",
        "expected": "Delete files a small fraction of total bytes.",
        "risk": "Merge-on-read overhead grows on every query.",
        "benefit": "Cheaper reads after compaction.",
    },
    "manifest_organization": {
        "title": "Manifest Health",
        "priority": "Medium",
        "expected": "Manifest count proportional to data file count.",
        "risk": "Manifest bloat slows query planning.",
        "benefit": "Faster planning through rewritten manifests.",
    },
}

_STATUS_COLORS = {
    "Issue Found": "red",
    "Healthy": "green",
    "Unvalidated": "orange",
    "Could Not Verify": "gray",
    "Inconclusive": "orange",
}


def get_status(check_type: str, verdict: str, rationale: str, validated) -> str:
    """Map a finding's verdict and validation state to a display status."""
    if verdict == "could_not_verify":
        return "Could Not Verify"
    if verdict == "inconclusive":
        return "Inconclusive"
    if not validated:
        return "Unvalidated"
    return "Issue Found" if verdict == "found" else "Healthy"


def get_status_color(status: str) -> str:
    return _STATUS_COLORS.get(status, "gray")


def get_priority(
    check_type: str,
    verdict: str,
    status: str,
    base_priority: str,
    recommendation: str | None = None,
) -> str:
    """A check only carries its priority when it actually found something."""
    if status == "Issue Found":
        return base_priority
    if status in ("Could Not Verify", "Inconclusive", "Unvalidated"):
        return "Needs Review"
    return "None"
