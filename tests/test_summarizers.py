"""Tests for the context summarizers (CU-7).

CU-7: summarize_findings must include exact_result so the DECIDE step
reasons on actual query data, not only on the LLM's paraphrase.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.context.summarizers import summarize_findings


def _finding(check_num: int = 0, exact_result: str = "count=42") -> dict:
    return {
        "check_num": check_num,
        "question": "How many files exist?",
        "verdict": "found",
        "rationale": "The file count indicates fragmentation",
        "exact_result": exact_result,
    }


class TestCU7SummarizeFindingsIncludesExactResult:
    """CU-7: exact_result must be present in summarize_findings output."""

    def test_exact_result_present_in_summary(self):
        """summarize_findings must return exact_result for each finding."""
        findings = [_finding(exact_result="avg_file_size=10MB")]
        summary = summarize_findings(findings, max_items=3)
        assert len(summary) == 1
        assert "exact_result" in summary[0], (
            "exact_result missing from summarize_findings output — "
            "DECIDE step cannot reason on real query data (RC-10)"
        )

    def test_exact_result_value_is_correct(self):
        """The exact_result value must match the finding's exact_result (truncated to 120 chars)."""
        findings = [_finding(exact_result="file_count=5000, avg_size=8MB")]
        summary = summarize_findings(findings, max_items=3)
        assert summary[0]["exact_result"] == "file_count=5000, avg_size=8MB"

    def test_exact_result_truncated_to_120_chars(self):
        """Long exact_result values are truncated consistently with rationale."""
        long_result = "x" * 200
        findings = [_finding(exact_result=long_result)]
        summary = summarize_findings(findings, max_items=3)
        assert len(summary[0]["exact_result"]) <= 120

    def test_missing_exact_result_does_not_crash(self):
        """Findings without exact_result are handled gracefully (empty string)."""
        finding = {"check_num": 0, "question": "Q?", "verdict": "found", "rationale": "R"}
        summary = summarize_findings([finding], max_items=3)
        assert "exact_result" in summary[0]
        assert summary[0]["exact_result"] == ""

    def test_existing_fields_still_present(self):
        """Adding exact_result must not remove check_num, question, verdict, rationale."""
        findings = [_finding()]
        summary = summarize_findings(findings, max_items=3)
        for field in ("check_num", "question", "verdict", "rationale", "exact_result"):
            assert field in summary[0], f"Field '{field}' missing from summarize_findings output"

    def test_max_items_still_respected(self):
        """max_items limit must still be enforced after the change."""
        findings = [_finding(check_num=i) for i in range(10)]
        summary = summarize_findings(findings, max_items=3)
        assert len(summary) == 3

    def test_empty_findings_returns_empty(self):
        assert summarize_findings([], max_items=3) == []

    def test_max_items_zero_returns_empty(self):
        findings = [_finding()]
        assert summarize_findings(findings, max_items=0) == []


if __name__ == "__main__":
    t = TestCU7SummarizeFindingsIncludesExactResult()
    tests = [
        t.test_exact_result_present_in_summary,
        t.test_exact_result_value_is_correct,
        t.test_exact_result_truncated_to_120_chars,
        t.test_missing_exact_result_does_not_crash,
        t.test_existing_fields_still_present,
        t.test_max_items_still_respected,
        t.test_empty_findings_returns_empty,
        t.test_max_items_zero_returns_empty,
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
