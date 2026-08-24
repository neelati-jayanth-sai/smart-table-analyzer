"""Prioritized findings projection for one selected report."""

from __future__ import annotations

import streamlit as st

from src.dashboard.view_models import finding_rows
from src.models import InvestigationReport

from ui_render import render_text_block


def render(report: InvestigationReport) -> None:
    """Render findings in report priority order, then expand supporting detail."""
    rows = finding_rows(report)
    if not rows:
        st.info("No findings were recorded for this run.")
        return
    for row in rows:
        finding = row["finding"]
        label = f"{row['title']} · {row['priority']} · {row['status']}"
        with st.expander(label, expanded=row["status"] != "Clean"):
            st.markdown(f"**Question:** {finding['question']}")
            st.markdown(f"**Threshold / expected:** {row['expected']}")
            st.markdown("**What the data shows:**")
            render_text_block(finding["exact_result"])
            st.markdown(f"**Why it matters:** {row['risk']}")
            st.markdown(f"**Assessment:** {finding['rationale']}")
            st.caption(f"Evidence: {', '.join(finding['evidence_ids']) or 'not recorded'}")
            _render_action(report, finding)


def _render_action(report: InvestigationReport, finding: dict) -> None:
    if report.assessment.state != "action_required":
        return
    if finding.get("issue_state") != "issue_found" or not finding["validation"]["valid"]:
        return
    if finding.get("recommendation"):
        st.success(finding["recommendation"])
    if finding.get("actionable_sql"):
        st.code(finding["actionable_sql"], language="sql")
