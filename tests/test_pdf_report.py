"""PDF report rendering through the public reporting seam."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from src.models import Assessment, InvestigationReport
from src.reporting import render_pdf


def test_pdf_contains_the_canonical_investigation_report_sections():
    pdf = render_pdf(_report())
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1_000
    assert "Investigation Report" in text
    assert "Executive Summary" in text
    assert "Deterministic Coverage" in text
    assert "Whole-run Review" in text


def _report() -> InvestigationReport:
    finding = {
        "check_num": 1, "question": "Are file sizes healthy?", "verdict": "found",
        "issue_state": "issue_found", "db_validated": True, "check_type": "small_files",
        "exact_result": "431 files are below the target size.", "rationale": "Metadata proves fragmentation.",
        "confidence": 0.95, "evidence_ids": ["evidence-1"],
        "validation": {"valid": True, "errors": [], "missing_ids": []},
        "sql": [{"status": "success", "query": "SELECT COUNT(*) FROM files", "execution_time_ms": 12}],
        "recommendation": "Schedule compaction after workload review.",
        "actionable_sql": "CALL catalog.system.rewrite_data_files(table => 'cat.sch.orders')",
    }
    return InvestigationReport(
        1, "pdf-qa", "cat.sch.orders", "cat", "sch", "completed", "2026-08-25", "2026-08-25",
        "123", {"overall": 72, "dimensions": {"file_health": 72}},
        {"overall": 72, "rows": [{"evidence": "files", "dimension": "file_health", "subscore": 72, "weight": 1.0, "impact": -28.0}]},
        [finding], [{"source": "iceberg", "topic_path": "maintenance", "version": "1"}], [], [],
        {"total_findings": 1, "validated_findings": 1, "total_queries": 1},
        Assessment("action_required", ["Confirmed evidence requires action."]),
        coverage=[{"module": "column_profile", "status": "completed", "reason": "complete", "evidence_ids": ["evidence-1"]}],
        final_review={"status": "completed", "outcome": "approved", "summary": "Findings are consistent."},
    )
