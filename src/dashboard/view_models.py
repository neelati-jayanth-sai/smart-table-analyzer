"""Stable dashboard projections of a finalized investigation report."""

from __future__ import annotations

from typing import Any

from src.models import InvestigationReport

from ui_metadata import CHECK_METADATA, CHECK_METADATA_DEFAULT

_PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Needs Review": 3, "None": 4}


def finding_rows(report: InvestigationReport) -> list[dict[str, Any]]:
    """Project findings for display without deriving a table-level assessment."""
    rows = [_finding_row(report, finding) for finding in report.findings]
    return sorted(rows, key=lambda row: (_PRIORITY_ORDER[row["priority"]], row["check_num"]))


def signal_rows(report: InvestigationReport) -> list[dict[str, str]]:
    """Expose measured signals with their operating threshold where known."""
    return [_signal_row(signal) for signal in report.baseline_score.get("signals", [])]


def _finding_row(report: InvestigationReport, finding: dict[str, Any]) -> dict[str, Any]:
    meta = CHECK_METADATA.get(finding.get("check_type"), CHECK_METADATA_DEFAULT)
    status = _finding_status(report, finding)
    priority = meta["priority"] if status == "Issue found" else "Needs Review"
    if status == "Clean":
        priority = "None"
    return {
        "check_num": finding["check_num"],
        "title": meta["title"],
        "priority": priority,
        "status": status,
        "finding": finding,
        "expected": meta["expected"],
        "risk": meta["risk"],
    }


def _finding_status(report: InvestigationReport, finding: dict[str, Any]) -> str:
    if report.assessment.state == "incomplete":
        return "Incomplete"
    if not finding.get("db_validated") or not finding["validation"]["valid"]:
        return "Needs review"
    if finding.get("check_type") in report.assessment.required_review_checks:
        return "Needs review"
    if finding.get("verdict") == "found" and finding.get("issue_state") == "issue_found":
        return "Issue found"
    if finding["verdict"] in {"inconclusive", "could_not_verify"}:
        return "Needs review"
    return "Clean"


def _signal_row(signal: dict[str, Any]) -> dict[str, str]:
    metrics = signal.get("metrics") or {}
    name = signal.get("name", "measurement")
    actual, threshold = _signal_measurement(name, metrics)
    return {
        "signal": name.replace("_", " ").title(),
        "severity": signal.get("severity", "unknown").title(),
        "actual": actual or signal.get("detail", "Not recorded"),
        "threshold": threshold or "Operating guidance",
        "detail": signal.get("detail", ""),
    }


def _signal_measurement(name: str, metrics: dict[str, Any]) -> tuple[str, str]:
    if name == "partition_skew":
        return f"{metrics.get('ratio', 'n/a')}× largest / average", "20× requires review"
    if name == "small_files":
        return _megabytes(metrics.get("avg_file_bytes")), "67 MB (50% of 134 MB target)"
    if name == "large_files":
        return _megabytes(metrics.get("avg_file_bytes")), "268 MB (2× 134 MB target)"
    if name == "delete_overhead":
        return _megabytes(metrics.get("delete_bytes")), "More than 10% of table bytes"
    if name == "manifest_health":
        count = metrics.get("num_data_files")
        actual = f"{count:,} data files" if isinstance(count, int) else "n/a"
        return actual, "10,000 data files"
    if name == "snapshot_retention":
        return f"{metrics.get('snapshot_count', 'n/a')} snapshots", "100 snapshots"
    if name == "poor_pruning":
        return _megabytes(metrics.get("avg_input_bytes")), "More than 80% of table bytes scanned"
    return "", ""


def _megabytes(value: Any) -> str:
    return f"{float(value) / 1_000_000:.1f} MB" if isinstance(value, (int, float)) else "n/a"
