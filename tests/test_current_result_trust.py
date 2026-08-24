"""Trust gates for the current-result dashboard view."""

from __future__ import annotations

from src.dashboard.current_result_trust import (
    is_verified_finding,
    verified_issue_recommendations,
)


def _finding(**overrides):
    return {
        "db_validated": True,
        "validation": {"valid": True},
        "sql": [{"status": "success"}],
        "issue_state": "issue_found",
        "recommendation": "Rewrite the table.",
        **overrides,
    }


def test_verified_requires_persisted_claim_and_successful_execution():
    assert is_verified_finding(_finding())
    assert not is_verified_finding(_finding(db_validated=False))
    assert not is_verified_finding(_finding(validation={"valid": False}))
    assert not is_verified_finding(_finding(sql=[{"status": "timeout"}]))


def test_recommendations_exclude_unverified_findings():
    actions = verified_issue_recommendations([_finding(), _finding(db_validated=False)])

    assert [action["recommendation"] for action in actions] == ["Rewrite the table."]
