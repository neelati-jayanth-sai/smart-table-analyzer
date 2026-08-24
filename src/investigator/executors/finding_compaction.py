"""Compaction of a draft analysis into a persisted Finding."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.database import Finding
from src.models.finding import issue_state_for

from src.models.state import AnalysisState, FindingState, InvestigationState

if TYPE_CHECKING:
    from src.database import InvestigationDb

    from src.investigator.critic import FindingQualityGate

logger = logging.getLogger(__name__)


def build_finding_state(state: InvestigationState) -> FindingState:
    """Build a FindingState-shaped dict from the current draft analysis.

    Shared by the critic loop in `investigator/loop/chain.py`
    and the final compaction step below, so both agree on what a Finding
    looks like before it is validated.
    """
    analysis = dict(state.get("current_analysis") or AnalysisState(
        verdict="could_not_verify",
        exact_result=str(state.get("execution_status", "unknown")),
        rationale="No analysis available",
        evidence_ids=[], confidence=0.0, recommendation=None, alternatives=[],
        actionable_sql=None,
        issue_state="needs_review",
    ))
    # Remove loop-control fields that are not part of a Finding
    for internal in ("approved", "critic_feedback", "needs_followup", "followup_question"):
        analysis.pop(internal, None)
    analysis.setdefault("confidence", 0.0)
    analysis["issue_state"] = issue_state_for(str(analysis["verdict"]))

    return FindingState(
        check_num=state["check_count"],
        question=state.get("current_question") or "",
        validated=(state.get("execution_status") == "success"
                   and analysis["verdict"] != "could_not_verify"),
        check_type=state.get("current_check_type"),
        **analysis,
    )


def compact_to_finding_state(
    state: InvestigationState, db: "InvestigationDb", quality_gate: "FindingQualityGate"
) -> InvestigationState:
    finding_state = build_finding_state(state)
    finding = Finding(**finding_state)
    is_valid, rejection_reason = quality_gate.validate(finding)
    if not is_valid:
        logger.warning("Finding rejected by quality gate: %s (check %d)",
                       rejection_reason, state["check_count"],
                       extra={"investigation_id": state["investigation_id"]})
        finding_state = FindingState(
            check_num=state["check_count"],
            question=state.get("current_question") or "",
            validated=False,
            verdict="inconclusive",
            exact_result=finding.exact_result,
            rationale=f"Quality gate rejection: {rejection_reason}",
            evidence_ids=finding.evidence_ids,
            confidence=0.0,
            recommendation=None, alternatives=[],
            check_type=finding.check_type,
            actionable_sql=None,
            issue_state="needs_review",
        )
    db.record_finding(state["investigation_id"], Finding(**finding_state))
    findings = list(state.get("findings", []))
    findings.append(finding_state)
    return {
        **state, "findings": findings,
        "check_count": state["check_count"] + 1,
        "retry_count": 0, "current_question": None, "current_check_type": None,
        "current_query": None, "query_result": None, "current_analysis": None,
        "knowledge_consulted": [],
    }
