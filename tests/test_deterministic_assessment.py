"""Cross-seam tests for deterministic assessment evidence."""

from __future__ import annotations

from src.reporting import ReportAssembler, render_markdown
from tests.test_investigator_scenarios import build


def test_high_signal_not_found_requires_review_in_the_report(tmp_path):
    table, _, _, db, analyzer = build("partition_skew", tmp_path, max_checks=1)
    outcome = analyzer.analyze(table.name, "cat", "sch")
    report = ReportAssembler(db).assemble(outcome.investigation_id)
    markdown = render_markdown(report)

    assert report.high_severity_signals
    assert report.baseline_score["overall"] < 95.0
    assert "require review" in markdown
    assert "No confirmed problems" not in markdown
