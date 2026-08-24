"""Test IOMETE query pattern adapter table reference filtering."""

import pytest
from src.metadata.query_patterns import IOMETEQueryPatternAdapter
from src.metadata.workload import QueryPatterns


class MockSparkSession:
    """Mock Spark session for testing."""
    
    class MockRow:
        def __init__(self, sql_text, performance_metrics):
            self.sql_text = sql_text
            self.performance_metrics = performance_metrics
    
    class MockResult:
        def __init__(self, rows):
            self.rows = rows
        
        def collect(self):
            return self.rows
        
        def first(self):
            return self.rows[0] if self.rows else None
    
    def __init__(self):
        self.rows = [
            self.MockRow(
                "SELECT t1.col, t2.col FROM target_table t1 JOIN other_table t2 ON t1.id = t2.id ORDER BY t2.sort_col",
                "totalInputBytes=1000,totalCpuTime=50000"
            ),
            self.MockRow(
                "SELECT col FROM target_table ORDER BY col",
                "totalInputBytes=2000,totalCpuTime=60000"
            ),
            self.MockRow(
                "SELECT t1.col, t2.col FROM target_table t1 JOIN other_table t2 ON t1.id = t2.id GROUP BY t2.group_col",
                "totalInputBytes=1500,totalCpuTime=55000"
            ),
            self.MockRow(
                "SELECT col FROM target_table GROUP BY col",
                "totalInputBytes=2500,totalCpuTime=65000"
            ),
            self.MockRow(
                "SELECT t1.col FROM target_table t1 ORDER BY t1.date_col",
                "totalInputBytes=3000,totalCpuTime=70000"
            ),
            self.MockRow(
                "SELECT col FROM target_table WHERE col > 10",
                "totalInputBytes=1000,totalCpuTime=50000"
            ),
            self.MockRow(
                "SELECT t1.col FROM target_table t1 JOIN other_table t2 ON t1.id = t2.id",
                "totalInputBytes=2000,totalCpuTime=60000"
            ),
            self.MockRow(
                "SELECT col FROM target_table ORDER BY col DESC",
                "totalInputBytes=1500,totalCpuTime=55000"
            ),
            self.MockRow(
                "SELECT col FROM target_table GROUP BY col HAVING COUNT(*) > 5",
                "totalInputBytes=2500,totalCpuTime=65000"
            ),
            self.MockRow(
                "SELECT t1.col FROM target_table t1 ORDER BY t1.date_col ASC",
                "totalInputBytes=3000,totalCpuTime=70000"
            ),
        ]
    
    def sql(self, query):
        # If it's the availability check, return a mock result
        if "SELECT 1 FROM" in query and "LIMIT 1" in query:
            return self.MockResult([self.MockRow("1", "")])
        # If it's a query for the target table, return the rows
        # The adapter queries for sql_text LIKE '%target_table%'
        if "sql_text LIKE" in query and "target_table" in query.lower():
            return self.MockResult(self.rows)
        # Otherwise return empty
        return self.MockResult([])


def test_order_by_filters_by_table_reference():
    """Test that ORDER BY columns are filtered to only include target table columns."""
    spark = MockSparkSession()
    adapter = IOMETEQueryPatternAdapter(spark)
    
    patterns = adapter.extract_patterns("target_table")
    
    # Should include 'col' and 'date_col' from target_table
    # Should NOT include 'sort_col' from other_table
    assert patterns.order_by_columns is not None
    assert "col" in patterns.order_by_columns
    assert "date_col" in patterns.order_by_columns
    assert "sort_col" not in patterns.order_by_columns


def test_group_by_filters_by_table_reference():
    """Test that GROUP BY columns are filtered to only include target table columns."""
    spark = MockSparkSession()
    adapter = IOMETEQueryPatternAdapter(spark)
    
    patterns = adapter.extract_patterns("target_table")
    
    # Should include 'col' from target_table
    # Should NOT include 'group_col' from other_table
    assert patterns.group_by_columns is not None
    assert "col" in patterns.group_by_columns
    assert "group_col" not in patterns.group_by_columns


def test_qualified_table_name():
    """Test filtering with fully qualified table names."""
    spark = MockSparkSession()
    adapter = IOMETEQueryPatternAdapter(spark)
    
    patterns = adapter.extract_patterns("catalog.schema.target_table")
    
    # Should still work with qualified names
    assert patterns.order_by_columns is not None
    assert "col" in patterns.order_by_columns
    assert "date_col" in patterns.order_by_columns
    assert "sort_col" not in patterns.order_by_columns


def test_column_usage_unaffected():
    """Test that column usage extraction still works correctly."""
    spark = MockSparkSession()
    adapter = IOMETEQueryPatternAdapter(spark)
    
    patterns = adapter.extract_patterns("target_table")
    
    # Column usage extraction should not crash
    # The actual extraction depends on qualified column references in the SQL
    assert patterns is not None
    assert patterns.total_queries_analyzed == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
