"""Run one query through the workbench and record it in the audit trail."""

from __future__ import annotations

from src.investigator.state import InvestigationState, validate_state
from src.models.state import QueryResultState

from ._logging import _logged


class QueryExecution:
    """Mixin: execute a query, recording hook violations and failures as evidence."""

    @_logged
    def execute_with_workbench(self, state: InvestigationState) -> InvestigationState:
        validate_state(state)
        query = state.get("current_query")
        if not query:
            new_state = {**state, "execution_status": "error",
                         "query_result": QueryResultState(success=False, error="No query generated")}
            return validate_state(new_state)
        result = self.workbench.execute_query(query)
        status = "success" if result.success else "error"
        if result.hook_result and not result.hook_result.is_valid:
            status = "hook_failed"
            self.db.record_hook_violation(
                state["investigation_id"], state["check_count"], query,
                result.hook_result.hook_name, result.hook_result.error_message,
            )
        qrs = QueryResultState(**{k: getattr(result, k) for k in QueryResultState.__annotations__})
        self.db.record_query(
            state["investigation_id"], state["check_count"], "execute_query",
            result.query, result.rewritten_query, qrs, status,
            result.execution_time_ms, result.error,
        )
        return validate_state({**state, "query_result": qrs, "execution_status": status})
