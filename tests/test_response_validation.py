"""LLM response handling: fences, malformed JSON, and status derivation.

Kept separate from the scenario suite because none of it needs Spark or a
table — these are the contracts at the LLM boundary and at the end of a run.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.investigator.investigator import _final_status
from src.investigator.prompts import ResponseValidator


class TestResponseRobustness:
    """LLMs wrap JSON in markdown fences unprompted; that must not lose a finding."""

    def test_analysis_json_in_a_fence_is_accepted(self):
        fenced = (
            '```json\n{"verdict": "found", "exact_result": "430 partitions", '
            '"rationale": "long enough rationale for the gate", "evidence_ids": ["trail:0"]}\n```'
        )
        is_valid, error, parsed = ResponseValidator.validate_analysis_response(fenced)
        assert is_valid, error
        assert parsed["verdict"] == "found"

    def test_sql_in_a_fence_is_unwrapped(self):
        is_valid, _, sql = ResponseValidator.validate_query_response(
            "```sql\nSELECT COUNT(*) FROM cat.sch.orders\n```"
        )
        assert is_valid
        assert sql == "SELECT COUNT(*) FROM cat.sch.orders"

    def test_unparseable_response_is_still_rejected(self):
        is_valid, error, _ = ResponseValidator.validate_analysis_response("not json at all")
        assert not is_valid and error

    def test_invalid_verdict_is_rejected(self):
        is_valid, error, _ = ResponseValidator.validate_analysis_response(
            '{"verdict": "probably", "exact_result": "x", "rationale": "y"}'
        )
        assert not is_valid and "verdict" in error


class TestStatusDerivation:
    """'completed' means every planned hypothesis concluded on real evidence."""

    def test_partial_conclusion_is_aborted_not_completed(self):
        findings = [{"check_num": 0, "evidence_ids": ["trail:0"]}]
        assert _final_status(findings, chains_concluded=1, chains_planned=3,
                             step_count=6, max_steps=100) == "aborted"

    def test_all_chains_concluded_is_completed(self):
        findings = [{"check_num": 0, "evidence_ids": ["trail:0"]}]
        assert _final_status(findings, chains_concluded=3, chains_planned=3,
                             step_count=18, max_steps=100) == "completed"

    def test_step_budget_exhaustion_is_completed(self):
        findings = [{"check_num": 0, "evidence_ids": ["trail:0"]}]
        assert _final_status(findings, chains_concluded=1, chains_planned=5,
                             step_count=100, max_steps=100) == "completed"

    def test_no_evidence_is_always_failed(self):
        findings = [{"check_num": 0, "evidence_ids": []}]
        assert _final_status(findings, chains_concluded=5, chains_planned=5,
                             step_count=100, max_steps=100) == "failed"
        assert _final_status([], chains_concluded=0, chains_planned=0,
                             step_count=0, max_steps=100) == "failed"


class TestExecutiveSummaryHeadlines:
    """A finding's exact_result is often a Markdown table; a bullet cannot hold one."""

    def test_markdown_table_is_flattened_to_one_line(self):
        from src.reporting.sections import _one_line

        flattened = _one_line("| files | avg_bytes |\n|---|---|\n| 3,000 | 6,291,456 |")
        assert "\n" not in flattened
        assert "files" in flattened and "3,000" in flattened
        assert "---" not in flattened

    def test_long_result_is_truncated(self):
        from src.reporting.sections import _HEADLINE_MAX, _one_line

        assert len(_one_line("x" * 500)) <= _HEADLINE_MAX

    def test_plain_result_passes_through(self):
        from src.reporting.sections import _one_line

        assert _one_line("430 partitions, max 453 MB") == "430 partitions, max 453 MB"
