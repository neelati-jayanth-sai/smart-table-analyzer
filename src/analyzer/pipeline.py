"""Single execution path: deterministic collection, investigation, then report."""

from __future__ import annotations

import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.database import InvestigationDb
from src.context import InvestigationContext
from src.evidence import (
    CollectionEvidenceAdapter,
    persist_collection_evidence,
    persist_column_profile_evidence,
)
from src.investigator.critic import run_final_review
from src.investigator import Investigator
from src.investigator.investigator import InvestigationResult
from src.query import QueryWorkbench, create_investigation_hooks
from src.query.snapshot_pinning import fetch_current_snapshot
from src.metadata.collection_profile import MetadataCollectionProfile

from .collection_stage import collect_core, complete_profile, report_core_findings
from .outcome import AnalysisOutcome
from .progress import AnalysisProgress, ProgressCallback
from .report_output import count_unvalidated, write_report
logger = logging.getLogger(__name__)


class SmartTableAnalyzer:
    """Run one table through the full pipeline."""

    def __init__(
        self,
        spark,
        db: InvestigationDb,
        llm,
        knowledge,
        max_checks: int = 10,
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
        self.metadata_profile = MetadataCollectionProfile.from_name(metadata_profile or "deep")
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
        if snapshot_id is None:
            snapshot_id = fetch_current_snapshot(self.spark, table_name)
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
            context = collect_core(self.spark, self.metadata_profile, table_name, catalog_name,
                                   schema_name, snapshot_id, query_metrics_table)
            context.investigation_id = investigation_id
            context.evidence_refs.extend(
                persist_collection_evidence(
                    self.db, investigation_id, CollectionEvidenceAdapter().build(context)
                )
            )
            self.db.record_baseline_score(
                investigation_id,
                context.baseline["overall"],
                context.baseline["dimensions"],
                context.signals,
                {"partition_analysis": context.metadata.get("partition_analysis", {})},
                context.baseline.get("score_status", "complete"),
                context.baseline.get("score_reason"),
            )
            report_core_findings(self._progress, context, investigation_id)
            context, result = self._investigate_with_profile(investigation_id, context)
            self.db.record_final_review(investigation_id, run_final_review(self.llm, self.db, investigation_id))
        except Exception as exc:
            logger.exception(
                "Investigation failed before conclusions were reached",
                extra={"investigation_id": investigation_id},
            )
            self.db.complete_investigation(investigation_id, "failed")
            self._progress("error", str(exc), investigation_id)
            raise

        unvalidated = count_unvalidated(self.db, investigation_id)
        self._progress("rendering_report", "Rendering the investigation report", investigation_id)
        report_path = write_report(self.db, investigation_id, output_dir, output_path)
        self._progress("report_complete", "Investigation report is ready", investigation_id)

        return AnalysisOutcome(
            investigation_id=investigation_id,
            result=result,
            context=context,
            report_path=report_path,
            unvalidated_findings=unvalidated,
        )

    def _progress(self, stage: str, message: str, investigation_id: int) -> None:
        try:
            self.db.append_timeline_event(
                investigation_id, stage, message, status=_timeline_status(stage)
            )
        except Exception:
            logger.exception("Could not persist investigation timeline event")
        if self.progress is not None:
            self.progress(AnalysisProgress(stage, message, investigation_id))

    def _investigate_with_profile(
        self, investigation_id: int, context: InvestigationContext
    ) -> tuple[InvestigationContext, InvestigationResult]:
        """Run full profiling beside the initial evidence investigation."""
        if not self.metadata_profile.analyze_column_stats:
            self._progress("investigating", "I am testing the evidence collected so far.", investigation_id)
            return context, self._investigate(investigation_id, context)
        self._progress("profiling_columns", "I am profiling every primitive column while I investigate the first findings.", investigation_id)
        with ThreadPoolExecutor(max_workers=1) as pool:
            profile = pool.submit(complete_profile, self.spark, self.metadata_profile, context)
            self._progress("investigating", "I am testing the evidence collected so far.", investigation_id)
            result = self._investigate(investigation_id, context)
            context = profile.result()
        context.evidence_refs.append(persist_column_profile_evidence(self.db, investigation_id, context))
        self._progress("profile_complete", "Full column profile is complete; I am reconciling any new partition evidence.", investigation_id)
        if any(signal.get("name") == "unpartitioned" for signal in context.signals):
            result = self._investigate(investigation_id, context, max_checks=1, reconciliation=True)
        return context, result

    def _investigate(
        self, investigation_id: int, context: InvestigationContext, max_checks: int | None = None,
        reconciliation: bool = False,
    ) -> InvestigationResult:
        """Run mandatory evidence-backed investigation checks."""
        workbench = self._build_workbench(context)
        investigator = Investigator(
            llm=self.llm,
            workbench=workbench,
            knowledge_retrieval=self.knowledge,
            db=self.db,
            db_path=self.db.db_path,
            max_checks=max_checks or self.max_checks,
            max_retries_per_check=self.max_retries,
            max_workers=self.max_workers,
        )
        return investigator.run_investigation(
            investigation_id, context.table_name, context.baseline, context=context,
            reconciliation=reconciliation,
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


def _timeline_status(stage: str) -> str:
    if stage == "finding":
        return "confirmed"
    if stage in {"profiling_columns", "investigating", "collecting_metadata"}:
        return "pending"
    if stage == "error":
        return "failed"
    if stage in {"profile_complete", "report_complete"}:
        return "completed"
    return "info"
