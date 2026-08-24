"""Single execution path: deterministic collection, investigation, then report."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.database import InvestigationDb
from src.context import InvestigationContext
from src.investigator import Investigator
from src.investigator.investigator import InvestigationResult
from src.query import QueryWorkbench, create_investigation_hooks
from src.reporting import ReportAssembler, ReportWriter
from src.validation import ClaimValidator
from src.metadata.collection_profile import MetadataCollectionProfile

from .legacy_analyzer import LegacyAnalyzer
from .progress import AnalysisProgress, ProgressCallback

logger = logging.getLogger(__name__)


@dataclass
class AnalysisOutcome:
    investigation_id: int
    result: InvestigationResult
    context: InvestigationContext
    report_path: Path | None
    unvalidated_findings: int


class SmartTableAnalyzer:
    """Run one table through the full pipeline."""

    def __init__(
        self,
        spark,
        db: InvestigationDb,
        llm,
        knowledge,
        max_checks: int = 5,
        max_retries: int = 3,
        max_workers: int = 1,
        metadata_profile: str | None = None,
        progress: ProgressCallback | None = None,
    ):
        self.spark = spark
        self.db = db
        self.llm = llm
        self.knowledge = knowledge
        self.max_checks = max_checks
        self.max_retries = max_retries
        self.max_workers = max_workers
        self.metadata_profile = MetadataCollectionProfile.from_name(metadata_profile)
        self.progress = progress

    def analyze(
        self,
        table_name: str,
        catalog_name: str = "",
        schema_name: str = "",
        snapshot_id: str | None = None,
        query_metrics_table: str | None = None,
        output_dir: Path | str | None = None,
        output_path: Path | str | None = None,
    ) -> AnalysisOutcome:
        run_id = str(uuid.uuid4())
        investigation_id = self.db.create_investigation(
            run_id=run_id,
            table_name=table_name,
            catalog_name=catalog_name,
            schema_name=schema_name,
            max_checks=self.max_checks,
            snapshot_id=snapshot_id,
        )
        logger.info("Investigation %s started for %s", investigation_id, table_name,
                    extra={"investigation_id": investigation_id})
        self._progress("collecting_metadata", "Collecting Iceberg metadata", investigation_id)

        try:
            context = self._collect(
                table_name, catalog_name, schema_name, snapshot_id, query_metrics_table
            )
            context.investigation_id = investigation_id
            self.db.record_baseline_score(
                investigation_id,
                context.baseline["overall"],
                context.baseline["dimensions"],
                context.signals,
                {"partition_analysis": context.metadata.get("partition_analysis", {})},
            )

            self._progress("investigating", "Running evidence checks", investigation_id)
            result = self._investigate(investigation_id, context)
        except Exception as exc:
            logger.exception(
                "Investigation failed before conclusions were reached",
                extra={"investigation_id": investigation_id},
            )
            self.db.complete_investigation(investigation_id, "failed")
            self._progress("error", str(exc), investigation_id)
            raise

        unvalidated = self._count_unvalidated(investigation_id)
        self._progress("rendering_report", "Rendering the investigation report", investigation_id)
        report_path = self._write_report(investigation_id, output_dir, output_path)
        self._progress("report_complete", "Investigation report is ready", investigation_id)

        return AnalysisOutcome(
            investigation_id=investigation_id,
            result=result,
            context=context,
            report_path=report_path,
            unvalidated_findings=unvalidated,
        )

    def _progress(self, stage: str, message: str, investigation_id: int) -> None:
        if self.progress is not None:
            self.progress(AnalysisProgress(stage, message, investigation_id))

    def _collect(
        self,
        table_name: str,
        catalog_name: str,
        schema_name: str,
        snapshot_id: str | None,
        query_metrics_table: str | None,
    ) -> InvestigationContext:
        """Read metadata once and produce the deterministic source of truth."""
        return LegacyAnalyzer(self.spark, self.metadata_profile).collect(
            table_name, catalog_name, schema_name, snapshot_id, query_metrics_table
        )

    def _investigate(
        self, investigation_id: int, context: InvestigationContext
    ) -> InvestigationResult:
        """Run mandatory evidence-backed investigation checks."""
        workbench = self._build_workbench(context)
        investigator = Investigator(
            llm=self.llm,
            workbench=workbench,
            knowledge_retrieval=self.knowledge,
            db=self.db,
            db_path=self.db.db_path,
            max_checks=self.max_checks,
            max_retries_per_check=self.max_retries,
            max_workers=self.max_workers,
        )
        return investigator.run_investigation(
            investigation_id, context.table_name, context.baseline, context=context
        )

    def _build_workbench(self, context: InvestigationContext) -> QueryWorkbench:
        """Build evidence-query access using the cached metadata context."""
        hooks = create_investigation_hooks(
            [context.catalog_name] if context.catalog_name else None,
            [context.schema_name] if context.schema_name else None,
        )
        return QueryWorkbench(
            self.spark,
            hooks=hooks,
            snapshot_id=context.snapshot_id,
            timeout_seconds=int(os.getenv("QUERY_TIMEOUT_SECONDS", "180")),
            row_limit=int(os.getenv("QUERY_ROW_LIMIT", "500")),
            table_name=context.table_name,
            table_metadata=context.metadata,
        )

    def _count_unvalidated(self, investigation_id: int) -> int:
        validator = ClaimValidator(self.db)
        return sum(
            1
            for finding in self.db.list_findings(investigation_id)
            if not validator.validate(investigation_id, finding).valid
        )

    def _write_report(
        self,
        investigation_id: int,
        output_dir: Path | str | None,
        output_path: Path | str | None,
    ) -> Path | None:
        """Stage 3 — render validated findings. Never blocks the investigation."""
        if output_dir is None and output_path is None:
            return None
        try:
            report = ReportAssembler(self.db).assemble(investigation_id)
            return ReportWriter(output_dir or Path("reports")).write(report, output_path)
        except Exception:
            logger.exception(
                "Report generation failed; findings remain in the database",
                extra={"investigation_id": investigation_id},
            )
            return None
