"""Only successful execution-backed findings can become report root causes."""

from __future__ import annotations

from src.database import Finding, InvestigationDb
from src.reporting import ReportAssembler, render_markdown
from src.validation import ClaimValidator


def _finding(check_num: int, evidence_ids: list[str]) -> Finding:
    return Finding(
        check_num=check_num,
        question="Did the check find an issue?",
        exact_result="A measured result was returned.",
        verdict="found",
        rationale="The measured result establishes the reported table condition.",
        evidence_ids=evidence_ids,
        issue_state="issue_found",
    )


def test_claim_requires_successful_evidence_from_the_finding_check(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-claim", "cat.sch.orders", "cat", "sch")
    db.record_query(
        investigation_id, 0, "execute_query", "SELECT 1", query_result={"value": 1},
        execution_status="success",
    )
    db.record_query(
        investigation_id, 1, "execute_query", "SELECT 2", query_result={"value": 2},
        execution_status="success",
    )

    assert ClaimValidator(db).validate(investigation_id, _finding(0, ["trail:0"])).valid
    cross_check = ClaimValidator(db).validate(investigation_id, _finding(0, ["trail:1"]))
    assert not cross_check.valid
    assert "unrelated" in " ".join(cross_check.errors)


def test_claim_cannot_be_knowledge_only_or_failed_query(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-claim", "cat.sch.orders", "cat", "sch")
    db.record_knowledge_fetch(investigation_id, 0, "iceberg", "rules", "v1")
    db.record_query(
        investigation_id, 0, "execute_query", "SELECT 1", execution_status="error",
        error_message="failed",
    )

    knowledge_only = ClaimValidator(db).validate(
        investigation_id, _finding(0, ["knowledge:iceberg/rules@v1"])
    )
    failed_query = ClaimValidator(db).validate(investigation_id, _finding(0, ["trail:0"]))
    assert not knowledge_only.valid
    assert not failed_query.valid
    assert any("successful table-query" in error for error in knowledge_only.errors)


def test_report_projection_cannot_preserve_model_validation_without_evidence(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-report", "cat.sch.orders", "cat", "sch")
    finding = _finding(0, ["trail:99"])
    finding.validated = True
    db.record_finding(
        investigation_id,
        finding,
    )
    report = ReportAssembler(db).assemble(investigation_id)
    finding = report.findings[0]

    assert finding["evidence_validated"] is False
    assert finding["validated"] is False
    assert finding["validation"]["valid"] is False


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
    assert report.assessment.state == "incomplete"


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
