"""Audit projection of persisted execution records."""

from __future__ import annotations

import json

import streamlit as st

from src.models import InvestigationReport


def render(report: InvestigationReport) -> None:
    """Render ordered SQL, blocked checks, and immutable report metadata."""
    entries = [entry for entry in report.trail if entry.get("query_text")]
    if not entries:
        st.info("No SQL was executed for this run.")
    for entry in entries:
        st.markdown(
            f"**Check {entry['check_num']}** · `{entry['node_name']}` · "
            f"{entry.get('execution_status')} · {entry.get('execution_time_ms') or 'n/a'} ms"
        )
        st.code(entry.get("rewritten_query") or entry["query_text"], language="sql")
        if entry.get("error_message"):
            st.error(entry["error_message"])
    if report.hook_violations:
        st.markdown("### Blocked checks")
        for violation in report.hook_violations:
            st.warning(
                f"Check {violation['check_num']}: {violation['hook_name']} — {violation['reason']}"
            )
    st.markdown("### Report record")
    st.json(json.loads(json.dumps(report.to_dict(), default=str)))
