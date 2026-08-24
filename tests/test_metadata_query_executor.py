"""Focused coverage for deadline and provenance on metadata reads."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.metrics import _timeout_seconds, collect_raw_metrics
from src.metadata.query_executor import MetadataQueryExecutor
from tests.mocks import MockSpark
from tests.mocks.iceberg import healthy_table


class TaggedSpark:
    def __init__(self):
        self.started = threading.Event()
        self.cancelled = threading.Event()
        self.added: list[str] = []
        self.removed: list[str] = []
        self.interrupted: list[str] = []

    def addTag(self, tag: str) -> None:
        self.added.append(tag)
        self.started.set()

    def removeTag(self, tag: str) -> None:
        self.removed.append(tag)

    def interruptTag(self, tag: str) -> None:
        self.interrupted.append(tag)
        self.cancelled.set()


class SlowSnapshotSpark(MockSpark):
    def sql(self, query: str):
        if ".snapshots" in query:
            time.sleep(0.05)
        return super().sql(query)


def test_metadata_timeout_defaults_to_five_minutes_and_supports_override(monkeypatch):
    monkeypatch.delenv("METADATA_QUERY_TIMEOUT_SECONDS", raising=False)
    assert _timeout_seconds(None) == 300.0

    monkeypatch.setenv("METADATA_QUERY_TIMEOUT_SECONDS", "45")
    assert _timeout_seconds(None) == 45.0


def test_deadline_cancels_a_tagged_spark_query():
    spark = TaggedSpark()
    result = MetadataQueryExecutor(spark, 0.001).execute(
        lambda: (spark.started.wait(0.05), spark.cancelled.wait(1))[1]
    )

    assert result.status == "timed_out"
    assert result.timed_out is True
    assert result.cancellation == "attempted"
    assert spark.added and spark.interrupted == spark.added


def test_collector_records_timeout_provenance_without_losing_other_metrics():
    table = healthy_table("cat.sch.orders")
    metrics = collect_raw_metrics(SlowSnapshotSpark(table), table.name, query_timeout_seconds=0.001)

    assert metrics["num_data_files"] == 240
    assert metrics["failed_metrics"] == ["snapshot_count"]
    assert metrics["timed_out_metrics"] == ["snapshot_count"]
    assert metrics["cancelled_metrics"] == []
    observation = metrics["metric_provenance"]["snapshot_count"]
    assert observation["status"] == "timed_out"
    assert observation["cancellation"] == "unavailable"


def test_collector_records_spark_failure_provenance():
    table = healthy_table("cat.sch.orders")
    metrics = collect_raw_metrics(MockSpark(table, fail_on=r"AS snapshot_count"), table.name)

    observation = metrics["metric_provenance"]["snapshot_count"]
    assert observation["status"] == "failed"
    assert observation["timed_out"] is False
    assert "simulated Spark failure" in observation["error"]
