"""Checks on the mock Iceberg fixtures themselves.

If the fixtures drift, every Investigator test built on them silently stops
testing what it claims to. These assert the mocks stay realistic and internally
consistent, and that the SQL evaluator answers the queries the real code emits.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.mocks import SCENARIOS, MockSpark
from tests.mocks.iceberg import MB, TARGET_FILE_BYTES, healthy_table, partition_skew_table
from tests.mocks.sql import TableStats, UnsupportedQuery, evaluate


class TestScenarioRealism:
    @pytest.mark.parametrize("name", [n for n in SCENARIOS if n != "empty"])
    def test_metadata_is_internally_consistent(self, name):
        """Row counts, file counts, and byte totals must agree across metadata tables."""
        table = SCENARIOS[name]()

        data_files = [f for f in table.files if f["content"] == 0]
        assert table.row_count == sum(f["record_count"] for f in data_files)
        assert table.row_count == sum(p["record_count"] for p in table.partitions)
        assert len(data_files) == sum(p["file_count"] for p in table.partitions)
        assert table.total_data_bytes == sum(
            p["total_data_file_size_in_bytes"] for p in table.partitions
        )

    @pytest.mark.parametrize("name", [n for n in SCENARIOS if n != "empty"])
    def test_metadata_rows_carry_real_iceberg_columns(self, name):
        table = SCENARIOS[name]()
        assert set(table.files[0]) >= {
            "content", "file_path", "file_format", "record_count",
            "file_size_in_bytes", "sort_order_id", "partition",
        }
        assert set(table.partitions[0]) >= {"partition", "record_count", "file_count"}
        assert set(table.snapshots[0]) >= {"committed_at", "snapshot_id", "operation"}
        assert len(table.history) == len(table.snapshots)

    def test_healthy_table_sits_at_the_target_file_size(self):
        table = healthy_table()
        assert 0.9 * TARGET_FILE_BYTES <= table.avg_file_bytes <= 1.5 * TARGET_FILE_BYTES

    def test_skew_scenario_has_a_dominant_partition(self):
        table = partition_skew_table()
        records = [p["record_count"] for p in table.partitions]
        assert max(records) / (sum(records) / len(records)) > 20

    def test_small_files_scenario_is_well_below_target(self):
        table = SCENARIOS["small_files"]()
        assert table.avg_file_bytes < TARGET_FILE_BYTES * 0.5
        assert table.avg_file_bytes == 6 * MB

    def test_empty_scenario_has_no_data(self):
        table = SCENARIOS["empty"]()
        assert table.row_count == 0 and not table.files and not table.partitions


class TestSqlEvaluator:
    """The evaluator must answer the exact queries the production code emits."""

    def _spark(self):
        return MockSpark(healthy_table("cat.sch.t"))

    def test_count_star_uses_the_declared_row_count(self):
        spark = self._spark()
        assert spark.sql("SELECT COUNT(*) FROM cat.sch.t").first()[0] == 120 * 1_000_000

    def test_metadata_count_with_where(self):
        spark = self._spark()
        row = spark.sql("SELECT COUNT(*) FROM cat.sch.t.files WHERE content = 0").first()
        assert row[0] == 240

    def test_coalesce_sum(self):
        spark = self._spark()
        row = spark.sql(
            "SELECT COALESCE(SUM(file_size_in_bytes),0) FROM cat.sch.t.files WHERE content!=0"
        ).first()
        assert row[0] == 0, "healthy table has no delete files"

    def test_count_distinct(self):
        spark = self._spark()
        row = spark.sql(
            "SELECT COUNT(DISTINCT sort_order_id) FROM cat.sch.t.files WHERE content=0"
        ).first()
        assert row[0] == 1

    def test_partition_aggregate_row(self):
        spark = self._spark()
        row = spark.sql(
            "SELECT MAX(record_count) AS max_rows, MIN(record_count) AS min_rows,"
            " AVG(record_count) AS avg_rows, MAX(file_count) AS max_files"
            " FROM cat.sch.t.partitions"
        ).first()
        assert row["max_rows"] == 1_000_000 and row["min_rows"] == 1_000_000
        assert row["max_files"] == 2

    def test_group_by_returns_one_row_per_group(self):
        spark = self._spark()
        rows = spark.sql(
            "SELECT file_count AS files, COUNT(*) AS partitions"
            " FROM cat.sch.t.partitions GROUP BY file_count"
        ).collect()
        assert len(rows) == 1
        assert rows[0]["files"] == 2 and rows[0]["partitions"] == 120

    def test_order_by_desc_with_limit(self):
        spark = self._spark()
        rows = spark.sql(
            "SELECT snapshot_id FROM cat.sch.t.snapshots ORDER BY committed_at DESC LIMIT 1"
        ).collect()
        assert len(rows) == 1
        assert rows[0]["snapshot_id"] == 7000000000000000003

    def test_column_cardinality_query(self):
        """The form column_analyzer emits: cardinality and null count together."""
        spark = self._spark()
        row = spark.sql(
            "SELECT COUNT(DISTINCT region), COUNT(*) - COUNT(region) FROM cat.sch.t"
        ).first()
        assert row[0] == 3, "three regions in the healthy sample"
        assert row[1] == 0, "no nulls declared"

    def test_show_tblproperties(self):
        spark = self._spark()
        properties = {r["key"]: r["value"] for r in spark.sql("SHOW TBLPROPERTIES cat.sch.t").collect()}
        assert properties["format-version"] == "2"

    def test_describe_extended_exposes_partition_columns(self):
        spark = self._spark()
        rows = spark.sql("DESCRIBE EXTENDED cat.sch.t").collect()
        partition_row = [r for r in rows if r["col_name"] == "Partition Columns"]
        assert partition_row and partition_row[0]["data_type"] == "[order_date]"

    def test_snapshot_pinning_syntax_is_tolerated(self):
        spark = self._spark()
        row = spark.sql(
            "SELECT COUNT(*) FROM cat.sch.t.files VERSION AS OF 7000000000000000003"
            " WHERE content = 0"
        ).first()
        assert row[0] == 240

    def test_unknown_table_raises_like_spark(self):
        with pytest.raises(RuntimeError, match="not found"):
            self._spark().sql("SELECT 1 FROM cat.sch.missing")

    def test_unsupported_sql_is_explicit(self):
        with pytest.raises(UnsupportedQuery):
            evaluate("SELECT a FROM t JOIN u ON t.id = u.id", [])

    def test_stats_only_apply_to_the_whole_table(self):
        """A WHERE clause must fall back to the sample rows, not declared totals."""
        rows = [{"x": 1}, {"x": 2}]
        stats = TableStats(row_count=1_000_000)
        assert evaluate("SELECT COUNT(*) FROM t", rows, stats)[0]["count"] == 1_000_000
        assert evaluate("SELECT COUNT(*) FROM t WHERE x = 1", rows, stats)[0]["count"] == 1


class TestFailureInjection:
    def test_fail_on_pattern_raises(self):
        spark = MockSpark(healthy_table("cat.sch.t"), fail_on=r"\.partitions")
        spark.sql("SELECT COUNT(*) FROM cat.sch.t.files WHERE content = 0")  # unaffected
        with pytest.raises(RuntimeError):
            spark.sql("SELECT COUNT(*) FROM cat.sch.t.partitions")

    def test_queries_and_table_reads_are_recorded(self):
        spark = MockSpark(healthy_table("cat.sch.t"))
        spark.sql("SELECT COUNT(*) FROM cat.sch.t")
        spark.table("cat.sch.t")
        assert spark.queries and spark.table_reads == ["cat.sch.t"]
