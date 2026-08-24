"""Load Iceberg table properties without hiding case-sensitive configuration errors."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


_CANONICAL_PROPERTIES = {
    "format-version",
    "uuid",
    "snapshot-count",
    "current-snapshot-id",
    "current-snapshot-summary",
    "current-snapshot-timestamp-ms",
    "current-schema",
    "default-file-format",
    "default-partition-spec",
    "default-sort-order",
    "default-sort-order-id",
    "schema.name-mapping.default",
    "object-storage.enabled",
}
_CONFIGURATION_PREFIXES = (
    "commit.",
    "compatibility.",
    "gc.",
    "history.",
    "metrics.",
    "read.",
    "write.",
)


def _is_known_configuration(canonical_key: str) -> bool:
    return canonical_key in _CANONICAL_PROPERTIES or canonical_key.startswith(
        _CONFIGURATION_PREFIXES
    )


def load_table_properties(spark, table_name: str) -> dict[str, Any]:
    """Return exact DDL keys, effective lowercase keys, and casing risks.

    ``properties`` is deliberately limited to keys already written in canonical
    lowercase. ``raw_properties`` preserves what the catalog returned so a
    mixed-case key cannot appear to be an active Iceberg setting.
    """
    raw_properties: dict[str, str] = {}
    effective_properties: dict[str, str] = {}
    variants: dict[str, list[str]] = defaultdict(list)

    try:
        rows = spark.sql(f"SHOW TBLPROPERTIES {table_name}").collect()
        for row in rows:
            key, value = str(row["key"]), str(row["value"])
            raw_properties[key] = value
            canonical_key = key.lower()
            variants[canonical_key].append(key)
            if key == canonical_key:
                effective_properties[key] = value
    except Exception as exc:
        return {"error": str(exc)}

    caps_warnings = _caps_warnings(raw_properties, effective_properties, variants)
    collisions = [warning for warning in caps_warnings if warning["has_canonical_collision"]]
    return {
        "properties": effective_properties,
        "raw_properties": raw_properties,
        "caps_warnings": caps_warnings,
        "case_collisions": collisions,
        "has_caps_issues": bool(caps_warnings),
    }


def _caps_warnings(
    raw_properties: dict[str, str],
    effective_properties: dict[str, str],
    variants: dict[str, list[str]],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for key, value in raw_properties.items():
        canonical_key = key.lower()
        if key == canonical_key:
            continue
        collision = canonical_key in effective_properties
        warnings.append(
            {
                "property": key,
                "canonical_property": canonical_key,
                "value": value,
                "is_known_configuration": _is_known_configuration(canonical_key),
                "has_canonical_collision": collision,
                "case_variants": variants[canonical_key],
                "reason": _casing_reason(canonical_key, collision),
            }
        )
    return warnings


def _casing_reason(canonical_key: str, collision: bool) -> str:
    if collision:
        return (
            f"Also set as '{canonical_key}'; the mixed-case duplicate is an ignored "
            "configuration lookalike."
        )
    return (
        f"Use the canonical lowercase key '{canonical_key}'; a mixed-case key may be "
        "stored but not read as an Iceberg configuration."
    )
