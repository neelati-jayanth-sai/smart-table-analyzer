"""Report data model. Holds validated findings only — it never derives conclusions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .assessment import Assessment

REPORT_VERSION = "2.1.0"


@dataclass
class InvestigationReport:
    """Everything the report renderer needs, already validated."""

    investigation_id: int
    run_id: str
    table_name: str
    catalog_name: str
    schema_name: str
    status: str
    started_at: str
    completed_at: str | None
    snapshot_id: str | None
    baseline_score: dict[str, Any]
    score_explanation: dict[str, Any]
    findings: list[dict[str, Any]]
    knowledge_references: list[dict[str, Any]]
    trail: list[dict[str, Any]]
    hook_violations: list[dict[str, Any]]
    summary: dict[str, Any]
    assessment: Assessment
    warnings: list[str] = field(default_factory=list)
    version: str = REPORT_VERSION

    @property
    def root_causes(self) -> list[dict[str, Any]]:
        """Confirmed problems, most confident first."""
        confirmed = [
            f
            for f in self.findings
            if f.get("verdict") == "found"
            and f.get("issue_state") == "issue_found"
            and f.get("db_validated")
            and f["validation"]["valid"]
        ]
        return sorted(confirmed, key=lambda f: -(f.get("confidence") or 0.0))

    @property
    def recommendations(self) -> list[dict[str, Any]]:
        return [f for f in self.root_causes if f.get("recommendation")]

    @property
    def high_severity_signals(self) -> list[dict[str, Any]]:
        """Measured conditions that prevent a clean assessment."""
        signals = self.baseline_score.get("signals") or []
        return [signal for signal in signals if signal.get("severity") == "HIGH"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "investigation_id": self.investigation_id,
            "run_id": self.run_id,
            "table_name": self.table_name,
            "catalog_name": self.catalog_name,
            "schema_name": self.schema_name,
            "status": self.status,
            "lifecycle_state": self.status,
            "assessment": asdict(self.assessment),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "snapshot_id": self.snapshot_id,
            "warnings": self.warnings,
            "root_causes": [f["question"] for f in self.root_causes],
            "baseline_score": self.baseline_score,
            "score_explanation": self.score_explanation,
            "findings": self.findings,
            "knowledge_references": self.knowledge_references,
            "hook_violations": self.hook_violations,
            "trail": self.trail,
            "summary": self.summary,
        }
