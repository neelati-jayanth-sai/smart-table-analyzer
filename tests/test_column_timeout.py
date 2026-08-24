"""Tests for per-query timeout guard in analyze_columns (column timeout fix).

analyze_columns must:
  - Complete even when a column's Spark query times out
  - Mark timed-out columns with {"type": ..., "timeout": True}
  - Continue processing subsequent columns after a timeout
"""

from __future__ import annotations

import sys
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metadata.columns import analyze_columns


def _always_timeout_spark():
    """Spark mock where every sql().first() raises TimeoutError."""
    spark = MagicMock()
    spark.sql.return_value.first.side_effect = FuturesTimeoutError("query timed out")
    return spark


def _spark_with_values(cardinality: int = 100, null_count: int = 0):
    """Spark mock that returns cardinality then null_count on successive calls."""
    row_card = MagicMock()
    row_card.__getitem__ = lambda self, i: cardinality
    row_null = MagicMock()
    row_null.__getitem__ = lambda self, i: null_count

    call_count = {"n": 0}
    def _first():
        call_count["n"] += 1
        return row_card if call_count["n"] % 2 == 1 else row_null

    df = MagicMock()
    df.first.side_effect = lambda: _first()
    spark = MagicMock()
    spark.sql.return_value = df
    return spark


class TestColumnTimeout:

    def test_returns_result_even_when_all_queries_timeout(self):
        """analyze_columns must not raise even if every column query times out."""
        spark = _always_timeout_spark()
        cols = [{"name": "col_a", "type": "STRING"}, {"name": "col_b", "type": "INT"}]
        result = analyze_columns(spark, "cat.sch.tbl", cols, row_count=1000)
        assert "column_stats" in result, "Must return column_stats even on timeout"

    def test_timed_out_column_marked_with_timeout_flag(self):
        """Columns that time out must have timeout=True in their stats."""
        spark = _always_timeout_spark()
        cols = [{"name": "col_a", "type": "STRING"}]
        result = analyze_columns(spark, "cat.sch.tbl", cols, row_count=1000)
        stats = result["column_stats"].get("col_a", {})
        assert stats.get("timeout") is True, (
            f"Expected timeout=True for timed-out column, got: {stats}"
        )

    def test_continues_after_timeout(self):
        """After a timeout on col_a, col_b must still be processed."""
        # col_a: always times out; col_b: succeeds
        df_timeout = MagicMock()
        df_timeout.first.side_effect = FuturesTimeoutError()
        df_ok_card = MagicMock()
        df_ok_card.__getitem__ = lambda self, i: 500
        df_ok_null = MagicMock()
        df_ok_null.__getitem__ = lambda self, i: 0

        call_count = {"n": 0}
        def _sql(query):
            if "col_a" in query:
                return df_timeout
            call_count["n"] += 1
            df = MagicMock()
            df.first.return_value = df_ok_card if call_count["n"] % 2 == 1 else df_ok_null
            return df

        spark = MagicMock()
        spark.sql.side_effect = _sql

        cols = [{"name": "col_a", "type": "STRING"}, {"name": "col_b", "type": "INT"}]
        result = analyze_columns(spark, "cat.sch.tbl", cols, row_count=10000)
        col_a = result["column_stats"].get("col_a", {})
        col_b = result["column_stats"].get("col_b", {})
        assert col_a.get("timeout") is True, f"col_a must be marked timeout, got {col_a}"
        assert "cardinality" in col_b, f"col_b must be fully analyzed, got {col_b}"

    def test_normal_columns_still_analyzed(self):
        """Columns that succeed must still have full stats."""
        spark = _spark_with_values(cardinality=500, null_count=10)
        cols = [{"name": "status", "type": "STRING"}]
        result = analyze_columns(spark, "cat.sch.tbl", cols, row_count=10000)
        stats = result["column_stats"].get("status", {})
        assert "cardinality" in stats, f"Normal column must have cardinality, got {stats}"
        assert stats.get("timeout") is not True


if __name__ == "__main__":
    t = TestColumnTimeout()
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
