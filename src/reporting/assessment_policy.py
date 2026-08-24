"""Finalize report assessment from lifecycle, deterministic evidence, and findings."""

from __future__ import annotations

from typing import Any

from src.investigator.planner import SIGNAL_HYPOTHESES
from src.models import ASSESSMENT_VERSION, Assessment


def assess(
    lifecycle_state: str,
    baseline: dict[str, Any],
    findings: list[dict[str, Any]],
    hook_violations: list[dict[str, Any]],
) -> Assessment:
    """Return the only assessment state report consumers may present."""
    if lifecycle_state != "completed":
        return Assessment("incomplete", [f"Investigation lifecycle ended as '{lifecycle_state}'."])
    if baseline.get("assessment_version") != ASSESSMENT_VERSION:
        return Assessment(
            "incomplete",
            ["This run predates deterministic assessment provenance. Run it again before treating it as clean."],
        )
    confirmed = [
        finding
        for finding in findings
        if finding.get("verdict") == "found"
        and finding.get("issue_state") == "issue_found"
        and finding.get("db_validated")
        and finding["validation"]["valid"]
    ]
    if confirmed:
        return Assessment(
            "action_required",
            [f"{len(confirmed)} evidence-backed problem(s) were confirmed."],
        )
    high_signals = [s for s in baseline.get("signals", []) if s.get("severity") == "HIGH"]
    checks = _review_checks(high_signals)
    if high_signals:
        return Assessment(
            "needs_review",
            [f"{signal['detail']}" for signal in high_signals],
            checks,
        )
    if hook_violations or not findings or _has_incomplete_check(findings):
        return Assessment(
            "needs_review",
            ["One or more checks could not establish a clean result."],
        )
    return Assessment("clean", ["All completed checks returned validated clean evidence."])


def _review_checks(signals: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            SIGNAL_HYPOTHESES[signal["name"]][0]
            for signal in signals
            if signal.get("name") in SIGNAL_HYPOTHESES
        }
    )


def _has_incomplete_check(findings: list[dict[str, Any]]) -> bool:
    return any(
        not finding["validation"]["valid"]
        or not finding.get("db_validated")
        or finding["verdict"] in {"inconclusive", "could_not_verify"}
        or finding.get("issue_state") == "needs_review"
        for finding in findings
    )
