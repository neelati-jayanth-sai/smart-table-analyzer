"""Prepare a fixed query for one registered deterministic skill."""

from __future__ import annotations

from src.investigator.skills import CheckPreparationError, prepare
from src.investigator.skills.baseline import result_for
from src.investigator.state import InvestigationState, validate_state
from src.models.state import QueryResultState

from ._logging import _logged


class QueryGeneration:
    """Mixin: turn an allowlisted check selection into executable SQL.

    The LLM may select ``current_check_type`` while planning. It never supplies
    SQL: this module resolves the catalogued template at the execution seam.
    """

    @_logged
    def generate_sql_query(self, state: InvestigationState) -> InvestigationState:
        validate_state(state)
        check_type = state.get("current_check_type") or ""
        cached = result_for(check_type, state.get("table_metadata"))
        if cached is not None:
            return validate_state({
                **state, "current_query": None, "execution_status": "prepared",
                "current_template_id": f"baseline:{check_type}",
                "cached_check_result": QueryResultState(**cached),
            })
        try:
            prepared = prepare(check_type, state["table_name"])
        except (KeyError, CheckPreparationError) as exc:
            return _error(state, str(exc))
        return validate_state({
            **state, "current_query": prepared.query, "execution_status": "prepared",
            "retry_count": state.get("retry_count", 0),
            "current_template_id": prepared.identifier,
            "cached_check_result": None,
        })


def _error(state: InvestigationState, message: str) -> InvestigationState:
    return validate_state({
        **state,
        "execution_status": "error",
        "query_result": QueryResultState(success=False, error=message),
    })
