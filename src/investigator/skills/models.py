"""Small, inspectable contracts for deterministic investigation skills."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckTemplate:
    """A checked-in read-only query and the result shape it promises."""

    identifier: str
    filename: str
    expected_columns: tuple[str, ...]


@dataclass(frozen=True)
class CheckSkill:
    """One selectable investigation capability behind a small interface."""

    identifier: str
    purpose: str
    template: CheckTemplate
    interpretation: str
    failure_policy: str = "Record unavailable evidence; do not infer a finding."
    required_inputs: tuple[str, ...] = ("table_name",)
