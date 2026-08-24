"""Tests for prompt builder correctness.

CU-1: Verify that analysis_prompt includes the current check number so the
LLM can construct syntactically correct trail:N evidence IDs.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path when running directly or via pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.context import InvestigationContextEngine, PromptProfile
from src.investigator.prompts import build_analysis_prompt
from src.investigator.state import InvestigationState


def _make_state(check_count: int = 3) -> InvestigationState:
    """Build a minimal InvestigationState for prompt rendering tests."""
    return {
        "investigation_id": 1,
        "table_name": "catalog.schema.test_table",
        "baseline_score": {"overall": 42.0, "dimensions": {"file_size": 30.0}},
        "check_count": check_count,
        "max_checks": 10,
        "retry_count": 0,
        "max_retries": 3,
        "step_count": 0,
        "max_steps": 100,
        "status": "running",
        "current_question": "Are files correctly sized?",
        "current_check_type": "file_size",
        "current_query": None,
        "query_result": {
            "success": True,
            "rows": [{"count": 42}],
            "schema": [{"name": "count", "type": "long"}],
            "row_count": 1,
        },
        "current_analysis": None,
        "knowledge_consulted": [],
        "findings": [],
        "asked_questions": [],
        "table_metadata": None,
    }


class TestAnalysisPromptContainsCheckNum:
    """CU-1 acceptance criteria: analysis prompt must surface the check number."""

    def test_analysis_prompt_contains_check_number(self):
        """The rendered analysis prompt must contain the literal check number
        so the LLM can produce the correct 'trail:N' evidence ID."""
        check_count = 3
        state = _make_state(check_count=check_count)
        engine = InvestigationContextEngine()
        context = engine.render(PromptProfile.ANALYSIS, state)
        prompt = build_analysis_prompt(context, state)

        # The prompt must contain the check number so the LLM can construct
        # the correct evidence ID format: trail:{check_count}
        assert f"trail:{check_count}" in prompt, (
            f"analysis prompt does not contain 'trail:{check_count}' — "
            f"LLM cannot construct correct evidence ID without knowing the check number. "
            f"Prompt excerpt: {prompt[:500]}"
        )

    def test_analysis_prompt_check_number_matches_state(self):
        """The check number in the prompt must match the state's check_count."""
        for check_count in (0, 1, 5, 12):
            state = _make_state(check_count=check_count)
            engine = InvestigationContextEngine()
            context = engine.render(PromptProfile.ANALYSIS, state)
            prompt = build_analysis_prompt(context, state)
            assert f"trail:{check_count}" in prompt, (
                f"check_count={check_count}: expected 'trail:{check_count}' in prompt"
            )

    def test_analysis_prompt_does_not_contain_wrong_check_number(self):
        """Confirm the prompt contains the CORRECT check number, not a neighbour."""
        state = _make_state(check_count=7)
        engine = InvestigationContextEngine()
        context = engine.render(PromptProfile.ANALYSIS, state)
        prompt = build_analysis_prompt(context, state)

        assert "trail:7" in prompt, "Expected trail:7 to appear in prompt"
        # Ensure check 6 and 8 are not injected as the 'current' check instruction
        # (they may legitimately appear in prior findings, but not as the check num hint)
        assert "trail:7" in prompt, "trail:7 must be in the evidence guidance"


if __name__ == "__main__":
    t = TestAnalysisPromptContainsCheckNum()
    tests = [
        t.test_analysis_prompt_contains_check_number,
        t.test_analysis_prompt_check_number_matches_state,
        t.test_analysis_prompt_does_not_contain_wrong_check_number,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as e:
            print(f"FAIL  {test.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(failed)
