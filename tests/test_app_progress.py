"""Focused tests for the dashboard's human-facing progress labels."""

from app import _progress_label


def test_progress_labels_explain_deep_profile_and_findings():
    assert _progress_label("profiling_columns") == (
        "Deep-diving into every primitive column", "🧪"
    )
    assert _progress_label("finding") == ("I found something worth checking", "⚠️")


def test_unknown_progress_stage_remains_readable():
    assert _progress_label("new_background_stage") == ("New Background Stage", "•")
