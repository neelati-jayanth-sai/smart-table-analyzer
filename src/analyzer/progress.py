"""Progress events emitted by the full investigation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AnalysisProgress:
    """One human-readable lifecycle update for an investigation run."""

    stage: str
    message: str
    investigation_id: int | None = None


ProgressCallback = Callable[[AnalysisProgress], None]
