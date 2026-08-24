"""Domain models shared across the pipeline.

These belong to the domain, not to the database: the Investigator produces a
`Finding`, the reporting layer renders one, and SQLite merely stores one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Investigation lifecycle, ordered from earliest to latest; terminal states last.
LIFECYCLE_STATES = (
    "running",
    "metadata_collected",
    "planning",
    "checks_running",
    "evidence_validated",
    "completed",
    "failed",
    "aborted",
)

TERMINAL_STATES = ("completed", "failed", "aborted")


def issue_state_for(verdict: str) -> str:
    """Derive the reportable issue state from the answer to a check."""
    if verdict == "found":
        return "issue_found"
    if verdict == "not_found":
        return "no_issue_found"
    return "needs_review"


@dataclass
class Finding:
    """One evidence-backed answer to one investigation question."""

    check_num: int
    question: str
    exact_result: str
    verdict: str
    rationale: str
    evidence_ids: list[str]
    recommendation: str | None = None
    alternatives: list[str] = field(default_factory=list)
    validated: bool = False
    check_type: str | None = None
    actionable_sql: str | None = None
    confidence: float | None = None
    issue_state: str = "needs_review"


@dataclass
class Investigation:
    """A persisted investigation run."""

    investigation_id: int
    run_id: str
    table_name: str
    catalog_name: str
    schema_name: str
    status: str
    max_checks: int
    current_check: int
    started_at: str
    completed_at: str | None = None
    snapshot_id: str | None = None
    baseline_score: dict[str, Any] | None = None
