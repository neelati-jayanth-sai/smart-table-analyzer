"""Streamlit dashboard for investigation results.

Same section order as the written report: conclusions first, metadata last.
This view renders findings the Investigator produced; it never derives new ones.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.calculators.baseline_scorer import explain_score
from src.database import InvestigationDb
from ui_metadata import CHECK_METADATA, CHECK_METADATA_DEFAULT, get_priority, get_status, get_status_color
from ui_render import render_text_block

st.set_page_config(page_title="Smart Table Analyzer", layout="wide")

DB_PATH = Path("data/investigation.db")

if not DB_PATH.exists():
    st.error(f"Database not found at {DB_PATH}. Run an investigation first.")
    st.stop()

db = InvestigationDb(DB_PATH)

st.sidebar.title("Investigations")
investigations = db.list_investigations()
if not investigations:
    st.sidebar.info("No investigations found.")
    st.stop()

options = {
    f"#{i['investigation_id']} - {i['table_name']} ({i['status']})": i["investigation_id"]
    for i in investigations
}
inv_id = options[st.sidebar.selectbox("Select Investigation", list(options))]

investigation = db.get_investigation(inv_id)
findings = db.list_findings(inv_id)
trail = db.list_trail(inv_id)
hook_violations = db.list_hook_violations(inv_id)

st.title("Smart Table Analyzer")
st.subheader(f"`{investigation.table_name}`")

_STATUS_COLOR = {"completed": "green", "failed": "red", "aborted": "orange"}
st.markdown(
    f"**Status:** :{_STATUS_COLOR.get(investigation.status, 'blue')}"
    f"[{investigation.status.upper()}] | **Investigation ID:** {inv_id}"
)

root_causes = [f for f in findings if f.verdict == "found" and f.evidence_ids]

tab_summary, tab_findings, tab_sql, tab_appendix = st.tabs(
    ["Executive Summary", "Root Causes & Evidence", "SQL Validation", "Metadata Appendix"]
)

with tab_summary:
    if root_causes:
        st.markdown(f"### {len(root_causes)} confirmed problem(s)")
        for finding in root_causes:
            confidence = f" — confidence {finding.confidence:.2f}" if finding.confidence else ""
            st.markdown(f"- **{finding.check_type or 'finding'}**: {finding.exact_result}{confidence}")
    elif findings:
        st.success("No confirmed problems. Every check that produced evidence came back clean.")
    else:
        st.warning("No findings were produced by this investigation.")

    if investigation.status != "completed":
        st.warning(
            f"This investigation ended as '{investigation.status}'. Treat its conclusions as incomplete."
        )
    if hook_violations:
        st.warning(f"{len(hook_violations)} query/queries were blocked by a safety hook.")

    baseline = investigation.baseline_score or {}
    dimensions = baseline.get("dimensions", {})
    explanation = explain_score(dimensions)
    if explanation["rows"]:
        st.markdown("### Health score, explained")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Evidence": row["evidence"],
                        "Dimension score": row["subscore"],
                        "Weight": row["weight"],
                        "Impact on final score": row["impact"],
                    }
                    for row in explanation["rows"]
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.metric("Overall health score", f"{explanation['overall']:.1f}/100")

    if findings:
        st.markdown("### Check summary")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Check": CHECK_METADATA.get(f.check_type, CHECK_METADATA_DEFAULT)["title"],
                        "Priority": get_priority(
                            f.check_type,
                            f.verdict,
                            get_status(f.check_type, f.verdict, f.rationale, f.validated),
                            CHECK_METADATA.get(f.check_type, CHECK_METADATA_DEFAULT)["priority"],
                            f.recommendation,
                        ),
                        "Status": get_status(f.check_type, f.verdict, f.rationale, f.validated),
                        "Confidence": f.confidence,
                    }
                    for f in findings
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

with tab_findings:
    if not findings:
        st.info("No findings recorded.")
    for finding in findings:
        meta = CHECK_METADATA.get(finding.check_type, CHECK_METADATA_DEFAULT)
        status = get_status(finding.check_type, finding.verdict, finding.rationale, finding.validated)
        color = get_status_color(status)

        with st.expander(f"{meta['title']} - :{color}[{status}]", expanded=bool(finding.evidence_ids)):
            cols = st.columns([2, 1])
            with cols[0]:
                st.markdown(f"**Question:** {finding.question}")
                st.markdown("**What the data shows:**")
                render_text_block(finding.exact_result)
                st.markdown(f"**Why:** {finding.rationale}")
            with cols[1]:
                st.markdown(f"**Verdict:** {finding.verdict}")
                if finding.confidence is not None:
                    st.markdown(f"**Confidence:** {finding.confidence:.2f}")
                st.markdown(f"**Evidence:** {', '.join(finding.evidence_ids) or 'none'}")
                st.markdown(f"**Expected state:** {meta['expected']}")
                st.markdown(f"**Risk:** {meta['risk']}")

            if finding.recommendation:
                st.markdown("#### Recommendation")
                st.success(finding.recommendation)
            if finding.actionable_sql:
                st.code(finding.actionable_sql, language="sql")
            if not finding.evidence_ids:
                st.error("This finding cites no evidence and must not be acted on.")

with tab_sql:
    for entry in trail:
        if not entry.get("query_text"):
            continue
        st.markdown(
            f"**Check {entry['check_num']}** - `{entry['node_name']}` "
            f"({entry['execution_status']}, {entry['execution_time_ms']}ms)"
        )
        st.code(entry.get("rewritten_query") or entry["query_text"], language="sql")
        if entry.get("error_message"):
            st.error(entry["error_message"])
    for violation in hook_violations:
        st.warning(
            f"`{violation['hook_name']}` blocked check {violation['check_num']}: {violation['reason']}"
        )

with tab_appendix:
    st.markdown(
        f"- Run ID: `{investigation.run_id}`\n"
        f"- Catalog / schema: {investigation.catalog_name} / {investigation.schema_name}\n"
        f"- Snapshot: {investigation.snapshot_id or 'not pinned'}\n"
        f"- Started: {investigation.started_at}\n"
        f"- Completed: {investigation.completed_at or 'n/a'}"
    )
    if (investigation.baseline_score or {}).get("dimensions"):
        st.json(json.dumps(investigation.baseline_score["dimensions"], default=str))
