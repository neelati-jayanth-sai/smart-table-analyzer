"""Unit tests for StepBudget and BudgetRouter."""

from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.investigator.state import BudgetRouter, StepBudget


def test_step_budget_computes_max_steps() -> None:
    budget = StepBudget(max_checks=3, max_retries_per_check=2)
    # 3 checks * (6 + 2*2) + 5 = 3 * 10 + 5 = 35
    assert budget.max_steps == 35
    assert budget.recursion_limit == 40
    print(f"✅ StepBudget max_steps={budget.max_steps}, recursion_limit={budget.recursion_limit}")


def test_route_after_execution_success() -> None:
    state = {"execution_status": "success"}
    assert BudgetRouter.route_after_execution(state) == "success"
    print("✅ route_after_execution returns success")


def test_route_after_execution_retry_when_budget_allows() -> None:
    state = {
        "execution_status": "error",
        "retry_count": 0,
        "max_retries": 3,
        "step_count": 6,
        "max_steps": 20,
    }
    assert BudgetRouter.route_after_execution(state) == "retry"
    print("✅ route_after_execution returns retry when budget allows")


def test_route_after_execution_failed_when_retries_exhausted() -> None:
    state = {
        "execution_status": "error",
        "retry_count": 3,
        "max_retries": 3,
        "step_count": 6,
        "max_steps": 20,
    }
    assert BudgetRouter.route_after_execution(state) == "failed"
    print("✅ route_after_execution returns failed when retries exhausted")


def test_route_after_execution_failed_when_no_step_budget() -> None:
    state = {
        "execution_status": "error",
        "retry_count": 0,
        "max_retries": 3,
        "step_count": 19,
        "max_steps": 20,
    }
    # Need 2 more steps for retry, only 1 remains.
    assert BudgetRouter.route_after_execution(state) == "failed"
    print("✅ route_after_execution returns failed when no step budget for retry")


def test_check_budget_complete_by_checks() -> None:
    state = {"check_count": 3, "max_checks": 3, "step_count": 5, "max_steps": 100}
    assert BudgetRouter.check_budget(state) == "complete"
    print("✅ check_budget returns complete when checks exhausted")


def test_check_budget_complete_by_steps() -> None:
    state = {"check_count": 1, "max_checks": 3, "step_count": 50, "max_steps": 50}
    assert BudgetRouter.check_budget(state) == "complete"
    print("✅ check_budget returns complete when step budget exhausted")


def test_check_budget_continue() -> None:
    state = {"check_count": 1, "max_checks": 3, "step_count": 5, "max_steps": 100}
    assert BudgetRouter.check_budget(state) == "continue"
    print("✅ check_budget returns continue when budget remains")


def main() -> int:
    test_step_budget_computes_max_steps()
    test_route_after_execution_success()
    test_route_after_execution_retry_when_budget_allows()
    test_route_after_execution_failed_when_retries_exhausted()
    test_route_after_execution_failed_when_no_step_budget()
    test_check_budget_complete_by_checks()
    test_check_budget_complete_by_steps()
    test_check_budget_continue()
    print("\n✅ Budget tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
