"""Compact a reviewed draft into a persisted finding."""

from __future__ import annotations

from src.investigator.state import InvestigationState, validate_state

from ._logging import _logged
from .finding_compaction import compact_to_finding_state


class FindingCompaction:
    """Mixin: persist the finding and reset per-check state."""

    @_logged
    def compact_to_trail(self, state: InvestigationState) -> InvestigationState:
        validate_state(state)
        new_state = compact_to_finding_state(state, self.db, self.quality_gate)
        return validate_state(new_state)
