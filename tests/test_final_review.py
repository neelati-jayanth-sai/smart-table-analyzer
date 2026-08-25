"""Whole-run review persistence and evidence-coverage report contract."""

from __future__ import annotations

from src.analyzer import SmartTableAnalyzer
from src.database import InvestigationDb, KnowledgeStore
from src.investigator.critic import run_final_review
from src.reporting import ReportAssembler, render_markdown

from tests.mocks import MockSpark, SCENARIOS, ScriptedLLM


class ReviewLlm:
    """Small adapter proving the final-review structured output Interface."""

    def generate(self, _messages):
        return {
            "content": (
                '{"outcome":"approved","summary":"Findings are consistent.",'
                '"consistency_issues":[],"unsupported_certainty":[],'
                '"duplicate_recommendations":[],"missing_justification":[],'
                '"coverage_gaps":[]}'
            )
        }


def _analyzer(tmp_path, profile: str = "fast", spark=None):
    table = SCENARIOS["healthy"]()
    spark = spark or MockSpark(table)
    db_path = tmp_path / "investigation.db"
    db = InvestigationDb(db_path)
    analyzer = SmartTableAnalyzer(
        spark, db, ScriptedLLM(table=table.name), KnowledgeStore(db_path, repo_root=tmp_path),
        max_checks=1, metadata_profile=profile,
    )
    return table, db, analyzer


def test_structured_final_review_round_trips_through_database(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("review-run", "orders", "cat", "sch")

    review = run_final_review(ReviewLlm(), db, investigation_id)
    db.record_final_review(investigation_id, review)

    assert review["status"] == "completed"
    assert db.get_final_review(investigation_id) == review


def test_pipeline_persists_invalid_review_as_explicit_safe_fallback(tmp_path):
    table, db, analyzer = _analyzer(tmp_path)

    outcome = analyzer.analyze(table.name, "cat", "sch")

    review = db.get_final_review(outcome.investigation_id)
    assert review is not None
    assert review["status"] == "invalid"
    assert review["outcome"] == "not_assessed"
    assert review["coverage_gaps"] == []


def test_fast_coverage_is_rendered_as_not_assessed_not_clean(tmp_path):
    table, db, analyzer = _analyzer(tmp_path)
    outcome = analyzer.analyze(table.name, "cat", "sch")

    report = ReportAssembler(db).assemble(outcome.investigation_id)
    markdown = render_markdown(report)

    assert "## 7. Deterministic Coverage" in markdown
    assert "column_profile | Not assessed" in markdown
    assert "Column profiling was not assessed in Fast collection." in report.warnings


def test_deep_failed_profile_prevents_clean_assessment(tmp_path):
    table = SCENARIOS["healthy"]()
    _, db, analyzer = _analyzer(
        tmp_path,
        "deep",
        MockSpark(table, fail_on=r"`order_id`"),
    )

    outcome = analyzer.analyze(table.name, "cat", "sch")
    report = ReportAssembler(db).assemble(outcome.investigation_id)

    profile = next(entry for entry in report.coverage if entry["module"] == "column_profile")
    assert profile["status"] == "failed"
    assert report.assessment.state == "needs_review"
    assert "Deep collection failed required module" in report.assessment.reasons[0]


def test_completed_review_can_require_follow_up_for_an_otherwise_clean_run(tmp_path):
    table, db, analyzer = _analyzer(tmp_path)
    outcome = analyzer.analyze(table.name, "cat", "sch")
    db.record_final_review(
        outcome.investigation_id,
        {
            "status": "completed", "outcome": "needs_review", "summary": "Duplicate advice.",
            "consistency_issues": [], "unsupported_certainty": [],
            "duplicate_recommendations": ["Checks repeat one recommendation."],
            "missing_justification": [], "coverage_gaps": [],
        },
    )

    report = ReportAssembler(db).assemble(outcome.investigation_id)

    assert report.assessment.state == "needs_review"
    assert "Whole-run review identified" in report.assessment.reasons[0]
