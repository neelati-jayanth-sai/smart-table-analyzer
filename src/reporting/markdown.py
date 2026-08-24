"""Render an InvestigationReport as Markdown."""

from __future__ import annotations

from src.models import InvestigationReport

from .closing_sections import appendix, recommendations

from .sections import (
    _evidence,
    _executive_summary,
    _root_causes,
    _sql_validation,
)


def render_markdown(report: InvestigationReport) -> str:
    lines: list[str] = [
        f"# Investigation Report: {report.table_name}",
        "",
        "## 1. Executive Summary",
        "",
    ]
    lines += _executive_summary(report)
    lines += ["", "## 2. Root Causes", ""] + _root_causes(report)
    lines += ["", "## 3. Evidence", ""] + _evidence(report)
    lines += ["", "## 4. SQL Validation", ""] + _sql_validation(report)
    lines += ["", "## 5. Recommendations", ""] + recommendations(report)
    lines += ["", "## 6. Metadata Appendix", ""] + appendix(report)
    return "\n".join(lines) + "\n"
