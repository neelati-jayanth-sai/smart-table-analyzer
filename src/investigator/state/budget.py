"""Step budget and graph routing for bounded investigation execution."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.state import InvestigationState


@dataclass(frozen=True)
class StepBudget:
    """Compute the maximum graph steps from check and retry limits."""

    max_checks: int
    max_retries_per_check: int
    padding: int = 5

    @property
    def max_steps(self) -> int:
        # Nominal 6 nodes per check: decide, fetch, generate, execute, analyze, compact.
        # Each retry adds 2 nodes: regenerate, re-execute.
        per_check = 6 + 2 * self.max_retries_per_check
        return self.max_checks * per_check + self.padding

    @property
    def recursion_limit(self) -> int:
        return self.max_steps + self.padding


class BudgetRouter:
    """Route LangGraph edges using step, retry, and check budgets from state."""

    @staticmethod
    def route_after_execution(state: InvestigationState) -> str:
        status = state.get("execution_status", "error")
        if status == "success":
            return "success"
        # Treat hook failures as retryable errors
        if status in ("error", "hook_failed"):
            if _has_retry_budget(state):
                return "retry"
        return "failed"

    @staticmethod
    def check_budget(state: InvestigationState) -> str:
        if state.get("check_count", 0) >= state.get("max_checks", 0):
            return "complete"
        if state.get("step_count", 0) >= state.get("max_steps", 0):
            return "complete"
        return "continue"


def _has_retry_budget(state: InvestigationState) -> bool:
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 0)
    step_count = state.get("step_count", 0)
    max_steps = state.get("max_steps", 0)
    if retry_count >= max_retries:
        return False
    # A retry needs room for generate + execute.
    return step_count + 2 <= max_steps
