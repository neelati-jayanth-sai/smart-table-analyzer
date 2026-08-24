"""Shared step logging for executor nodes."""

from __future__ import annotations

import logging

from src.models.state import InvestigationState

logger = logging.getLogger(__name__)


def _logged(node):
    """Log entry/exit of one investigation step and advance the step counter."""
    def wrapper(self, state: InvestigationState) -> InvestigationState:
        inv_id = state["investigation_id"]
        logger.info("%s: enter", node.__name__, extra={"investigation_id": inv_id})
        state["step_count"] = state.get("step_count", 0) + 1
        new_state = node(self, state)
        logger.info(
            "%s: exit step=%d", node.__name__, new_state.get("step_count", 0),
            extra={"investigation_id": new_state["investigation_id"]},
        )
        return new_state
    return wrapper
