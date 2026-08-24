"""Iceberg metadata collection.

Everything that reads table structure from Spark lives here, and it is read
exactly once per investigation — see `loader.load_table_metadata`.
"""

from .columns import analyze_columns
from .collection_profile import MetadataCollectionProfile
from .loader import load_table_metadata
from .partitions import analyze_partitioning
from .properties import load_table_properties

__all__ = [
    "analyze_columns",
    "MetadataCollectionProfile",
    "analyze_partitioning",
    "load_table_metadata",
    "load_table_properties",
]
