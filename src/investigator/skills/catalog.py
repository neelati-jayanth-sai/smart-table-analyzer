"""Allowlisted Investigator checks and compatibility aliases."""

from __future__ import annotations

from .models import CheckSkill, CheckTemplate


def _skill(identifier: str, purpose: str, interpretation: str, filename: str, *columns: str) -> CheckSkill:
    return CheckSkill(identifier, purpose, CheckTemplate(identifier, filename, columns), interpretation)


_SKILLS = (
    _skill("empty_table", "Confirm whether a table has data files.", "Zero files and rows confirms an empty table.", "empty_table.sql", "file_count", "row_count"),
    _skill("file_size", "Measure data-file size distribution.", "Compare average and extremes with the configured target.", "file_size.sql", "file_count", "avg_bytes"),
    _skill("skew", "Measure partition row-count skew.", "Compare maximum partition rows with the average.", "partition_skew.sql", "partition_count", "max_rows"),
    _skill("partitioning", "Measure partition capacity.", "Compare average partition bytes with target file capacity.", "partition_size.sql", "partition_count", "avg_bytes"),
    _skill("partition_suggestions", "Measure candidate-column cardinality evidence.", "Use cached column evidence; this confirms table scale.", "partition_candidates.sql", "file_count"),
    _skill("sort", "Measure whether data files have a sort order.", "Zero sort orders means no declared file sort order.", "sort_order.sql", "sort_orders", "file_count"),
    _skill("delete_overhead", "Measure delete-file overhead.", "Compare delete files and bytes with data-file evidence.", "delete_overhead.sql", "delete_files", "delete_bytes"),
    _skill("snapshot_retention", "Measure retained snapshot history.", "Large retained history warrants expiry review.", "snapshot_history.sql", "snapshot_count"),
    _skill("table_properties", "Read configured table properties.", "Compare keys with canonical Iceberg property names.", "table_properties.sql", "key", "value"),
    _skill("scan_efficiency", "Measure file-level scan footprint.", "Compare data bytes with cached workload input bytes.", "scan_efficiency.sql", "file_count", "data_bytes"),
)

_BY_ID = {skill.identifier: skill for skill in _SKILLS}


def get_skill(identifier: str) -> CheckSkill | None:
    """Return a registered skill; unregistered LLM output is never executable."""
    return _BY_ID.get(identifier)


def registered_check_ids() -> tuple[str, ...]:
    return tuple(_BY_ID)
