"""Trust projection for the dashboard's just-completed investigation view."""

from __future__ import annotations

from typing import Any


def is_verified_finding(finding: dict[str, Any]) -> bool:
    """Require persisted claim validation and a successful executed query."""
    validation = finding.get("validation") or {}
    queries = finding.get("sql") or []
    return bool(
        finding.get("db_validated")
        and validation.get("valid")
        and any(query.get("status") == "success" for query in queries)
    )


def verified_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only findings whose proof survives both trust gates."""
    return [finding for finding in findings if is_verified_finding(finding)]


def verified_issue_recommendations(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return actions only where the persisted, executed finding confirmed an issue."""
    return [
        finding
        for finding in verified_findings(findings)
        if finding.get("issue_state") == "issue_found" and finding.get("recommendation")
    ]
