"""Recommendation and appendix builders for an investigation report."""

from __future__ import annotations

from src.models import InvestigationReport


def recommendations(report: InvestigationReport) -> list[str]:
    """Render actions only for validated, confirmed root causes."""
    items = report.recommendations
    if not items:
        return ["No evidence-backed recommendation. Do not act on an unvalidated finding."]

    lines: list[str] = []
    for finding in items:
        lines += [f"### {finding.get('check_type') or 'recommendation'}", "", finding["recommendation"], ""]
        lines.append(f"Backed by: {', '.join(finding['evidence_ids'])}")
        if finding.get("alternatives"):
            lines += ["", "Alternatives considered:"]
            lines += [f"- {alternative}" for alternative in finding["alternatives"]]
        if finding.get("actionable_sql"):
            lines += [
                "",
                "Proposed SQL — manual review required; it was not executed by this tool.",
                "```sql",
                finding["actionable_sql"].strip(),
                "```",
            ]
        lines.append("")
    return lines


def appendix(report: InvestigationReport) -> list[str]:
    """Render run metadata and the raw baseline dimensions."""
    baseline = report.baseline_score or {}
    dimensions = baseline.get("dimensions") or {}
    lines = [
        f"- Investigation ID: {report.investigation_id}",
        f"- Run ID: {report.run_id}",
        f"- Catalog / schema: {report.catalog_name} / {report.schema_name}",
        f"- Started: {report.started_at}",
        f"- Completed: {report.completed_at or 'n/a'}",
        f"- Overall health score: {baseline.get('overall', 'n/a')}",
        "",
        "Table metrics:",
    ]
    lines += [f"  - {key}: {value}" for key, value in sorted(dimensions.items())]
    partition = (baseline.get("metadata_evidence") or {}).get("partition_analysis") or {}
    if partition:
        lines += ["", "Partition metadata evidence:"]
        if partition.get("partition_spec"):
            lines.append(f"  - Active partition spec: `{partition['partition_spec']}`")
        if partition.get("table_ddl"):
            lines += ["", "```sql", str(partition["table_ddl"]).strip(), "```"]
    return lines


def coverage(report: InvestigationReport) -> list[str]:
    """Render deterministic collection coverage without interpreting it as findings."""
    if not report.coverage:
        return ["No deterministic collection coverage was recorded."]
    lines = ["| Module | Status | Reason | Evidence IDs |", "|---|---|---|---|"]
    for entry in report.coverage:
        status = "Not assessed" if entry.get("status") == "skipped" else entry.get("status", "unknown")
        evidence_ids = ", ".join(entry.get("evidence_ids") or []) or "none"
        lines.append(
            f"| {entry.get('module', 'unknown')} | {status} | "
            f"{entry.get('reason') or 'n/a'} | {evidence_ids} |"
        )
    return lines


def final_review(report: InvestigationReport) -> list[str]:
    """Render the whole-run critic output, including its safe fallback state."""
    review = report.final_review or {}
    status = review.get("status", "not_available")
    lines = [f"- Status: {status}", f"- Outcome: {review.get('outcome', 'not_assessed')}"]
    lines.append(f"- Summary: {review.get('summary') or 'Whole-run review was not recorded.'}")
    if review.get("error"):
        lines.append(f"- Review error: {review['error']}")
    for field, label in (
        ("consistency_issues", "Consistency issues"),
        ("unsupported_certainty", "Unsupported certainty"),
        ("duplicate_recommendations", "Duplicate recommendations"),
        ("missing_justification", "Missing justification"),
        ("coverage_gaps", "Coverage gaps"),
    ):
        items = review.get(field) or []
        if items:
            lines += ["", f"{label}:"] + [f"- {item}" for item in items]
    return lines
