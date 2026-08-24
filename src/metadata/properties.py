"""Load and validate Iceberg table properties with CAPS issue detection."""

from __future__ import annotations

from typing import Any

# Standard Iceberg reserved properties (lowercase)
RESERVED_ICEBERG_PROPERTIES = {
    "format-version",
    "uuid",
    "snapshot-count",
    "current-snapshot-id",
    "current-snapshot-summary",
    "current-snapshot-timestamp-ms",
    "current-schema",
    "default-partition-spec",
    "default-sort-order",
}


def load_table_properties(spark, table_name: str) -> dict[str, Any]:
    """Load table properties and check for CAPS issues.
    
    Returns a dict with properties and any CAPS warnings.
    """
    properties = {}
    caps_warnings = []
    
    try:
        rows = spark.sql(f"SHOW TBLPROPERTIES {table_name}").collect()
        for row in rows:
            key = str(row["key"])
            value = str(row["value"])
            
            # Check for CAPS issues in property names
            if key != key.lower():
                key_lower = key.lower()
                # Only warn if it's not a standard reserved property
                if key_lower not in RESERVED_ICEBERG_PROPERTIES:
                    caps_warnings.append({
                        "property": key,
                        "suggested": key_lower,
                        "value": value,
                        "reason": "Property names should be lowercase for Iceberg compatibility"
                    })
                # Store with lowercase key for consistency
                properties[key_lower] = value
            else:
                properties[key] = value
    except Exception as exc:
        return {"error": str(exc)}
    
    return {
        "properties": properties,
        "caps_warnings": caps_warnings,
        "has_caps_issues": len(caps_warnings) > 0
    }
