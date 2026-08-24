"""Runtime validation for InvestigationState invariants."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from src.models.state import InvestigationState


class StateValidationError(Exception):
    """Raised when an investigation state invariant is violated."""


def validate_state(state: InvestigationState) -> InvestigationState:
    """Validate that state satisfies core invariants and return it."""

    errors: list[str] = []

    if not state.get("investigation_id"):
        errors.append("Missing investigation_id")

    check_count = state.get("check_count", 0)
    max_checks = state.get("max_checks", 0)
    if check_count < 0:
        errors.append("check_count must be non-negative")
    if max_checks > 0 and check_count > max_checks:
        errors.append(f"check_count {check_count} exceeds max_checks {max_checks}")

    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 0)
    if retry_count < 0:
        errors.append("retry_count must be non-negative")
    if max_retries > 0 and retry_count > max_retries:
        errors.append(f"retry_count {retry_count} exceeds max_retries {max_retries}")

    step_count = state.get("step_count", 0)
    max_steps = state.get("max_steps", 0)
    if step_count < 0:
        errors.append("step_count must be non-negative")
    if max_steps < 0:
        errors.append("max_steps must be non-negative")

    if not isinstance(state.get("findings", []), list):
        errors.append("findings must be a list")

    if not isinstance(state.get("knowledge_consulted", []), list):
        errors.append("knowledge_consulted must be a list")

    if state.get("asked_questions") is not None and not isinstance(state["asked_questions"], list):
        errors.append("asked_questions must be a list")

    query_result = state.get("query_result")
    if query_result is not None and not isinstance(query_result.get("success"), bool):
        errors.append("query_result.success must be a boolean when present")

    if errors:
        raise StateValidationError("; ".join(errors))
    return state


def validated(node: Callable[[Any], InvestigationState]) -> Callable[[Any], InvestigationState]:
    """Decorator that validates state before and after a graph node runs."""

    @wraps(node)
    def wrapper(state: InvestigationState) -> InvestigationState:
        validate_state(state)
        new_state = node(state)
        validate_state(new_state)
        return new_state

    return wrapper
