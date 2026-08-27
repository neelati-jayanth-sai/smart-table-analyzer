"""Single-run Streamlit interface for table investigations."""

from __future__ import annotations

import time
import os
from html import escape
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.analyzer.progress import AnalysisProgress
from src.dashboard import AnalysisRequest, DashboardAnalysisRunner
from src.dashboard.current_result import render as render_current_result
from src.database import InvestigationDb, investigation_db_path
from src.models import InvestigationReport
from src.reporting import ReportAssembler, render_pdf

REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")

@st.cache_resource(show_spinner=False)
def _spark_connection():
    """Keep one Spark Connect session for this dashboard process."""
    return DashboardAnalysisRunner(REPO_ROOT).connect()


def _render_brand_header() -> None:
    st.markdown(
        "<div class='brand-header'><div class='brand-mark'>ST</div><div><div class='brand-name'>Smart Table Analyzer</div><div class='brand-tagline'>Evidence-led Iceberg intelligence</div></div><div class='brand-badge'>FULL DEEP · THOROUGH</div></div>",
        unsafe_allow_html=True,
    )


def _inject_styles() -> None:
    st.markdown(
        """<style>
        :root{--ink:#10233f;--muted:#64748b;--line:#dbe5f0;--navy:#12233f}.stApp{background:linear-gradient(180deg,#f7faff 0,#fff 360px);color:var(--ink)}.block-container{max-width:1180px;padding-top:2.2rem;padding-bottom:4rem}
        .brand-header{display:flex;align-items:center;gap:.8rem;padding:0 0 2rem;border-bottom:1px solid var(--line);margin-bottom:2.4rem}.brand-mark{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#2563eb,#0f3b82);color:#fff;display:grid;place-items:center;font-weight:800;letter-spacing:-.06em;box-shadow:0 8px 18px #2563eb33}.brand-name{font-size:1.05rem;font-weight:750;letter-spacing:-.02em}.brand-tagline,.muted{color:var(--muted);font-size:.83rem}.brand-badge,.live-pill{margin-left:auto;border:1px solid #cbdcf8;color:#2358ad;background:#edf4ff;border-radius:999px;padding:.36rem .7rem;font-size:.68rem;font-weight:750;letter-spacing:.08em}
        .hero-copy{max-width:760px;margin:1rem 0 2rem}.eyebrow{color:#3b72cc;font-size:.67rem;letter-spacing:.14em;font-weight:800;margin:0 0 .5rem}.hero-copy h1{color:var(--navy);font-size:clamp(2.1rem,4vw,3.5rem);line-height:1.05;letter-spacing:-.055em;margin:0 0 1rem}.hero-subtitle{color:#53657e;font-size:1.05rem;line-height:1.65;max-width:650px}
        .panel{border:1px solid var(--line);border-radius:18px;background:#fff;box-shadow:0 14px 34px #183b6810;padding:1.5rem}.form-panel h2,.timeline-heading h2{color:var(--navy);letter-spacing:-.035em;margin:.1rem 0 .35rem}.promise-panel{height:100%;background:linear-gradient(150deg,#f2f7ff,#fff)}.promise{display:flex;gap:.8rem;align-items:flex-start;padding:1rem 0;border-bottom:1px solid #e5edf7}.promise:last-child{border-bottom:0}.promise span{color:#4d82d2;font-size:.75rem;font-weight:800}.promise b{display:block;color:var(--navy);font-size:.92rem;margin-bottom:.22rem}.promise small{color:var(--muted);line-height:1.45;display:block}
        .timeline-heading{display:flex;align-items:end;margin-top:2rem}.timeline-heading h2{margin-bottom:0}.live-pill{margin-bottom:.25rem;color:#15803d;background:#ecfdf3;border-color:#bbf7d0}.timeline-card{display:flex;gap:.8rem;border:1px solid var(--line);border-radius:14px;background:#fff;padding:1rem 1.1rem;margin:.7rem 0;box-shadow:0 5px 16px #183b680b}.timeline-icon{width:2rem;height:2rem;flex:none;display:grid;place-items:center;background:#eff5ff;border-radius:10px;font-size:1rem}.timeline-body{flex:1;min-width:0}.timeline-meta{display:flex;justify-content:space-between;gap:1rem;color:var(--navy);font-size:.88rem}.timeline-meta span{color:#94a3b8;font-size:.72rem;white-space:nowrap}.timeline-message{color:#52647d;font-size:.88rem;line-height:1.55;margin-top:.3rem}
        div[data-testid='stTextInput'] label p{color:var(--navy)!important;font-size:.82rem;font-weight:650}div[data-testid='stTextInput'] input{background:#fff!important;color:var(--navy)!important;border:1px solid #cbd8e8!important;border-radius:10px!important;box-shadow:0 2px 6px #183b6808}div[data-testid='stTextInput'] input::placeholder{color:#8291a6!important;opacity:1}div[data-testid='stTextInput'] input:focus{border-color:#4d82d2!important;box-shadow:0 0 0 3px #4d82d226!important}div[data-testid='stExpander']{background:#f7faff;border:1px solid #dbe5f0;border-radius:12px;overflow:hidden}div[data-testid='stExpander'] summary{background:#f7faff!important;color:var(--navy)!important}div[data-testid='stExpander'] summary p{color:var(--navy)!important;font-size:.85rem;font-weight:650}div[data-testid='stExpander'] svg{color:#4d72a6!important}div[data-testid='stFormSubmitButton'] button{border-radius:10px;font-weight:700;min-height:2.8rem}div[data-testid='stForm']{border:0;padding:0}div[data-testid='stStatusWidget']{border-radius:14px}
        </style>""",
        unsafe_allow_html=True,
    )


