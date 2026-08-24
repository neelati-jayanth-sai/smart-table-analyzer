"""Tests for partition capacity evidence and DDL metadata."""

from __future__ import annotations

from src.analyzer.signals import TARGET_FILE_BYTES, detect_signals
from src.metadata.partitions import analyze_partitioning


def test_undersized_partition_signal_carries_measured_capacity():
    raw = {
        "num_data_files": 118,
        "total_data_file_bytes": 19_503_617,
        "partition_count": 118,
        "partition_storage": {
            "avg_partition_bytes": 165_284.89,
            "avg_files_per_partition": 1,
        },
    }

    signals = detect_signals(raw, {}, None)
    signal = next(item for item in signals if item["name"] == "undersized_partitions")

    assert signal["severity"] == "HIGH"
    assert signal["metrics"] == {
        "avg_partition_bytes": 165_284,
        "partition_count": 118,
        "avg_files_per_partition": 1.0,
    }
    assert TARGET_FILE_BYTES / raw["partition_storage"]["avg_partition_bytes"] > 100


def test_partition_metadata_includes_ddl_and_transform():
    metadata = {"column_analysis": {"partition_candidates": []}}
    result = analyze_partitioning(_Spark(), "cat.sch.orders", metadata)

    assert result["current_partition_columns"] == ["order_date"]
    assert result["table_ddl"].startswith("CREATE TABLE cat.sch.orders")
    assert result["partition_spec"] == "days(order_date)"


class _Row:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, index):
        return self._values[index]

    def get(self, key, default=None):
        return self._values.get(key, default)


class _Frame:
    def __init__(self, rows):
        self._rows = rows

    def collect(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _Spark:
    def sql(self, query):
        if query.startswith("DESCRIBE EXTENDED"):
            return _Frame([_Row({"col_name": "Partition Columns", "data_type": "[order_date]"})])
        return _Frame([_Row(["CREATE TABLE cat.sch.orders USING iceberg PARTITIONED BY (days(order_date))"])])
