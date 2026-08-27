"""Contract tests for reusing Legacy Analyzer evidence in Investigator checks."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.context import InvestigationContext
from src.database import InvestigationDb, KnowledgeStore
from src.investigator import Investigator
from tests.mocks import ScriptedLLM


class _FailIfCalledWorkbench:
    """A cache-backed check must not regress into a second metadata query."""

    def execute_query(self, query: str) -> Any:
        raise AssertionError(f"cached check unexpectedly executed SQL: {query}")


class _RecordingWorkbench:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def execute_query(self, query: str) -> Any:
        self.queries.append(query)
        return SimpleNamespace(
            success=True,
            query=query,
            rewritten_query=query,
            rows=[{"file_count": 4, "avg_bytes": 1024}],
            schema=[],
            row_count=1,
            execution_time_ms=1,
            truncated=False,
            error=None,
            hook_result=None,
        )


def _context(*, cached: bool) -> InvestigationContext:
    """Build the compact metadata contract emitted by Legacy Analyzer."""
    metrics = {
        "num_data_files": 4,
        "total_data_file_bytes": 4096,
        "row_count": 400,
        "distinct_sort_orders": 1,
        "partition_count": 1,
        "snapshot_count": 2,
        "partition_stats": {"max_rows": 400, "avg_rows": 400},
    }
    metadata = {
        "table_name": "cat.sch.orders",
        "deterministic_metrics": metrics if cached else {},
        "files": {"columns": []},
        "partitions": {"columns": []},
        "snapshots": {"columns": []},
        "history": {"columns": []},
    }
    return InvestigationContext(
        table_name="cat.sch.orders",
        metadata=metadata,
        baseline={
            "overall": 80,
            "dimensions": {
                "is_empty": False,
                "row_count": 400,
                "num_data_files": 4,
                "partition_count": 1,
                "snapshot_count": 2,
            },
            "signals": [],
        },
    )


def _investigator(tmp_path: Path, workbench: Any) -> tuple[Investigator, InvestigationDb, int]:
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation(
        run_id="cached-skill-test",
        table_name="cat.sch.orders",
        catalog_name="cat",
        schema_name="sch",
        max_checks=1,
        snapshot_id=None,
    )
    investigator = Investigator(
        llm=ScriptedLLM(table="cat.sch.orders", plan=[("file_size", "Measure file sizes")]),
        workbench=workbench,
        knowledge_retrieval=KnowledgeStore(tmp_path / "investigation.db", repo_root=tmp_path),
        db=db,
        max_checks=1,
        max_retries_per_check=0,
    )
    return investigator, db, investigation_id


def test_file_size_uses_legacy_metrics_without_workbench(tmp_path: Path) -> None:
    """Baseline evidence is already the result of the fixed file-size read."""
    investigator, db, investigation_id = _investigator(tmp_path, _FailIfCalledWorkbench())

    result = investigator.run_investigation(
        investigation_id,
        "cat.sch.orders",
        context=_context(cached=True),
    )

    assert result.checks_completed == 1
    trail = db.list_trail(investigation_id)
    assert len(trail) == 1
    assert trail[0]["node_name"] == "execute_skill:baseline:file_size"
    assert trail[0]["query_text"] == "BASELINE_CACHE:baseline:file_size"
    assert db.list_findings(investigation_id)


def test_file_size_without_cached_metrics_runs_registered_template(tmp_path: Path) -> None:
    """Missing baseline evidence must retain the normal deterministic fallback."""
    workbench = _RecordingWorkbench()
    investigator, db, investigation_id = _investigator(tmp_path, workbench)

    result = investigator.run_investigation(
        investigation_id,
        "cat.sch.orders",
        context=_context(cached=False),
    )

    assert result.checks_completed == 1
    assert len(workbench.queries) == 1
    assert "cat.sch.orders.files" in workbench.queries[0]
    assert db.list_trail(investigation_id)
