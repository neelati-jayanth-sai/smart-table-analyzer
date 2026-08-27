"""Small presentation helpers shared across read-only projections."""

from __future__ import annotations

from typing import Any


def human_bytes(value: Any) -> str:
    """Format a byte count without losing meaning at fixture-scale values."""
    if not isinstance(value, (int, float)):
        return "not recorded"
    amount = float(value)
    if amount < 1_000:
        return f"{amount:.0f} bytes"
    if amount < 1_000_000:
        return f"{_decimal(amount / 1_000)} KB"
    if amount < 1_000_000_000:
        return f"{_decimal(amount / 1_000_000)} MB"
    return f"{_decimal(amount / 1_000_000_000)} GB"


def _decimal(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")
