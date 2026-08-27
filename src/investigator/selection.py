"""Select the next registered skill from current investigation evidence."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.context import PromptProfile
from src.investigator.prompts import build_decide_prompt
from src.investigator.skills import get_skill
from src.investigator.skills.candidates import candidates
from src.models.state import InvestigationState
from src.utils import parse_json_response

logger = logging.getLogger(__name__)


def select_next_check(nodes, state: InvestigationState, used: set[str], fallback: bool = True) -> tuple[str, str] | None:
    """Let the Investigator choose one registered check, with safe fallback."""
    choices = candidates(list(state.get("signals") or []), used)
    if not fallback:
        choices = [choice for choice in choices if choice[0] == "partition_suggestions"]
    if (state.get("table_metadata") or {}).get("column_analysis", {}).get("status") != "completed":
        choices = [choice for choice in choices if choice[0] != "partition_suggestions"]
    if len(choices) == 1:
        return choices[0]
    proposed = _llm_choice(nodes, state, used, {check_id for check_id, _ in choices})
    if proposed is not None:
        return proposed
    return choices[0] if choices else None


def _llm_choice(nodes, state: InvestigationState, used: set[str], allowed: set[str]) -> tuple[str, str] | None:
    try:
        context = nodes.context_engine.render(PromptProfile.DECIDE, state)
        prompt = build_decide_prompt(context, state)
        signals = list(state.get("signals") or [])
        if signals:
            prompt += "\n\nMeasured signals:\n" + json.dumps(signals, default=str)
        parsed: dict[str, Any] = parse_json_response(
            nodes.llm.generate([{"role": "user", "content": prompt}]).get("content", "")
        ) or {}
        check_id = str(parsed.get("check_type") or "").strip()
        question = str(parsed.get("question") or "").strip()
        if get_skill(check_id) and check_id in allowed and check_id not in used and question:
            return check_id, question
    except Exception:
        logger.warning("Investigator selection unavailable; using measured evidence", exc_info=True)
    return None
