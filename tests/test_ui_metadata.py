"""Tests for presentation policy at the Streamlit seam."""

from __future__ import annotations

from types import SimpleNamespace

from ui_metadata import get_finding_status, has_actionable_recommendation


def _finding(*, verdict: str, validated: bool, recommendation: str | None = None):
    return SimpleNamespace(
        check_type="skew",
        verdict=verdict,
        rationale="test rationale",
        validated=validated,
        recommendation=recommendation,
    )


def test_high_signal_not_found_is_not_presented_as_healthy():
    finding = _finding(verdict="not_found", validated=True)

    assert get_finding_status(finding, {"skew"}) == "Needs Review"


def test_clean_finding_cannot_present_an_action():
    finding = _finding(verdict="not_found", validated=True, recommendation="Do work")

    assert not has_actionable_recommendation(finding)


def test_valid_confirmed_finding_can_present_an_action():
    finding = _finding(verdict="found", validated=True, recommendation="Do work")

    assert has_actionable_recommendation(finding)
