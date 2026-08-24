"""Deterministic guards applied to LLM output before it becomes a finding."""

from __future__ import annotations

from src.models.state import InvestigationState

_PLACEHOLDER_TABLE_NAMES = [
    "your_catalog.your_database.your_table",
    "my_db.my_table",
    "your_table",
    "<table_name>",
]


def sanitize_actionable_sql(sql: str | None, real_table_name: str | None) -> str | None:
    """Replace placeholder table names in Critic/Analyst SQL with the real one.

    LLMs occasionally emit boilerplate table names (e.g. `my_db.my_table`)
    instead of the fully-qualified table actually under investigation. This
    is a deterministic safety net on top of the prompt-level instructions.
    """
    if not sql or not real_table_name:
        return sql
    sanitized = sql
    for placeholder in _PLACEHOLDER_TABLE_NAMES:
        sanitized = sanitized.replace(placeholder, real_table_name)
    return sanitized


def confidence_for(
    parsed: dict, state: InvestigationState, fallback: float | None = None
) -> float:
    """Every finding carries a confidence, whether or not the LLM supplied one.

    A stated value is trusted once clamped to [0, 1]; otherwise confidence is
    derived from what the evidence actually supports.
    """
    for candidate in (parsed.get("confidence"), fallback):
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            return round(min(max(float(candidate), 0.0), 1.0), 2)

    verdict = str(parsed.get("verdict", "inconclusive"))
    if verdict in ("inconclusive", "could_not_verify"):
        return 0.2
    if state.get("execution_status") != "success":
        return 0.3
    return 0.7 if parsed.get("evidence_ids") else 0.4
