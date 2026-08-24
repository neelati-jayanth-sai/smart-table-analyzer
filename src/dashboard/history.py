"""History projection of prior investigation runs."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.report_store import RunIndex


def render(runs: list[RunIndex], selected_id: int) -> None:
    """Show available runs while selection remains in the sidebar."""
    rows = [
        {
            "Selected": run.investigation_id == selected_id,
            "Run": run.investigation_id,
            "Table": run.table_name,
            "Lifecycle": run.lifecycle_state,
            "Source": run.source,
            "Finalized": run.finalized,
            "Started": run.started_at,
            "Completed": run.completed_at or "-",
        }
        for run in runs
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Select a run from the sidebar to inspect its finalized report projection.")
