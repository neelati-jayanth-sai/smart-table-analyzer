"""Load Iceberg/IOMETE table metadata in a single pass.

This is the ONLY place that reads table structure from Spark. Callers pass the
result around (see `InvestigationContext`) instead of re-querying — repeated
Iceberg metadata reads are the dominant avoidable cost in an investigation.
"""

from __future__ import annotations

import logging
from typing import Any

from src.query.query_workbench import _json_safe

from src.metadata.columns import analyze_columns
from src.metadata.collection_profile import MetadataCollectionProfile
from src.metadata.partitions import analyze_partitioning
from src.metadata.properties import load_table_properties

logger = logging.getLogger(__name__)

METADATA_SUFFIXES = ("files", "partitions", "history", "snapshots")

_SAMPLE_ROWS = 3


def _columns_of(spark, name: str) -> list[dict[str, str]]:
    """Return [{name, type}] for a table, or [] when it is not readable."""
    try:
        return [
            {"name": f.name, "type": f.dataType.simpleString()}
            for f in spark.table(name).schema.fields
        ]
    except Exception as exc:
        logger.info("Could not read schema for %s: %s", name, exc)
        return []


def _sample_rows(spark, table_name: str) -> list[dict[str, Any]]:
    try:
        rows = spark.table(table_name).limit(_SAMPLE_ROWS).collect()
        return [_json_safe(row.asDict(recursive=True)) for row in rows]
    except Exception as exc:
        logger.info("Could not read sample rows for %s: %s", table_name, exc)
        return []


def load_table_metadata(
    spark,
    table_name: str,
    row_count: int = 0,
    profile: MetadataCollectionProfile | None = None,
) -> dict[str, Any]:
    """Read schema, Iceberg metadata tables, and optional deep data profiling.

    Every sub-read is individually guarded: a table that does not expose
    `.partitions` still yields usable metadata for everything else.
    """
    logger.info("Loading metadata for %s", table_name)

    collection_profile = profile or MetadataCollectionProfile.from_name(None)
    metadata: dict[str, Any] = {
        "table_name": table_name,
        "collection_profile": collection_profile.name,
        "collection_contract": collection_profile.contract(),
        "collection_contract": collection_profile.contract(),
    }

    metadata["columns"] = _columns_of(spark, table_name)
    for suffix in METADATA_SUFFIXES:
        metadata[suffix] = {"columns": _columns_of(spark, f"{table_name}.{suffix}")}

    metadata["sample_rows"] = (
        _sample_rows(spark, table_name) if collection_profile.include_sample_rows else []
    )
    if collection_profile.analyze_column_stats and metadata["columns"]:
        metadata["column_analysis"] = analyze_columns(
            spark, table_name, metadata["columns"], row_count
        )
    else:
        metadata["column_analysis"] = {"status": "not_collected_in_fast_profile"}

    metadata["partition_analysis"] = analyze_partitioning(spark, table_name, metadata)
    metadata["table_properties"] = load_table_properties(
        spark, table_name, metadata["partition_analysis"].get("table_ddl", "")
    )

    return _json_safe(metadata)
