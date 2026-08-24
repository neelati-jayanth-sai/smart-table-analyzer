"""Generate the SQL that tests one hypothesis."""

from __future__ import annotations

from src.context import PromptProfile
from src.investigator.prompts import build_query_prompt
from src.investigator.state import InvestigationState, validate_state
from src.models.state import QueryResultState

from ._logging import _logged


class QueryGeneration:
    """Mixin: turn the current question into one executable query."""

    @_logged
    def generate_sql_query(self, state: InvestigationState) -> InvestigationState:
        validate_state(state)
        prompt_context = self.context_engine.render(PromptProfile.QUERY, state)
        response = self.llm.generate(
            [{"role": "user", "content": build_query_prompt(prompt_context, state)}]
        )
        content = response.get("content", "")
        is_valid, error_msg, query = self.validator.validate_query_response(content)

        if not is_valid:
            retry_count = state.get("retry_count", 0) + 1
            error_state = {**state, "retry_count": retry_count, "execution_status": "error"}
            error_state["query_result"] = QueryResultState(
                success=False, error=error_msg or "Failed to validate query response"
            )
            return validate_state(error_state)

        # A previous failed execution means this generation is a retry.
        retry_count = state.get("retry_count", 0)
        execution_status = state.get("execution_status")
        if execution_status and execution_status != "success":
            retry_count += 1
            execution_status = None

        return validate_state({
            **state,
            "current_query": query,
            "retry_count": retry_count,
            "execution_status": execution_status,
        })
