"""Coercion helpers for LLM output that may or may not already be a string."""

from __future__ import annotations

import json


def to_str(value: object) -> str:
    return value if isinstance(value, str) else json.dumps(value, default=str)


def to_str_or_none(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else to_str(value)
