"""Cross-seam tests for report-backed dashboard projections."""

from __future__ import annotations

import json

from src.dashboard import InvestigationReportStore, RunIndex, default_run_index
from src.dashboard.view_models import finding_rows, signal_rows
from src.reporting import ReportAssembler
from tests.test_investigator_scenarios import build


def test_skew_report_projects_one_non_clean_assessment(tmp_path):
    table, _, _, db, analyzer = build("partition_skew", tmp_path, max_checks=1)
    outcome = analyzer.analyze(table.name, "cat", "sch")

    report = ReportAssembler(db).assemble(outcome.investigation_id)
    rows = finding_rows(report)
    signals = signal_rows(report)

    assert report.assessment.state == "needs_review"
    assert rows[0]["status"] == "Needs review"
    assert signals[0]["actual"].endswith("largest / average")
    assert signals[0]["threshold"] == "20× requires review"


def test_legacy_baseline_cannot_be_projected_as_clean(tmp_path):
    table, _, _, db, analyzer = build("healthy", tmp_path, max_checks=1)
    outcome = analyzer.analyze(table.name, "cat", "sch")
    investigation = db.get_investigation(outcome.investigation_id)
    baseline = dict(investigation.baseline_score or {})
    baseline.pop("assessment_version", None)
    with db._connect() as conn:
        conn.execute(
            "UPDATE investigations SET baseline_score_json = ? WHERE investigation_id = ?",
            (json.dumps(baseline), outcome.investigation_id),
        )

    report = ReportAssembler(db).assemble(outcome.investigation_id)

    assert report.assessment.state == "incomplete"
    assert "predates deterministic assessment provenance" in report.assessment.reasons[0]


def test_store_defaults_history_to_latest_run_and_fingerprints_report(tmp_path):
    table, _, _, db, analyzer = build("healthy", tmp_path, max_checks=1)
    first = analyzer.analyze(table.name, "cat", "sch")
    second = analyzer.analyze(table.name, "cat", "sch")
    store = InvestigationReportStore(db.db_path)

    runs = store.list_runs()
    report = store.get_report(runs[0])

    assert runs[0].investigation_id == second.investigation_id
    assert runs[1].investigation_id == first.investigation_id
    assert len(store.fingerprint(report)) == 12


def test_store_prefers_latest_report_artifact_and_recovers_snapshot(tmp_path):
    table, _, _, db, _ = build("healthy", tmp_path, max_checks=1)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    artifact = {
        "investigation_id": 99,
        "run_id": "production-run",
        "table_name": table.name,
        "catalog_name": "cat",
        "schema_name": "sch",
        "status": "completed",
        "started_at": "2026-08-24 10:00:00",
        "completed_at": "2026-08-24 10:11:00",
        "baseline_score": {"overall": 83.0, "dimensions": {}},
        "score_explanation": {},
        "findings": [{
            "check_num": 0,
            "verdict": "found",
            "issue_state": "needs_review",
            "validation": {"valid": True, "errors": [], "missing_ids": []},
            "sql": [{"query": "SELECT 1 VERSION AS OF 987654", "status": "success"}],
        }],
        "knowledge_references": [],
        "hook_violations": [],
        "summary": {"total_findings": 1, "validated_findings": 1},
    }
    (reports_dir / "production.json").write_text(json.dumps(artifact), encoding="utf-8")
    store = InvestigationReportStore(db.db_path, reports_dir)

    run = store.list_runs()[0]
    report = store.get_report(run)

    assert run.source == "report artifact"
    assert report.snapshot_id == "987654"
    assert report.assessment.state == "incomplete"


def test_dashboard_defaults_to_completed_database_run_before_historic_artifact():
    historic = RunIndex(
        investigation_id=7,
        run_id="historic",
        table_name="cat.sch.orders",
        lifecycle_state="completed",
        started_at="2026-08-24 10:00:00",
        completed_at="2026-08-24 10:11:00",
        source="report artifact",
    )
    current = RunIndex(
        investigation_id=8,
        run_id="current",
        table_name="cat.sch.orders",
        lifecycle_state="completed",
        started_at="2026-08-23 10:00:00",
        completed_at="2026-08-23 10:11:00",
        source="database",
    )

    assert default_run_index([historic, current]) == 1
    assert default_run_index([historic, current], preferred_id=7) == 0
