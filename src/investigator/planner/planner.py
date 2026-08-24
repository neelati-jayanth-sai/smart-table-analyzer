"""Adaptive hypothesis planning.

Signals from the Legacy Analyzer say what was measured; the Investigator decides
which measurements are worth a test and in what order. There is no fixed
checklist — the fallbacks exist so a planner outage degrades the investigation
instead of ending it.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from src.models.state import InvestigationState

from .hypotheses import FALLBACK_SEQUENCE, signal_hypotheses

if TYPE_CHECKING:
    from ..executors import InvestigationNodes

logger = logging.getLogger(__name__)


def plan_checks(
    state: InvestigationState,
    max_checks: int,
    nodes: "InvestigationNodes | None" = None,
) -> list[tuple[int, str, str]]:
    """Return (index, check_type, question) for the checks worth running.

    Order of preference:
      1. The LLM's ranked hypotheses, grounded in the measured signals.
      2. Hypotheses derived directly from the signals that fired.
      3. The generic coverage sequence.
    """
    if max_checks <= 0:
        return []

    signals = list(state.get("signals") or [])
    specs: list[tuple[int, str, str]] = []
    used: set[str] = set()

    if nodes is not None:
        for check_type, question in llm_hypotheses(nodes, state, signals, max_checks):
            if check_type not in used:
                specs.append((len(specs), check_type, question))
                used.add(check_type)

    for check_type, question in signal_hypotheses(signals) + FALLBACK_SEQUENCE:
        if len(specs) >= max_checks:
            break
        if check_type not in used:
            specs.append((len(specs), check_type, question))
            used.add(check_type)

    specs = specs[:max_checks]
    logger.info(
        "Planned %d check(s): %s", len(specs), ", ".join(ct for _, ct, _ in specs)
    )
    return specs


def llm_hypotheses(
    nodes: "InvestigationNodes",
    state: InvestigationState,
    signals: list[dict[str, Any]],
    max_checks: int,
) -> list[tuple[str, str]]:
    """Ask the Investigator to rank what deserves testing. Never raises."""
    try:
        from src.context import PromptProfile
        from src.investigator.prompts import build_decide_prompt
        from src.utils import parse_json_response

        hypotheses: list[tuple[str, str]] = []
        planning_state = {**dict(state), "findings": [], "check_count": 0}

        for _ in range(max_checks):
            context = nodes.context_engine.render(PromptProfile.DECIDE, planning_state)
            prompt = build_decide_prompt(context, planning_state)
            if signals:
                prompt += (
                    "\n\nMeasured signals (facts, not conclusions):\n"
                    + json.dumps(signals, default=str)
                    + "\n\nInvestigate what these signals make suspicious. Ignore any "
                      "dimension the signals show is healthy."
                )
            response = nodes.llm.generate([{"role": "user", "content": prompt}])
            parsed = parse_json_response(response.get("content", "")) or {}
            check_type = (parsed.get("check_type") or "").strip()
            question = (parsed.get("question") or "").strip()
            if not check_type or not question:
                break
            hypotheses.append((check_type, question))
            planning_state["findings"] = [
                {"check_type": ct, "question": q, "verdict": "planned"}
                for ct, q in hypotheses
            ]
            planning_state["check_count"] = len(hypotheses)
        return hypotheses
    except Exception:
        logger.warning(
            "LLM planning unavailable; falling back to signal-derived hypotheses",
            exc_info=True,
        )
        return []
