"""One hypothesis, run to a conclusion.

    Hypothesis -> SQL -> Evidence -> Decide -> (follow-up | conclude)

The steps are sequential because each depends on the previous one's evidence.
"""

from __future__ import annotations

import logging
import threading
from copy import deepcopy
from typing import TYPE_CHECKING

from src.models import Finding
from src.models.state import FindingState, InvestigationState

from ..executors.finding_compaction import build_finding_state

if TYPE_CHECKING:
    from ..executors import InvestigationNodes
    from .runner import _CheckNumbers

logger = logging.getLogger(__name__)

_db_lock = threading.Lock()

MAX_FOLLOWUPS_PER_CHAIN = 2
_MAX_CRITIC_LOOPS = 2


def _run_one_check(
    nodes: "InvestigationNodes",
    state: InvestigationState,
    check_index: int,
    check_type: str,
    question: str,
) -> InvestigationState:
    """Run knowledge -> generate -> execute -> analyze -> critic -> compact once.

    Returns the resulting state. A blocked or failing query does not raise: it
    produces a low-confidence finding so the investigation keeps going and the
    report can warn about the degraded evidence.
    """
    check_state: InvestigationState = {
        **deepcopy(dict(state)),
        "check_count": check_index,
        "current_question": question,
        "current_check_type": check_type,
        "knowledge_consulted": [],
        "current_query": None,
        "query_result": None,
        "current_analysis": None,
        "retry_count": 0,
        "execution_status": None,
    }

    check_state = nodes.fetch_relevant_knowledge(check_state)
    check_state = nodes.generate_sql_query(check_state)

    max_retries = state.get("max_retries", 3)
    for attempt in range(max_retries + 1):
        check_state = nodes.execute_with_workbench(check_state)
        status = check_state.get("execution_status")
        if status == "success":
            break
        if attempt < max_retries:
            logger.warning(
                "Check %d %s (%s); regenerating SQL, attempt %d/%d",
                check_index, status, _error_of(check_state), attempt + 1, max_retries,
            )
            check_state = nodes.generate_sql_query(check_state)

    if check_state.get("execution_status") != "success":
        logger.warning(
            "Check %d could not produce query evidence (%s); analysing on metadata alone",
            check_index, check_state.get("execution_status"),
            extra={"investigation_id": check_state["investigation_id"]},
        )

    for attempt in range(_MAX_CRITIC_LOOPS):
        check_state = nodes.analyze_query_result(check_state)
        check_state = nodes.review_finding(check_state)
        is_last_attempt = attempt == _MAX_CRITIC_LOOPS - 1

        analysis = check_state.get("current_analysis") or {}
        if not analysis.get("approved", True):
            logger.warning(
                "Check %d rejected by Critic. Retrying. Feedback: %s",
                check_index, analysis.get("critic_feedback"),
            )
            if is_last_attempt:
                break
            check_state["critic_feedback"] = analysis.get("critic_feedback")
            continue

        finding_state = build_finding_state(check_state)
        is_valid, rejection_reason = nodes.quality_gate.validate(Finding(**finding_state))
        if is_valid or is_last_attempt:
            break

        logger.warning(
            "Check %d rejected by quality gate. Retrying. Reason: %s",
            check_index, rejection_reason,
        )
        check_state["critic_feedback"] = (
            f"Your finding was rejected by an automated quality gate: {rejection_reason}. "
            "Fix this specific issue and resubmit a complete, valid finding."
        )

    followup = _followup_question(check_state)
    with _db_lock:
        check_state = nodes.compact_to_trail(check_state)
    check_state["_followup_question"] = followup
    return check_state


def _error_of(state: InvestigationState) -> str:
    return (state.get("query_result") or {}).get("error") or "no error reported"


def _followup_question(state: InvestigationState) -> str | None:
    """The Decide step: does this evidence warrant one more test?"""
    analysis = state.get("current_analysis") or {}
    if not analysis.get("needs_followup"):
        return None
    question = (analysis.get("followup_question") or "").strip()
    return question or None


def _run_chain(
    nodes: "InvestigationNodes",
    state: InvestigationState,
    check_index: int,
    check_type: str,
    question: str,
    numbers: _CheckNumbers,
) -> list[FindingState]:
    """Run one hypothesis to conclusion, following up while the evidence demands it."""
    findings: list[FindingState] = []
    current_index, current_question = check_index, question

    for depth in range(MAX_FOLLOWUPS_PER_CHAIN + 1):
        try:
            check_state = _run_one_check(
                nodes, state, current_index, check_type, current_question
            )
        except Exception:
            logger.exception(
                "Check %d (%s) failed; continuing with the remaining checks",
                current_index, check_type,
            )
            return findings

        produced = check_state.get("findings", [])
        if produced:
            findings.append(produced[-1])

        followup = check_state.get("_followup_question")
        if not followup or depth == MAX_FOLLOWUPS_PER_CHAIN:
            break

        current_index = numbers.next()
        current_question = followup
        logger.info(
            "Check %s raised a follow-up as check %d: %s",
            check_type, current_index, followup,
        )
        state = {**state, "findings": list(state.get("findings", [])) + findings}

    return findings
