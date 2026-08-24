"""Authoritative locations for investigation persistence."""

from __future__ import annotations

from pathlib import Path


def investigation_db_path(repo_root: Path | str) -> Path:
    """Return the repository's canonical investigation database path."""
    return Path(repo_root) / "data" / "investigation.db"


def resolve_investigation_db_path(
    repo_root: Path | str, configured_path: Path | str | None = None
) -> Path:
    """Resolve an optional override without changing the canonical default."""
    if configured_path is None:
        return investigation_db_path(repo_root)
    candidate = Path(configured_path)
    return candidate if candidate.is_absolute() else Path(repo_root) / candidate
