"""Evidence projection for one selected report."""

from __future__ import annotations

import streamlit as st

from src.models import InvestigationReport

from ui_render import render_text_block


def render(report: InvestigationReport) -> None:
    """Render the persisted result and validation for every finding."""
    _render_coverage(report)
    _render_final_review(report)
    if not report.findings:
        st.info("No evidence was recorded for this run.")
        return
    for finding in report.findings:
        title = f"Check {finding['check_num']} · {finding.get('check_type') or 'investigation'}"
        with st.expander(title):
            st.markdown(f"**Evidence IDs:** {', '.join(finding['evidence_ids']) or 'none'}")
            validation = finding["validation"]
            if validation["valid"]:
                st.success("Evidence references resolved.")
            elif not finding["evidence_ids"]:
                st.warning("No evidence reference was recorded for this result.")
            else:
                st.error("Evidence references could not be resolved.")
                st.write(validation["errors"] or validation["missing_ids"])
            st.markdown("**Recorded result:**")
            render_text_block(finding["exact_result"])
            _render_queries(finding.get("sql") or [])


def _render_queries(queries: list[dict]) -> None:
    for query in queries:
        st.caption(f"{query.get('status')} · {query.get('execution_time_ms') or 'n/a'} ms")
        st.code(query.get("query") or "", language="sql")
        if query.get("error"):
            st.error(query["error"])


def _render_coverage(report: InvestigationReport) -> None:
    st.markdown("### Deterministic coverage")
    if not report.coverage:
        st.info("No deterministic collection coverage was recorded.")
        return
    rows = []
    for entry in report.coverage:
        status = "Not assessed" if entry.get("status") == "skipped" else entry.get("status")
        rows.append(
            {
                "module": entry.get("module"),
                "status": status,
                "reason": entry.get("reason") or "n/a",
                "evidence IDs": ", ".join(entry.get("evidence_ids") or []) or "none",
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)


def _render_final_review(report: InvestigationReport) -> None:
    st.markdown("### Whole-run review")
    review = report.final_review or {}
    summary = review.get("summary") or "Whole-run review was not recorded."
    if review.get("status") == "completed":
        st.caption(f"{review.get('outcome', 'not_assessed')} · {summary}")
    else:
        st.warning(summary)
    for field in (
        "consistency_issues",
        "unsupported_certainty",
        "duplicate_recommendations",
        "missing_justification",
        "coverage_gaps",
    ):
        for item in review.get(field) or []:
            st.write(f"- {item}")
