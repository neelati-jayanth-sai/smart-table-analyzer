"""Bounded execution for deterministic Spark metadata observations."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import asdict, dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class QueryObservation:
    """One metadata read and the provenance required to interpret it."""

    value: Any = None
    status: str = "success"
    error: str | None = None
    timed_out: bool = False
    cancellation: str = "not_needed"

    def provenance(self) -> dict[str, Any]:
        return asdict(self)


class MetadataQueryExecutor:
    """Run one metadata read with a deadline and best-effort Spark cancellation."""

    def __init__(self, spark: Any, timeout_seconds: float):
        self._spark = spark
        self._timeout_seconds = timeout_seconds

    def execute(self, read: Callable[[], Any]) -> QueryObservation:
        tag = f"smart-table-metadata-{uuid.uuid4()}"
        worker = ThreadPoolExecutor(max_workers=1)
        future = worker.submit(self._tagged_read, tag, read)
        try:
            return QueryObservation(value=future.result(timeout=self._timeout_seconds))
        except TimeoutError:
            cancellation = self._cancel(tag)
            future.cancel()
            return QueryObservation(
                status="timed_out",
                error=f"Metadata query timed out after {self._timeout_seconds:g}s",
                timed_out=True,
                cancellation=cancellation,
            )
        except Exception as exc:
            return QueryObservation(status="failed", error=str(exc))
        finally:
            # Waiting here would defeat the deadline. The engine-level cancellation
            # above owns stopping an in-flight job when the connection supports it.
            worker.shutdown(wait=False, cancel_futures=True)

    def _tagged_read(self, tag: str, read: Callable[[], Any]) -> Any:
        api = self._tag_api()
        if api:
            api[0](tag)
        try:
            return read()
        finally:
            if api and api[1]:
                try:
                    api[1](tag)
                except Exception:
                    pass

    def _cancel(self, tag: str) -> str:
        api = self._tag_api()
        if not api or not api[2]:
            return "unavailable"
        try:
            api[2](tag)
            return "attempted"
        except Exception:
            return "failed"

    def _tag_api(self) -> tuple[Callable[[str], Any], Callable[[str], Any] | None,
                                Callable[[str], Any] | None] | None:
        direct = self._methods(self._spark, "addTag", "removeTag", "interruptTag")
        if direct:
            return direct
        try:
            context = getattr(self._spark, "sparkContext", None)
        except Exception:
            return None
        return self._methods(context, "addJobTag", "removeJobTag", "cancelJobsWithTag")

    @staticmethod
    def _methods(owner: Any, add: str, remove: str, cancel: str) -> tuple[
        Callable[[str], Any], Callable[[str], Any] | None, Callable[[str], Any] | None
    ] | None:
        add_method = getattr(owner, add, None)
        if not callable(add_method):
            return None
        remove_method = getattr(owner, remove, None)
        cancel_method = getattr(owner, cancel, None)
        return add_method, (remove_method if callable(remove_method) else None), (
            cancel_method if callable(cancel_method) else None
        )
