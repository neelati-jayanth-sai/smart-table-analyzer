"""Read the active partition spec and candidate columns from table metadata."""

from __future__ import annotations

import re
from typing import Any


def analyze_partitioning(spark, table_name: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Return the current partition spec, DDL, and viable candidate columns."""
    partition_info = {
        "current_partition_columns": [],
        "suggested_alternatives": [],
        "has_partitioning": False,
        "table_ddl": "",
        "partition_spec": "",
    }

    try:
        describe_rows = spark.sql(f"DESCRIBE EXTENDED {table_name}").collect()
        partition_cols = []
        for row in describe_rows:
            col_name = str(row.get("col_name", "")).strip()
            if col_name and col_name.startswith("Partition"):
                partition_spec = str(row.get("data_type", ""))
                if partition_spec:
                    cols = re.findall(r'\[(.*?)\]', partition_spec)
                    if cols:
                        partition_cols = [c.strip() for c in cols[0].split(',')]
                        break
        partition_info["current_partition_columns"] = partition_cols
        partition_info["has_partitioning"] = len(partition_cols) > 0
        ddl = _table_ddl(spark, table_name)
        partition_info["table_ddl"] = ddl
        partition_info["partition_spec"] = _partition_spec(ddl)

        column_analysis = metadata.get("column_analysis", {})
        if "partition_candidates" in column_analysis:
            current_set = set(col.lower() for col in partition_cols)
            alternatives = [
                candidate for candidate in column_analysis["partition_candidates"]
                if candidate["column"].lower() not in current_set
            ]
            partition_info["suggested_alternatives"] = alternatives[:5]
    except Exception as exc:
        partition_info["error"] = str(exc)
    return partition_info


def _table_ddl(spark, table_name: str) -> str:
    try:
        row = spark.sql(f"SHOW CREATE TABLE {table_name}").first()
        return str(row[0]) if row is not None else ""
    except Exception:
        return ""


def _partition_spec(ddl: str) -> str:
    match = re.search(r"PARTITIONED\s+BY\s*\(", ddl, re.IGNORECASE)
    if not match:
        return ""
    depth = 1
    start = match.end()
    for index, char in enumerate(ddl[start:], start):
        depth += (char == "(") - (char == ")")
        if depth == 0:
            return " ".join(ddl[start:index].split())
    return ""
