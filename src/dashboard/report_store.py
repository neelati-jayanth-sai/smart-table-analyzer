"""Load finalized report projections for the dashboard."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from src.database import InvestigationDb
from src.models import InvestigationReport
from src.reporting import ReportAssembler

from .artifact_reports import load_report


@dataclass(frozen=True)
class RunIndex:
    """Small history row that identifies a selectable investigation run."""

    investigation_id: int
    run_id: str
    table_name: str
    lifecycle_state: str
    started_at: str
    completed_at: str | None
    source: str
    artifact_path: Path | None = None

    @property
    def finalized(self) -> bool:
        return self.lifecycle_state == "completed"

    @property
    def label(self) -> str:
        timestamp = self.completed_at or self.started_at
        return f"{self.table_name} · {timestamp} · {self.source}"


class InvestigationReportStore:
    """Dashboard seam: run history and one assembled report per selected run."""

    def __init__(self, db_path: Path | str, reports_dir: Path | str = "reports"):
        self._db = InvestigationDb(db_path)
        self._assembler = ReportAssembler(self._db)
        self._reports_dir = Path(reports_dir)

    def list_runs(self) -> list[RunIndex]:
        database_runs = [
            RunIndex(
                investigation_id=row["investigation_id"],
                run_id=row["run_id"],
                table_name=row["table_name"],
                lifecycle_state=row["status"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                source="database",
            )
            for row in self._db.list_investigations()
        ]
        artifacts = self._artifact_runs()
        by_run = {run.run_id: run for run in database_runs}
        by_run.update({run.run_id: run for run in artifacts})
        return sorted(
            by_run.values(),
            key=lambda run: (run.lifecycle_state == "completed", _run_timestamp(run)),
            reverse=True,
        )

    def get_report(self, run: RunIndex) -> InvestigationReport:
        if run.artifact_path:
            return load_report(run.artifact_path)
        return self._assembler.assemble(run.investigation_id)

    def _artifact_runs(self) -> list[RunIndex]:
        if not self._reports_dir.exists():
            return []
        runs: list[RunIndex] = []
        for path in self._reports_dir.glob("*.json"):
            try:
                report = load_report(path)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            runs.append(
                RunIndex(
                    investigation_id=report.investigation_id,
                    run_id=report.run_id,
                    table_name=report.table_name,
                    lifecycle_state=report.status,
                    started_at=report.started_at,
                    completed_at=report.completed_at,
                    source="report artifact",
                    artifact_path=path,
                )
            )
        return runs

    @staticmethod
    def fingerprint(report: InvestigationReport) -> str:
        canonical = json.dumps(report.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _run_timestamp(run: RunIndex) -> str:
    return run.completed_at or run.started_at
