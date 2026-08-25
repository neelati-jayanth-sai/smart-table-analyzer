"""Single-run Streamlit interface for table investigations."""

from __future__ import annotations

import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.analyzer.progress import AnalysisProgress
from src.dashboard import AnalysisRequest, DashboardAnalysisRunner
from src.dashboard.current_result import render as render_current_result
from src.database import InvestigationDb, investigation_db_path
from src.reporting import ReportAssembler

REPO_ROOT = Path(__file__).resolve().parent

load_dotenv(REPO_ROOT / ".env")


@st.cache_resource(show_spinner=False)
def _spark_connection():
    """Keep one Spark Connect session for this dashboard process."""
    return DashboardAnalysisRunner(REPO_ROOT).connect()


def main() -> None:
    """Run one investigation and show only its current-session outcome."""
    st.set_page_config(page_title="Smart Table Analyzer", layout="wide")
    st.title("Smart Table Analyzer")
    st.caption("Investigate one Iceberg table with measured metadata and evidence-backed checks.")
    if "latest_outcome" in st.session_state:
        _render_latest_result()
    else:
        _render_analysis_form()


def _render_analysis_form() -> None:
    st.subheader("Start an investigation")
    st.caption("Enter the table. Shallow is the recommended fast starting point.")
    with st.form("analysis-request"):
        table = st.text_input(
            "Table name",
            placeholder="catalog.schema.table",
            help="Enter a three-part Iceberg table name, for example eds_it_dev.schema.orders.",
        )
        profile = st.radio(
            "Analysis depth",
            ("fast", "deep"),
            index=0,
            help="Fast is metadata-only. Deep profiles every primitive column in bounded aggregate batches.",
        )
        with st.expander("Advanced options"):
            query_table = st.text_input("Query metrics table (optional)")
            snapshot = st.text_input("Snapshot ID (optional)")
            breadth = st.selectbox(
                "Investigation breadth",
                ("Focused", "Standard", "Thorough"),
                index=1,
                help="Controls the initial hypotheses the LLM will test. More breadth takes longer.",
            )
        submitted = st.form_submit_button("Run analysis", type="primary")

    if submitted:
        request = AnalysisRequest(
            table_name=table,
            snapshot_id=snapshot or None,
            query_metrics_table=query_table or None,
            metadata_profile=profile,
            max_checks={"Focused": 1, "Standard": 5, "Thorough": 10}[breadth],
        )
        _run_analysis(request)


def _run_analysis(request: AnalysisRequest) -> None:
    try:
        request.resolved_table()
    except ValueError as exc:
        st.error(str(exc))
        return

    started = time.monotonic()
    status = st.status("Preparing analysis", expanded=True)

    def show_progress(update: AnalysisProgress) -> None:
        elapsed = time.monotonic() - started
        label = update.stage.replace("_", " ").title()
        status.write(f"{elapsed:.0f}s · **{label}** — {update.message}")
        state = "error" if update.stage == "error" else "complete" if update.stage == "report_complete" else "running"
        status.update(label=label, state=state, expanded=state != "complete")

    try:
        show_progress(AnalysisProgress("connecting", "Opening or reusing Spark Connect"))
        outcome = DashboardAnalysisRunner(REPO_ROOT).run(_spark_connection(), request, show_progress)
    except Exception as exc:
        show_progress(AnalysisProgress("error", "The investigation could not complete."))
        st.error("Analysis failed. Check the table name, Spark connection, and configured credentials.")
        with st.expander("Technical details"):
            st.code(str(exc))
        return

    st.session_state["latest_outcome"] = outcome
    st.session_state["latest_elapsed_seconds"] = round(time.monotonic() - started)
    st.rerun()


def _render_latest_result() -> None:
    outcome = st.session_state["latest_outcome"]
    if st.button("Start another analysis"):
        del st.session_state["latest_outcome"]
        st.session_state.pop("latest_elapsed_seconds", None)
        st.rerun()
    report = ReportAssembler(InvestigationDb(investigation_db_path(REPO_ROOT))).assemble(
        outcome.investigation_id
    )
    render_current_result(outcome, report, st.session_state.get("latest_elapsed_seconds", 0))


if __name__ == "__main__":
    main()
