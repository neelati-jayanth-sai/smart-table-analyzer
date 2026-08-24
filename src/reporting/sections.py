"""One builder per report section.

Section order is fixed and engineer-first: Executive Summary, Root Causes,
Evidence, SQL Validation, Recommendations, Metadata Appendix. Conclusions
first — row counts last.
"""

from __future__ import annotations

from src.models import InvestigationReport


def _executive_summary(report: InvestigationReport) -> list[str]:
    causes = report.root_causes
    lines: list[str] = []

    if causes:
        lines.append(
            f"**{len(causes)} confirmed problem(s)** found across "
            f"{report.summary['total_findings']} checks on `{report.table_name}`."
        )
        lines.append("")
        for finding in causes:
            lines.append(f"- {_headline(finding)}")
    elif report.summary["total_findings"]:
        lines.append(
            f"No confirmed problems. {report.summary['validated_findings']} of "
            f"{report.summary['total_findings']} checks produced evidence-backed findings, "
            "none of which identified a defect."
        )
    else:
        lines.append("No findings were produced. See warnings below.")

    explanation = report.score_explanation
    if explanation.get("rows"):
        lines += ["", "### Health score, explained", ""]
        lines.append("| Evidence | Dimension score | Weight | Impact on final score |")
        lines.append("|---|---:|---:|---:|")
        for row in explanation["rows"]:
            lines.append(
                f"| {row['evidence'] or row['dimension']} | {row['subscore']} | "
                f"{row['weight']:.2f} | {row['impact']:+.1f} |"
            )
        lines.append(f"| **Final score** | | | **{explanation['overall']:.1f} / 100** |")

    if report.warnings:
        lines += ["", "### Warnings", ""]
        lines += [f"- {w}" for w in report.warnings]

    lines += [
        "",
        f"Status: **{report.status}** | Investigation `{report.investigation_id}` | "
        f"{report.summary['total_queries']} quer(ies) executed | "
        f"{report.summary['validated_findings']}/{report.summary['total_findings']} findings validated.",
    ]
    return lines


_HEADLINE_MAX = 140


def _headline(finding: dict) -> str:
    confidence = finding.get("confidence")
    suffix = f" (confidence {confidence:.2f})" if isinstance(confidence, (int, float)) else ""
    result = _one_line(finding["exact_result"])
    return f"**{finding.get('check_type') or 'finding'}** - {result}{suffix}"


def _one_line(text: str) -> str:
    """Flatten a result onto one line so it survives inside a bullet.

    `exact_result` is often a Markdown table, which breaks list layout when
    inlined. The full value is rendered in Root Causes; this is only the
    headline.
    """
    flattened = " ".join(str(text).split())
    if flattened.startswith("|"):
        # Collapse a Markdown table to "header: values" without its rules.
        cells = [c.strip() for c in flattened.split("|") if c.strip() and set(c.strip()) != {"-"}]
        flattened = ", ".join(cells)
    if len(flattened) > _HEADLINE_MAX:
        flattened = flattened[: _HEADLINE_MAX - 1].rstrip() + "…"
    return flattened


def _root_causes(report: InvestigationReport) -> list[str]:
    causes = report.root_causes
    if not causes:
        return ["No root cause was confirmed with evidence."]

    lines: list[str] = []
    for finding in causes:
        lines.append(f"### {finding['question']}")
        lines.append("")
        lines.append(f"- **Verdict:** {finding['verdict']}")
        lines.append(f"- **What the data shows:** {finding['exact_result']}")
        lines.append(f"- **Why:** {finding['rationale']}")
        confidence = finding.get("confidence")
        if isinstance(confidence, (int, float)):
            lines.append(f"- **Confidence:** {confidence:.2f}")
        lines.append(f"- **Evidence:** {', '.join(finding['evidence_ids']) or 'none'}")
        lines.append("")
    return lines


def _evidence(report: InvestigationReport) -> list[str]:
    if not report.findings:
        return ["No evidence was recorded."]

    lines = ["| Check | Question | Verdict | Confidence | Evidence IDs | Validated |", "|---|---|---|---:|---|---|"]
    for finding in report.findings:
        confidence = finding.get("confidence")
        confidence_text = f"{confidence:.2f}" if isinstance(confidence, (int, float)) else "-"
        lines.append(
            f"| {finding['check_num']} | {_cell(finding['question'])} | {finding['verdict']} | "
            f"{confidence_text} | {_cell(', '.join(finding['evidence_ids']) or 'none')} | "
            f"{'yes' if finding['validation']['valid'] else 'no'} |"
        )

    unvalidated = [f for f in report.findings if not f["validation"]["valid"]]
    if unvalidated:
        lines += ["", "Unresolved evidence:"]
        for finding in unvalidated:
            errors = "; ".join(finding["validation"]["errors"]) or "unknown"
            lines.append(f"- Check {finding['check_num']}: {errors}")

    if report.knowledge_references:
        lines += ["", "Knowledge consulted:"]
        seen = set()
        for ref in report.knowledge_references:
            key = f"knowledge:{ref['source']}/{ref['topic_path']}@{ref['version']}"
            if key not in seen:
                seen.add(key)
                lines.append(f"- `{key}`")
    return lines


def _sql_validation(report: InvestigationReport) -> list[str]:
    lines: list[str] = []
    for finding in report.findings:
        queries = finding.get("sql") or []
        if not queries:
            continue
        lines.append(f"### Check {finding['check_num']} - {_cell(finding['question'])}")
        lines.append("")
        for query in queries:
            lines.append(f"Status: `{query['status']}`" + (
                f" | {query['execution_time_ms']} ms" if query.get("execution_time_ms") else ""
            ))
            lines.append("")
            lines.append("```sql")
            lines.append(str(query["query"]).strip())
            lines.append("```")
            if query.get("error"):
                lines.append(f"> Error: {query['error']}")
            lines.append("")
    if not lines:
        lines.append("No queries were executed.")

    if report.hook_violations:
        lines += ["", "### Blocked queries", ""]
        for violation in report.hook_violations:
            lines.append(
                f"- `{violation['hook_name']}` blocked check {violation['check_num']}: "
                f"{violation['reason']}"
            )
    return lines


def _recommendations(report: InvestigationReport) -> list[str]:
    recommendations = report.recommendations
    if not recommendations:
        return ["No evidence-backed recommendation. Do not act on an unvalidated finding."]

    lines: list[str] = []
    for finding in recommendations:
        lines.append(f"### {finding.get('check_type') or 'recommendation'}")
        lines.append("")
        lines.append(finding["recommendation"])
        lines.append("")
        lines.append(f"Backed by: {', '.join(finding['evidence_ids'])}")
        if finding.get("alternatives"):
            lines.append("")
            lines.append("Alternatives considered:")
            lines += [f"- {alt}" for alt in finding["alternatives"]]
        if finding.get("actionable_sql"):
            lines += ["", "```sql", finding["actionable_sql"].strip(), "```"]
        lines.append("")
    return lines


def _appendix(report: InvestigationReport) -> list[str]:
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
    return lines


def _cell(text: str) -> str:
    """Make a value safe to place inside a Markdown table cell."""
    return str(text).replace("|", "\\|").replace("\n", " ")
