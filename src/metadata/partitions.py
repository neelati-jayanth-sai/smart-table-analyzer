"""Analyze current partitioning and suggest alternatives."""

from __future__ import annotations

import re
from typing import Any


def analyze_partitioning(spark, table_name: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Analyze current partitioning and suggest alternatives.
    
    Args:
        spark: Spark session
        table_name: Full table name
        metadata: Table metadata including column analysis
        
    Returns:
        Dict with current partition info and suggested alternatives
    """
    partition_info = {
        "current_partition_columns": [],
        "suggested_alternatives": [],
        "has_partitioning": False
    }
    
    try:
        # Get current partition spec from DESCRIBE EXTENDED
        describe_rows = spark.sql(f"DESCRIBE EXTENDED {table_name}").collect()
        
        # Extract partition columns
        partition_cols = []
        for row in describe_rows:
            col_name = str(row.get("col_name", "")).strip()
            if col_name and col_name.startswith("Partition"):
                # Parse partition spec (e.g., "Partition Columns: [year, month]")
                partition_spec = str(row.get("data_type", ""))
                if partition_spec:
                    # Extract column names from bracket notation
                    cols = re.findall(r'\[(.*?)\]', partition_spec)
                    if cols:
                        partition_cols = [c.strip() for c in cols[0].split(',')]
                        break
        
        partition_info["current_partition_columns"] = partition_cols
        partition_info["has_partitioning"] = len(partition_cols) > 0
        
        # Get suggested alternatives from column analysis
        column_analysis = metadata.get("column_analysis", {})
        if "partition_candidates" in column_analysis:
            # Filter out columns that are already partition columns
            current_set = set(col.lower() for col in partition_cols)
            alternatives = [
                candidate for candidate in column_analysis["partition_candidates"]
                if candidate["column"].lower() not in current_set
            ]
            partition_info["suggested_alternatives"] = alternatives[:5]  # Top 5 alternatives
            
    except Exception as exc:
        partition_info["error"] = str(exc)
    
    return partition_info
