"""Collection profiles keep ordinary investigations off large table data files."""

from __future__ import annotations

import re

from src.analyzer.legacy_analyzer import LegacyAnalyzer
from src.metadata.collection_profile import MetadataCollectionProfile

from tests.mocks.iceberg import SCENARIOS
from tests.mocks.spark import MockSpark


def test_fast_profile_uses_iceberg_metadata_not_base_table_scans():
    table = SCENARIOS["small_files"]()
    spark = MockSpark(table)

    context = LegacyAnalyzer(spark, MetadataCollectionProfile.from_name("fast")).collect(table.name)

    assert context.metadata["collection_profile"] == "fast"
    assert context.metadata["sample_rows"] == []
    assert context.metadata["column_analysis"] == {"status": "not_collected_in_fast_profile"}
    assert context.baseline["dimensions"]["row_count"] == table.row_count
    assert not any("COUNT(DISTINCT" in query and ".files" not in query for query in spark.queries)
    base_table_read = re.compile(rf"\bFROM\s+{re.escape(table.name)}\s*$", re.IGNORECASE)
    assert not any(base_table_read.search(query.strip()) for query in spark.queries)


def test_deep_profile_keeps_data_profiling_an_explicit_choice():
    profile = MetadataCollectionProfile.from_name("deep")

    assert profile.include_sample_rows is True
    assert profile.analyze_column_stats is True
