"""Dashboard execution seam for a single interactive investigation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re

from src.analyzer import AnalysisOutcome, SmartTableAnalyzer
from src.analyzer.progress import AnalysisProgress, ProgressCallback
from src.connectors import DellAIAAdapter
from src.database import InvestigationDb, KnowledgeStore, investigation_db_path
from src.query.snapshot_pinning import fetch_current_snapshot


@dataclass(frozen=True)
class AnalysisRequest:
    """Validated dashboard inputs for one table investigation."""

    table_name: str
    snapshot_id: str | None = None
    query_metrics_table: str | None = None
    metadata_profile: str = "deep"
    max_checks: int = 10

    def resolved_table(self) -> tuple[str, str, str]:
        parts = self.table_name.strip().split(".")
        if len(parts) != 3 or not all(_IDENTIFIER.fullmatch(part) for part in parts):
            raise ValueError("Enter a full catalog.schema.table name.")
        return parts[0], parts[1], self.table_name.strip()

    def resolved_metadata_profile(self) -> str:
        """Return the fixed metadata contract, accepting legacy inputs."""
        profile = self.metadata_profile.strip().lower()
        if profile not in {"fast", "shallow", "deep"}:
            raise ValueError("Metadata profile must be deep (legacy: fast/shallow accepted).")
        return "deep"

    def resolved_max_checks(self) -> int:
        """Return the fixed thorough investigation limit."""
        return 10


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class DashboardAnalysisRunner:
    """Starts one pipeline run while preserving the caller-owned Spark session."""

    def __init__(
        self,
        repo_root: Path,
        spark_acquirer=None,
        analyzer_factory=SmartTableAnalyzer,
    ):
        self.repo_root = repo_root
        self._spark_acquirer = spark_acquirer
        self._analyzer_factory = analyzer_factory

    def connect(self):
        """Configure certificates and return an active Spark Connect session."""
        if os.getenv("STA_RUNTIME") == "local":
            from src.runtime import LocalIcebergRuntime, LocalIcebergSession

            root = self.repo_root / "data" / "local-e2e"
            runtime = LocalIcebergRuntime.from_paths(
                os.getenv("STA_LOCAL_CATALOG", str(root / "catalog.db")),
                os.getenv("STA_LOCAL_WAREHOUSE", str(root / "warehouse")),
            )
            return LocalIcebergSession(runtime)
        from scripts import _investigation_cli as cli
        from pyspark.sql import SparkSession

        active = SparkSession.getActiveSession()
        if active is not None:
            return active
        if not cli.setup_ssl(self.repo_root):
            raise RuntimeError("IOMETE certificate is unavailable; set IOMETE_CERT_FILE before connecting.")
        spark_acquirer = self._spark_acquirer or cli.acquire_spark_session
        return spark_acquirer()[0]

    def run(
        self, spark, request: AnalysisRequest, progress: ProgressCallback | None = None
    ) -> AnalysisOutcome:
        """Run through the existing pipeline and write its report beside CLI reports."""
        from scripts import _investigation_cli as cli

        catalog, schema, table_name = request.resolved_table()
        self._emit(progress, "queued", f"Queued {table_name}")
        db_path = investigation_db_path(self.repo_root)
        db = InvestigationDb(db_path)
        cli.seed_knowledge(db_path, self.repo_root)
        if request.snapshot_id:
            snapshot_id = request.snapshot_id
            self._emit(progress, "snapshot_ready", f"Using supplied snapshot {snapshot_id}")
        else:
            self._emit(progress, "pinning_snapshot", "Capturing the current Iceberg snapshot")
            snapshot_id = fetch_current_snapshot(spark, table_name)
            self._emit(progress, "snapshot_ready", "Snapshot captured" if snapshot_id else "No snapshot available")
        analyzer = self._analyzer_factory(
            spark=spark,
            db=db,
            llm=self._llm(),
            knowledge=KnowledgeStore(db_path, repo_root=self.repo_root),
            max_checks=request.resolved_max_checks(),
            max_retries=3,
            max_workers=1,
            metadata_profile=request.resolved_metadata_profile(),
            progress=progress,
        )
        return analyzer.analyze(
            table_name=table_name,
            catalog_name=catalog,
            schema_name=schema,
            snapshot_id=snapshot_id,
            query_metrics_table=request.query_metrics_table or None,
            output_dir=self.repo_root / "reports",
        )

    @staticmethod
    def _emit(progress: ProgressCallback | None, stage: str, message: str) -> None:
        if progress is not None:
            progress(AnalysisProgress(stage, message))

    @staticmethod
    def _llm():
        if os.getenv("LLM_PROVIDER", "dell").lower() == "ollama":
            from src.connectors import OllamaCloudAdapter

            return OllamaCloudAdapter.from_env()
        return DellAIAAdapter.from_env()
