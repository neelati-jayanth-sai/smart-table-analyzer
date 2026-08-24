"""Tests for snapshot auto-capture (snapshot pinning fix).

fetch_current_snapshot(spark, table_name) must:
  - Return the latest snapshot_id string when Spark succeeds
  - Return None gracefully when Spark fails or returns no rows
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.query.snapshot_pinning import fetch_current_snapshot


def _spark_returning(snapshot_id: str):
    """Spark mock that returns a single row with snapshot_id."""
    row = MagicMock()
    row.__getitem__ = lambda self, i: snapshot_id
    df = MagicMock()
    df.first.return_value = row
    spark = MagicMock()
    spark.sql.return_value = df
    return spark


def _spark_empty():
    """Spark mock that returns no rows (df.first() is None)."""
    df = MagicMock()
    df.first.return_value = None
    spark = MagicMock()
    spark.sql.return_value = df
    return spark


def _spark_failing():
    """Spark mock that raises on any sql() call."""
    spark = MagicMock()
    spark.sql.side_effect = RuntimeError("Spark connection lost")
    return spark


class TestFetchCurrentSnapshot:

    def test_returns_snapshot_id_when_spark_succeeds(self):
        spark = _spark_returning("1234567890")
        result = fetch_current_snapshot(spark, "catalog.schema.my_table")
        assert result == "1234567890", f"Expected '1234567890', got {result!r}"

    def test_returns_none_when_no_snapshots(self):
        result = fetch_current_snapshot(_spark_empty(), "catalog.schema.my_table")
        assert result is None, f"Expected None for empty table, got {result!r}"

    def test_returns_none_when_spark_fails(self):
        result = fetch_current_snapshot(_spark_failing(), "catalog.schema.my_table")
        assert result is None, f"Expected None on Spark error, got {result!r}"

    def test_queries_snapshots_metadata_table(self):
        spark = _spark_returning("99")
        fetch_current_snapshot(spark, "cat.sch.tbl")
        called_sql = spark.sql.call_args[0][0]
        assert "cat.sch.tbl.snapshots" in called_sql.lower() or "snapshots" in called_sql.lower(), (
            f"Expected query to reference .snapshots, got: {called_sql!r}"
        )

    def test_orders_by_committed_at_descending(self):
        spark = _spark_returning("99")
        fetch_current_snapshot(spark, "cat.sch.tbl")
        called_sql = spark.sql.call_args[0][0].upper()
        assert "ORDER BY" in called_sql and "DESC" in called_sql, (
            f"Expected DESC ORDER BY in query, got: {called_sql!r}"
        )


if __name__ == "__main__":
    t = TestFetchCurrentSnapshot()
    tests = [m for m in dir(t) if m.startswith("test_")]
    failed = 0
    for name in tests:
        try:
            getattr(t, name)()
            print(f"PASS  {name}")
        except Exception as e:
            print(f"FAIL  {name}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(failed)
