"""Streamlit dashboard for launching and viewing table investigations."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.analyzer.progress import AnalysisProgress
from src.dashboard import (
    AnalysisRequest,
    DashboardAnalysisRunner,
    InvestigationReportStore,
    default_run_index,
)
from src.database import investigation_db_path
from src.dashboard import audit, evidence, findings, history, overview

REPO_ROOT = Path(__file__).resolve().parent
DB_PATH = investigation_db_path(REPO_ROOT)
PAGES = ("Overview", "Findings", "Evidence", "History", "Audit")

load_dotenv(REPO_ROOT / ".env")


@st.cache_resource(show_spinner=False)
def _spark_connection():
    """Keep one Spark Connect session for this dashboard process."""
    return DashboardAnalysisRunner(REPO_ROOT).connect()


def main() -> None:
    """Launch an analysis or route a finalized report into a detail screen."""
    st.set_page_config(page_title="Smart Table Analyzer", layout="wide")
    st.title("Smart Table Analyzer")
    _render_analysis_form()

    store = InvestigationReportStore(DB_PATH, REPO_ROOT / "reports")
    runs = store.list_runs()
    if not runs:
        st.info("No investigations yet. Start one above to populate this dashboard.")
        return

    selected = _select_run(runs)
    report = store.get_report(selected)
    page = st.sidebar.radio("Explore", PAGES)
    _render(page, report, store, runs, selected)


def _render_analysis_form() -> None:
    st.subheader("Run an investigation")
    st.caption("The dashboard reuses its Spark Connect session; the analysis runs the same pipeline as the CLI.")
    with st.form("analysis-request"):
        table = st.text_input(
            "Table name",
            placeholder="catalog.schema.table",
            help="Enter the full Iceberg table name, for example eds_it_dev.schema.orders.",
        )
        options, advanced = st.columns(2)
        query_table = options.text_input(
            "Query metrics table (optional)",
            help="Use a separate IOMETE query-log table for workload metadata.",
        )
        snapshot = options.text_input("Snapshot ID (optional)")
        profile = advanced.selectbox(
            "Analysis depth",
            ("shallow", "deep"),
            index=0,
            help="Shallow is fast metadata-only collection. Deep also profiles table data and can take longer.",
        )
        max_checks = advanced.number_input(
            "Maximum planned checks",
            min_value=1,
            max_value=20,
            value=5,
            help="Caps the initial LLM hypotheses after deterministic metadata collection. "
            "Each runs sequentially and can add evidence-driven follow-ups, so the final check "
            "count can be higher. More planned checks take longer and use more LLM calls.",
        )
        submitted = st.form_submit_button("Start analysis", type="primary")

    if submitted:
        _run_analysis(AnalysisRequest(
            table_name=table,
            snapshot_id=snapshot or None, query_metrics_table=query_table or None,
            metadata_profile=profile, max_checks=int(max_checks),
        ))


def _run_analysis(request: AnalysisRequest) -> None:
    status = st.status("Queued", expanded=True)
    stage = status.empty()

    def show_progress(update: AnalysisProgress) -> None:
        stage.write(f"**{update.stage.replace('_', ' ').title()}** — {update.message}")
        if update.stage == "error":
            status.update(label="Analysis failed", state="error", expanded=True)
        elif update.stage == "report_complete":
            status.update(label="Report complete", state="complete", expanded=False)
        else:
            status.update(label=update.stage.replace("_", " ").title(), state="running")

    try:
        show_progress(AnalysisProgress("connecting", "Opening or reusing Spark Connect session"))
        outcome = DashboardAnalysisRunner(REPO_ROOT).run(_spark_connection(), request, show_progress)
    except Exception as exc:
        show_progress(AnalysisProgress("error", str(exc)))
        st.exception(exc)
        return
    st.session_state["latest_investigation_id"] = outcome.investigation_id
    st.success(f"Investigation {outcome.investigation_id} completed for `{outcome.context.table_name}`.")


def _select_run(runs):
    preferred_id = st.session_state.get("latest_investigation_id")
    index = default_run_index(runs, preferred_id)
    return st.sidebar.selectbox("Investigation run", runs, index=index, format_func=lambda run: run.label)


def _render(page, report, store, runs, selected) -> None:
    if page == "Overview":
        overview.render(report, store, selected)
    elif page == "Findings":
        findings.render(report)
    elif page == "Evidence":
        evidence.render(report)
    elif page == "History":
        history.render(runs, selected.investigation_id)
    else:
        audit.render(report)


if __name__ == "__main__":
    main()
