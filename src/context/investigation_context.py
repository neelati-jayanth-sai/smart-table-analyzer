"""The investigation context: one run's cached facts and running state.

Built once by the Legacy Analyzer, mutated only by the Investigator as checks
complete. Deliberately not a retriever, an agent, or anything backed by
embeddings — it is a dataclass holding facts that were already measured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InvestigationContext:
    """Cached facts and running state for one investigation.

    Built once by the Legacy Analyzer, mutated only by the Investigator as
    checks complete. Large payloads (raw query rows, manifest listings) never
    enter it — those stay in Spark and SQLite and are referenced by evidence ID.
    """

    table_name: str
    catalog_name: str = ""
    schema_name: str = ""
    snapshot_id: str | None = None
    investigation_id: int | None = None

    metadata: dict[str, Any] = field(default_factory=dict)
    signals: list[dict[str, Any]] = field(default_factory=list)
    baseline: dict[str, Any] = field(default_factory=dict)

    completed_checks: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------ mutation

    def record_finding(self, finding: dict[str, Any]) -> None:
        """Track one completed check: its type, its evidence, its conclusion."""
        self.findings.append(finding)
        check_type = finding.get("check_type")
        if check_type and check_type not in self.completed_checks:
            self.completed_checks.append(check_type)
        for evidence_id in finding.get("evidence_ids") or []:
            if evidence_id not in self.evidence_refs:
                self.evidence_refs.append(evidence_id)

    # -------------------------------------------------------------- reading

    @property
    def is_empty_table(self) -> bool:
        return bool((self.baseline.get("dimensions") or {}).get("is_empty"))

    def active_signals(self, min_severity: str = "MEDIUM") -> list[dict[str, Any]]:
        """Signals at or above a severity, strongest first."""
        order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        floor = order.get(min_severity.upper(), 1)
        return sorted(
            (s for s in self.signals if order.get(s.get("severity", "LOW"), 1) >= floor),
            key=lambda s: -order.get(s.get("severity", "LOW"), 1),
        )

    def summary_lines(self) -> list[str]:
        """The compact prompt block described in the architecture contract."""
        dims = self.baseline.get("dimensions") or {}
        lines = [f"TABLE: {self.table_name}", ""]
        for label, key in (
            ("Rows", "row_count"),
            ("Files", "num_data_files"),
            ("Partitions", "partition_count"),
            ("Snapshots", "snapshot_count"),
        ):
            if key in dims:
                lines.append(f"{label}: {dims[key]:,}" if isinstance(dims[key], int)
                             else f"{label}: {dims[key]}")
        if self.signals:
            lines += ["", "Signals"]
            lines += [f"- {s['name']}: {s['severity']}" for s in self.active_signals("LOW")]
        if self.findings:
            lines += ["", "Completed"]
            lines += [
                f"- {f.get('check_type', 'check')}: {f.get('verdict', 'unknown')}"
                for f in self.findings
            ]
        return lines

    def to_state(self, investigation_id: int | None = None, **overrides) -> dict[str, Any]:
        """Project the context into the InvestigationState the nodes consume."""
        state: dict[str, Any] = {
            "investigation_id": investigation_id or self.investigation_id,
            "table_name": self.table_name,
            "baseline_score": self.baseline,
            "table_metadata": self.metadata,
            "signals": self.signals,
            "findings": list(self.findings),
            "asked_questions": [f.get("question", "") for f in self.findings],
            "check_count": len(self.findings),
            "retry_count": 0,
            "step_count": 0,
            "status": "running",
        }
        state.update(overrides)
        return state
