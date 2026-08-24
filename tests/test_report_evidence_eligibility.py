"""Only successful execution-backed findings can become report root causes."""

from __future__ import annotations

from src.database import Finding, InvestigationDb
from src.reporting import ReportAssembler, render_markdown


def test_failed_execution_cannot_be_promoted_to_a_root_cause(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-1", "cat.sch.orders", "cat", "sch")
    db.record_baseline_score(investigation_id, 80.0, {}, [])
    db.record_query(
        investigation_id, 0, "execute_query", "SELECT 1", execution_status="error",
        error_message="simulated failure",
    )
    db.record_finding(
        investigation_id,
        Finding(
            check_num=0,
            question="Did the check find an issue?",
            exact_result="No result was returned.",
            verdict="found",
            rationale="The model incorrectly inferred a problem after the query failed.",
            evidence_ids=["trail:0"],
            recommendation="Do not run this recommendation.",
            validated=False,
            issue_state="issue_found",
        ),
    )
    db.complete_investigation(investigation_id, "completed")

    report = ReportAssembler(db).assemble(investigation_id)

    assert not report.root_causes
    assert report.assessment.state == "needs_review"


def test_partition_ddl_is_retained_in_the_report_artifact(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-2", "cat.sch.orders", "cat", "sch")
    db.record_baseline_score(
        investigation_id, 80.0, {}, [],
        {"partition_analysis": {
            "partition_spec": "days(order_date)",
            "table_ddl": "CREATE TABLE cat.sch.orders PARTITIONED BY (days(order_date))",
        }},
    )
    db.complete_investigation(investigation_id, "failed")

    report = ReportAssembler(db).assemble(investigation_id)
    markdown = render_markdown(report)

    assert report.baseline_score["metadata_evidence"]["partition_analysis"]["partition_spec"] == "days(order_date)"
    assert "CREATE TABLE cat.sch.orders" in markdown