def main() -> None:
    """Run one investigation and show only its current-session outcome."""
    st.set_page_config(page_title="Smart Table Analyzer", layout="wide")
    _inject_styles()
    _render_brand_header()
    if "latest_outcome" in st.session_state:
        _render_latest_result()
    else:
        _render_analysis_form()


def _render_analysis_form() -> None:
    st.markdown(
        "<div class='hero-copy'><p class='eyebrow'>TABLE INTELLIGENCE</p>"
        "<h1>Understand what is happening in your table.</h1>"
        "<p class='hero-subtitle'>The agent investigates the table like an experienced data engineer: it finds evidence, explains what it means, and keeps you informed as it works.</p></div>",
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.7, 1], gap="large")
    with left:
        st.markdown("<div class='panel form-panel'>", unsafe_allow_html=True)
        st.markdown("<h2>Start an investigation</h2><p class='muted'>Enter one Iceberg table. Full Deep profiling and Thorough analysis run automatically.</p>", unsafe_allow_html=True)
        with st.form("analysis-request"):
            table = (
                st.selectbox("Local test table", _local_tables())
                if os.getenv("STA_RUNTIME") == "local"
                else st.text_input(
                    "Table name", placeholder="catalog.schema.table",
                    help="Enter a three-part Iceberg table name, for example eds_it_dev.schema.orders.",
                )
            )
            with st.expander("Connection details (optional)"):
                query_table = st.text_input("Query metrics table", placeholder="catalog.schema.query_history")
                snapshot = st.text_input("Snapshot ID", placeholder="Leave blank to use the current snapshot")
            submitted = st.form_submit_button("Start investigation  →", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown(
            "<div class='panel promise-panel'><p class='eyebrow'>WHAT YOU WILL SEE</p>"
            "<div class='promise'><span>01</span><div><b>Evidence first</b><small>Exact measurements and property names, not guesses.</small></div></div>"
            "<div class='promise'><span>02</span><div><b>Human explanation</b><small>What was found, why it matters, and what happens next.</small></div></div>"
            "<div class='promise'><span>03</span><div><b>Complete deep dive</b><small>Every primitive column is profiled before the final assessment.</small></div></div></div>",
            unsafe_allow_html=True,
        )

    if submitted:
        request = AnalysisRequest(
            table_name=table,
            snapshot_id=snapshot or None,
            query_metrics_table=query_table or None,
        )
        _run_analysis(request)


def _run_analysis(request: AnalysisRequest) -> None:
    try:
        request.resolved_table()
    except ValueError as exc:
        st.error(str(exc))
        return

    started = time.monotonic()
    status = st.status("The agent is starting its investigation", expanded=True)
    st.markdown("<div class='timeline-heading'><div><p class='eyebrow'>LIVE INVESTIGATION</p><h2>What the agent knows so far</h2></div><span class='live-pill'>● LIVE</span></div>", unsafe_allow_html=True)
    st.caption("The agent will share what it finds while the full deep profile continues.")
    timeline = st.container()
    event_number = 0

    def show_progress(update: AnalysisProgress) -> None:
        nonlocal event_number
        event_number += 1
        elapsed = time.monotonic() - started
        label, icon = _progress_label(update.stage)
        with timeline:
            st.markdown(
                f"<div class='timeline-card'><div class='timeline-icon'>{icon}</div><div class='timeline-body'><div class='timeline-meta'><b>{escape(label)}</b><span>{event_number:02d} · {elapsed:.0f}s</span></div><div class='timeline-message'>{escape(update.message)}</div></div></div>",
                unsafe_allow_html=True,
            )
        status.write(f"{icon} {label} — {update.message}")
        state = "error" if update.stage == "error" else "complete" if update.stage == "report_complete" else "running"
        status.update(
            label="The agent has finished" if state == "complete" else f"The agent is working — {label}",
            state=state,
            expanded=state != "complete",
        )

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


def _local_tables() -> list[str]:
    return [f"local.e2e.{name}" for name in "healthy_orders small_files_orders skewed_orders tiny_partitions_orders snapshot_bloat_orders evolving_orders mixed_orders empty_orders".split()]


def _progress_label(stage: str) -> tuple[str, str]:
    """Turn pipeline stages into the short, human-facing timeline labels."""
    labels = {
        "connecting": ("Connecting to the table", "🔌"),
        "queued": ("I have the table and am getting started", "🟢"),
        "pinning_snapshot": ("Pinning the table snapshot", "📌"),
        "snapshot_ready": ("The table version is fixed for this investigation", "📍"),
        "collecting_metadata": ("Getting to know the table", "🔎"),
        "finding": ("I found something worth checking", "⚠️"),
        "profiling_columns": ("Deep-diving into every primitive column", "🧪"),
        "investigating": ("Testing the evidence and possible causes", "🧠"),
        "profile_complete": ("The full column profile is complete", "✅"),
        "rendering_report": ("Putting the evidence-backed explanation together", "📝"),
        "report_complete": ("Investigation complete", "✅"),
        "error": ("The investigation needs attention", "❌"),
    }
    return labels.get(stage, (stage.replace("_", " ").title(), "•"))


def _render_latest_result() -> None:
    outcome = st.session_state["latest_outcome"]
    if st.button("Start another analysis"):
        del st.session_state["latest_outcome"]
        st.session_state.pop("latest_elapsed_seconds", None)
        st.rerun()
    report = ReportAssembler(InvestigationDb(investigation_db_path(REPO_ROOT))).assemble(
        outcome.investigation_id
    )
    _download_report(report)
    render_current_result(outcome, report, st.session_state.get("latest_elapsed_seconds", 0))


def _download_report(report: InvestigationReport) -> None:
    """Offer the selected report without persisting a duplicate dashboard artifact."""
    name = "_".join(part for part in report.table_name.split(".") if part) or "table"
    st.download_button(
        "Download PDF report",
        data=render_pdf(report),
        file_name=f"investigation_{report.run_id}_{name}.pdf",
        mime="application/pdf",
        help="Downloads the same complete report sections shown for this investigation.",
    )


if __name__ == "__main__":
    main()
