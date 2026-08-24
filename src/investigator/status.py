"""Terminal-status policy for an investigation run."""

from __future__ import annotations


def final_status(
    findings: list[dict],
    chains_concluded: int,
    chains_planned: int,
    step_count: int,
    max_steps: int,
) -> str:
    """Derive the terminal lifecycle state from evidence and budget use."""
    if not any(finding.get("evidence_ids") for finding in findings):
        return "failed"
    budget_exhausted = chains_concluded >= chains_planned or step_count >= max_steps
    return "completed" if budget_exhausted else "aborted"
