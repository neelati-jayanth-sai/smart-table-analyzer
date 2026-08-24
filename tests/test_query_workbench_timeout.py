"""Spark Connect timeout and cancellation contracts."""

from __future__ import annotations

from threading import Event

from src.query.query_workbench import QueryWorkbench


def test_timeout_interrupts_only_its_tag():
    spark = _BlockingSpark()
    workbench = QueryWorkbench(spark, hooks=[], timeout_seconds=0.01)

    result = workbench.execute_query("SELECT 1")

    assert not result.success
    assert "interrupted" in (result.error or "")
    assert spark.interrupted == spark.tags[0]
    assert spark.released.wait(1)


def test_timeout_without_connect_cancellation_is_explicit():
    spark = _BlockingSpark(supports_interrupt=False)
    workbench = QueryWorkbench(spark, hooks=[], timeout_seconds=0.01)

    result = workbench.execute_query("SELECT 1")
    spark._wait.set()

    assert not result.success
    assert "cancellation was unavailable" in (result.error or "")
    assert spark.released.wait(1)


class _BlockingSpark:
    def __init__(self, supports_interrupt: bool = True):
        self.tags: list[str] = []
        self.interrupted = ""
        self.released = Event()
        self._wait = Event()
        if not supports_interrupt:
            self.interruptTag = None

    def addTag(self, tag: str):
        self.tags.append(tag)

    def removeTag(self, tag: str):
        self.released.set()

    def interruptTag(self, tag: str):
        self.interrupted = tag
        self._wait.set()

    def sql(self, _query: str):
        self._wait.wait(1)
        raise RuntimeError("query interrupted")
