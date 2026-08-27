"""Result value returned by the full analyzer pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.context import InvestigationContext
from src.investigator.investigator import InvestigationResult


@dataclass
class AnalysisOutcome:
    """One completed investigation and its report artifacts."""

    investigation_id: int
    result: InvestigationResult
    context: InvestigationContext
    report_path: Path | None
    unvalidated_findings: int
