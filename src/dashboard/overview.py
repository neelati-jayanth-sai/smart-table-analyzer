"""Overview projection for one selected finalized report."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.report_store import InvestigationReportStore
from src.dashboard.report_store import RunIndex
from src.dashboard.view_models import signal_rows
from src.models import InvestigationReport


def render(report: InvestigationReport, store: InvestigationReportStore, run: RunIndex) -> None:
    """Render current table health or a compact historic-report notice."""
    if report.assessment.state == "incomplete":
        _render_historic_report(report, run)
        return

    state = report.assessment.state.replace("_", " ").title()
    st.subheader("Table health")
    st.caption(f"{report.table_name} · {state}")
    for reason in report.assessment.reasons:
        st.warning(reason) if report.assessment.state != "clean" else st.success(reason)

    left, middle, right = st.columns(3)
    left.metric("Health score", _score(report))
    middle.metric("Validated findings", str(report.summary["validated_findings"]))
    right.metric("Evidence checks", str(report.summary["total_findings"]))

    _render_signals(report)
    _render_next_step(report)
    _render_run_details(report, store, run)


def _score(report: InvestigationReport) -> str:
    if report.assessment.state == "incomplete":
        return "Not current"
    overall = report.baseline_score.get("overall")
    return f"{overall:.1f}/100" if isinstance(overall, (int, float)) else "Not available"


def _render_signals(report: InvestigationReport) -> None:
    rows = signal_rows(report)
    if not rows:
        return
    st.markdown("### Measured conditions")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_run_details(
    report: InvestigationReport, store: InvestigationReportStore, run: RunIndex
) -> None:
    with st.expander("Run details"):
        st.caption(
            f"Snapshot: {report.snapshot_id or 'not pinned'} · Started: {report.started_at} · "
            f"Finalized: {report.completed_at or 'not finalized'} · "
            f"Report ID: `{store.fingerprint(report)}` · Source: {run.source}"
        )


def _render_historic_report(report: InvestigationReport, run: RunIndex) -> None:
    st.info(
        "Historical report — its assessment is not part of the current dashboard status. "
        "Use Findings or Evidence to inspect it, or start a new investigation above."
    )
    with st.expander("Historic report details"):
        st.caption(
            f"{report.table_name} · {run.source} · "
            f"Finalized: {report.completed_at or 'not finalized'}"
        )


def _render_next_step(report: InvestigationReport) -> None:
    st.markdown("### Next step")
    if report.assessment.state == "action_required":
        st.info("Review the confirmed findings and their evidence-backed recommendations.")
    elif report.assessment.state == "needs_review":
        st.info("Inspect the measured conditions and evidence before treating this table as clean.")
    elif report.assessment.state == "incomplete":
        st.info("Run the investigation again to produce a current, complete assessment.")
    else:
        st.success("No further action is indicated by the completed, validated checks.")
