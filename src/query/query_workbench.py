"""Query workbench: validates, pins snapshot, executes with timeout."""

from __future__ import annotations

import base64
import datetime
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .hook_factory import create_investigation_hooks
from .query_hooks import QueryHook, ValidationResult
from .snapshot_pinning import pin_snapshot
from .tagged_execution import QueryTimeoutUnconfirmed, TaggedQueryExecutor

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryResult:
    """Structured result of a workbench query execution."""

    success: bool
    query: str | None = None
    rewritten_query: str | None = None
    rows: list[dict[str, Any]] | None = None
    schema: list[dict[str, str]] | None = None
    row_count: int | None = None
    execution_time_ms: int | None = None
    truncated: bool = False
    error: str | None = None
    hook_result: ValidationResult | None = None


def _json_safe(value: Any) -> Any:
    """Recursively convert Spark values to plain JSON-serializable primitives."""

    def _default(obj: Any) -> Any:
        if isinstance(obj, (bytes, bytearray)):
            return base64.b64encode(obj).decode("ascii")
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if np is not None and isinstance(obj, np.generic):
            return obj.item()
        return str(obj)

    return json.loads(json.dumps(value, default=_default))


class QueryWorkbench:
    """Execute read-only Spark SQL through a hook pipeline and timeout."""

    def __init__(
        self,
        spark,
        hooks: list[QueryHook] | None = None,
        snapshot_id: str | None = None,
        timeout_seconds: int = 30,
        row_limit: int = 50,
        table_name: str | None = None,
        full_count: bool = False,
        table_metadata: dict[str, Any] | None = None,
    ):
        self.spark = spark
        self.hooks = list(hooks) if hooks is not None else create_investigation_hooks()
        self.snapshot_id = snapshot_id
        self.timeout_seconds = timeout_seconds
        self.row_limit = row_limit
        self.table_name = table_name
        self.full_count = full_count
        self.table_metadata = table_metadata
        # Ground registered template SQL in the real schema, so a bad template is
        # rejected with the available column list instead of failing in Spark.
        if table_name and table_metadata:
            from .schema_grounding import SqlGroundingHook
            self.hooks.append(SqlGroundingHook(table_name=table_name, table_metadata=table_metadata))
        if table_name:
            from .target_scope import TargetTableHook
            self.hooks.append(TargetTableHook(table_name))
    def validate_query(self, query: str) -> tuple[bool, ValidationResult, str]:
        """Run query through all hooks and return (ok, last_result, rewritten)."""
        for hook in self.hooks:
            result = hook.validate(query)
            if not result.is_valid:
                logger.warning(
                    "Query blocked by hook %s: %s",
                    result.hook_name,
                    result.error_message,
                )
                return False, result, ""

        rewritten = self._apply_snapshot_pinning(query)
        return True, ValidationResult(True, "QueryWorkbench"), rewritten
    def _apply_snapshot_pinning(self, query: str) -> str:
        """Rewrite table references to use the pinned snapshot."""
        return pin_snapshot(query, self.table_name, self.snapshot_id)
    def execute_query(self, query: str) -> QueryResult:
        """Validate, rewrite, and execute the query with a timeout."""
        logger.info(
            "Query execution started table_name=%s snapshot_id=%s",
            self.table_name,
            self.snapshot_id,
        )
        ok, hook_result, rewritten = self.validate_query(query)
        if not ok:
            return QueryResult(
                success=False,
                query=query,
                rewritten_query=None,
                error=f"{hook_result.hook_name}: {hook_result.error_message}",
                hook_result=hook_result,
            )

        try:
            (rows, schema, row_count, truncated), elapsed_ms = TaggedQueryExecutor(
                self.spark, self.timeout_seconds
            ).execute(lambda: self._run_query(rewritten))
            logger.info(
                "Query execution succeeded row_count=%d elapsed_ms=%d",
                row_count,
                elapsed_ms,
            )
            return QueryResult(
                success=True,
                query=query,
                rewritten_query=rewritten,
                rows=rows,
                schema=schema,
                row_count=row_count,
                execution_time_ms=elapsed_ms,
                truncated=truncated,
            )
        except QueryTimeoutUnconfirmed:
            logger.warning("Query timeout could not be confirmed after %ss", self.timeout_seconds)
            return QueryResult(
                success=False,
                query=query,
                rewritten_query=rewritten,
                error=f"Query timeout after {self.timeout_seconds}s; cancellation was unavailable",
            )
        except TimeoutError:
            logger.warning("Query timed out after %ss and was interrupted", self.timeout_seconds)
            return QueryResult(
                success=False,
                query=query,
                rewritten_query=rewritten,
                error=f"Query timed out after {self.timeout_seconds}s and was interrupted",
            )
        except Exception as exc:
            logger.exception("Query execution failed")
            return QueryResult(
                success=False,
                query=query,
                rewritten_query=rewritten,
                error=str(exc),
            )

    def _run_query(self, query: str) -> tuple[list[dict], list[dict], int, bool]:
        cleaned = query.strip().rstrip(";")
        df = self.spark.sql(cleaned)
        limited = df.limit(self.row_limit + 1)
        collected = [_json_safe(row.asDict(recursive=True)) for row in limited.collect()]
        truncated = len(collected) > self.row_limit
        rows = collected[:self.row_limit]
        schema = _json_safe(
            [{"name": f.name, "type": str(f.dataType)} for f in limited.schema.fields]
        )
        row_count = int(df.count()) if self.full_count else len(rows)
        return rows, schema, row_count, truncated
