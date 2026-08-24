"""Deadline-bound Spark execution with best-effort tag cancellation."""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Callable

logger = logging.getLogger(__name__)


class QueryTimeoutUnconfirmed(TimeoutError):
    """A query exceeded its deadline but the session cannot confirm cancellation."""


class TaggedQueryExecutor:
    """Run one callable with a Spark job tag and a bounded caller wait."""

    def __init__(self, spark: Any, timeout_seconds: int):
        self._spark = spark
        self._timeout_seconds = timeout_seconds

    def execute(self, operation: Callable[[], Any]) -> tuple[Any, int]:
        start = time.perf_counter()
        tag = f"investigation-query-{uuid.uuid4()}"
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(self._run_tagged, tag, operation)
        try:
            value = future.result(timeout=self._timeout_seconds)
        except TimeoutError:
            future.cancel()
            if not self._interrupt(tag):
                raise QueryTimeoutUnconfirmed from None
            raise
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return value, int((time.perf_counter() - start) * 1000)

    def _run_tagged(self, tag: str, operation: Callable[[], Any]) -> Any:
        add_tag = getattr(self._spark, "addTag", None)
        remove_tag = getattr(self._spark, "removeTag", None)
        if callable(add_tag):
            add_tag(tag)
        try:
            return operation()
        finally:
            if callable(remove_tag):
                remove_tag(tag)

    def _interrupt(self, tag: str) -> bool:
        interrupt = getattr(self._spark, "interruptTag", None)
        if not callable(interrupt):
            return False
        try:
            interrupt(tag)
            return True
        except Exception:
            logger.warning("Could not interrupt Spark query tag %s", tag, exc_info=True)
            return False
