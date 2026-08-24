"""Streamlit dashboard for one selected, finalized investigation report."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.dashboard import InvestigationReportStore
from src.database import investigation_db_path
from src.dashboard import audit, evidence, findings, history, overview

DB_PATH = investigation_db_path(Path(__file__).resolve().parent)
PAGES = ("Overview", "Findings", "Evidence", "History", "Audit")


def main() -> None:
    """Route a selected report into one progressive detail screen."""
    st.set_page_config(page_title="Smart Table Analyzer", layout="wide")
    st.title("Smart Table Analyzer")
    if not DB_PATH.exists():
        st.error(f"Database not found at {DB_PATH}. Run an investigation first.")
        return

    store = InvestigationReportStore(DB_PATH)
    runs = store.list_runs()
    if not runs:
        st.info("No investigations found.")
        return

    selected = _select_run(runs)
    report = store.get_report(selected)
    st.caption(
        f"`{report.table_name}` · lifecycle: {report.status.replace('_', ' ')} · "
        f"assessment: {report.assessment.state.replace('_', ' ')} · source: {selected.source}"
    )
    page = st.sidebar.radio("Explore", PAGES)
    _render(page, report, store, runs, selected.investigation_id)


def _select_run(runs):
    labels = {run.label: run for run in runs}
    label = st.sidebar.selectbox("Investigation run", list(labels))
    return labels[label]


def _render(page, report, store, runs, selected_id: int) -> None:
    if page == "Overview":
        overview.render(report, store)
    elif page == "Findings":
        findings.render(report)
    elif page == "Evidence":
        evidence.render(report)
    elif page == "History":
        history.render(runs, selected_id)
    else:
        audit.render(report)


if __name__ == "__main__":
    main()
