"""Shared preparation seam for every registered deterministic check."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import get_skill
from .renderer import TemplateRenderError, render


class CheckPreparationError(ValueError):
    """A selected check cannot become a safe executable request."""


@dataclass(frozen=True)
class PreparedCheck:
    identifier: str
    query: str


def prepare(check_id: str, table_name: str) -> PreparedCheck:
    """Resolve one allowlisted check to its checked-in SQL template."""
    skill = get_skill(check_id)
    if skill is None:
        raise CheckPreparationError(f"Unknown deterministic check: {check_id}")
    try:
        return PreparedCheck(skill.identifier, render(skill, table_name))
    except (OSError, TemplateRenderError) as exc:
        raise CheckPreparationError(f"Could not prepare {check_id}: {exc}") from exc
