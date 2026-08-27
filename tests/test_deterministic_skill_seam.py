"""Focused contract tests for deterministic check selection and execution."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.investigator.executors.execution import QueryExecution
from src.investigator.executors.query import QueryGeneration
from src.investigator.skills import get_skill, render


def _state(**overrides: Any) -> dict[str, Any]:
    state = {
        "investigation_id": 7,
        "table_name": "catalog.schema.orders",
        "baseline_score": {},
        "check_count": 2,
        "max_checks": 5,
        "retry_count": 0,
        "max_retries": 2,
        "step_count": 0,
        "max_steps": 20,
        "status": "checks_running",
        "current_check_type": "file_size",
        "current_question": "Are the data files too small?",
    }
    return {**state, **overrides}


class _RecordingWorkbench:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def execute_query(self, query: str) -> SimpleNamespace:
        self.queries.append(query)
        return SimpleNamespace(
            success=True,
            query=query,
            rewritten_query=query,
            rows=[{"file_count": 12, "avg_bytes": 1024}],
            schema=[],
            row_count=1,
            execution_time_ms=3,
            truncated=False,
            error=None,
            hook_result=None,
        )


class _RecordingDb:
    def __init__(self) -> None:
        self.records: list[tuple[Any, ...]] = []

    def record_query(self, *args: Any) -> None:
        self.records.append(args)

    def record_hook_violation(self, *args: Any) -> None:
        raise AssertionError("the fixed check should not trigger a hook violation")


def test_unregistered_selection_is_rejected_before_it_can_be_rendered() -> None:
    """A model-provided SQL string is not a registered executable capability."""
    assert get_skill("freeform_sql") is None
    assert get_skill("SELECT * FROM secrets") is None

    node = QueryGeneration()
    result = node.generate_sql_query(
        _state(current_check_type="freeform_sql", current_query="DROP TABLE secrets")
    )

    assert result["execution_status"] == "error"
    assert result.get("current_query") == "DROP TABLE secrets"
    assert result["query_result"]["success"] is False


def test_executor_receives_only_the_registered_template_output() -> None:
    """Injected SQL in state cannot replace the catalogued query."""
    workbench = _RecordingWorkbench()
    node = QueryGeneration()
    prepared = node.generate_sql_query(
        _state(current_query="DROP TABLE catalog.schema.orders")
    )

    execution = QueryExecution()
    execution.workbench = workbench
    execution.db = _RecordingDb()
    execution.execute_with_workbench(prepared)

    assert len(workbench.queries) == 1
    query = workbench.queries[0]
    assert query == render(get_skill("file_size"), "catalog.schema.orders")
    assert "DROP TABLE" not in query


def test_audit_record_uses_fixed_skill_template_id() -> None:
    """Audit consumers can trace execution to a checked-in template."""
    workbench = _RecordingWorkbench()
    db = _RecordingDb()
    node = QueryExecution()
    node.workbench = workbench
    node.db = db

    node.execute_with_workbench(
        QueryGeneration().generate_sql_query(_state())
    )

    assert len(db.records) == 1
    audit = db.records[0]
    assert audit[0:3] == (7, 2, "execute_skill:file_size")
    assert audit[3] == workbench.queries[0]

