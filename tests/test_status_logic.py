"""Tests for investigation status determination (CU-5).

CU-5: status must be 'completed' when step budget is exhausted, not 'aborted'.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _status_from_final_state(final_state: dict) -> str:
    """Mirrors the status logic in Investigator.run_investigation."""
    return "completed" if final_state["check_count"] >= final_state["max_checks"] else "aborted"


def _fixed_status_from_final_state(final_state: dict) -> str:
    """The corrected status logic (target after CU-5)."""
    is_budget_exhausted = (
        final_state["check_count"] >= final_state["max_checks"]
        or final_state["step_count"] >= final_state["max_steps"]
    )
    return "completed" if is_budget_exhausted else "aborted"


class TestCU5StatusDetermination:
    """CU-5: status logic must account for both check budget and step budget."""

    def test_completes_when_check_count_reaches_max(self):
        """Baseline: status=completed when check_count == max_checks (unchanged)."""
        state = {"check_count": 5, "max_checks": 5, "step_count": 10, "max_steps": 100}
        assert _status_from_final_state(state) == "completed"

    def test_current_logic_mislabels_step_budget_exhaustion(self):
        """Reproduce RC-7: step budget exhausted but check_count < max_checks → wrongly 'aborted'."""
        state = {"check_count": 3, "max_checks": 5, "step_count": 50, "max_steps": 50}
        # Current (broken) behaviour:
        assert _status_from_final_state(state) == "aborted", (
            "Expected current logic to produce 'aborted' — if this fails the bug is already fixed"
        )

    def test_fixed_logic_labels_step_budget_exhaustion_as_completed(self):
        """After CU-5: step budget exhausted must produce 'completed', not 'aborted'."""
        state = {"check_count": 3, "max_checks": 5, "step_count": 50, "max_steps": 50}
        assert _fixed_status_from_final_state(state) == "completed"

    def test_true_abort_still_labeled_aborted(self):
        """An investigation that exits early (neither budget hit) stays 'aborted'."""
        state = {"check_count": 2, "max_checks": 5, "step_count": 10, "max_steps": 50}
        assert _fixed_status_from_final_state(state) == "aborted"

    def test_investigator_uses_correct_condition(self):
        """After CU-5: investigator.py must check step_count in status determination."""
        import inspect
        from src.investigator.investigator import Investigator
        src = inspect.getsource(Investigator.run_investigation)
        assert "step_count" in src and "max_steps" in src, (
            "investigator.py does not check step_count in status logic — CU-5 not applied"
        )


if __name__ == "__main__":
    t = TestCU5StatusDetermination()
    tests = [
        t.test_completes_when_check_count_reaches_max,
        t.test_current_logic_mislabels_step_budget_exhaustion,
        t.test_fixed_logic_labels_step_budget_exhaustion_as_completed,
        t.test_true_abort_still_labeled_aborted,
        t.test_investigator_uses_correct_condition,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as e:
            print(f"FAIL  {test.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(failed)
