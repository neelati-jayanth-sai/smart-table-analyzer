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
