"""Helper functions for the run_investigation CLI.

Environment, Spark, and file plumbing only. Metadata collection lives in
`src/analyzer/legacy_analyzer.py`; orchestration lives in
`src/analyzer/pipeline.py`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession

from scripts import init_investigation_db as init_db
from src.database import InvestigationDb
from src.reporting import ReportAssembler, ReportWriter


def setup_logging(level: str | None = None, log_file: Path | None = None) -> None:
    """Configure investigation-aware logging once, for the whole process.

    Every record carries the investigation id when the caller supplied one, so
    concurrent checks stay attributable in the log.
    """
    resolved = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    class _InvestigationFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if not hasattr(record, "investigation_id"):
                record.investigation_id = "-"
            return True

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s [inv:%(investigation_id)s] %(name)s: %(message)s"
    )
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(_InvestigationFilter())

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(resolved)
    logging.getLogger("py4j").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def setup_ssl(repo_root: Path) -> Path | None:
    """Configure SSL certificates for Spark Connect and HTTP clients."""
    cert_file = os.getenv("IOMETE_CERT_FILE", "certs/CertificateAuthoritykob.cer")
    cert_path = repo_root / cert_file
    if not cert_path.exists():
        return None
    abs_cert = str(cert_path.absolute())
    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = abs_cert
    os.environ["REQUESTS_CA_BUNDLE"] = abs_cert
    os.environ["SSL_CERT_FILE"] = abs_cert
    return cert_path


def build_spark_url() -> str:
    """Build the Spark Connect URL from environment variables."""
    return (
        f"sc://{os.getenv('IOMETE_HOST')}:443/;"
        f"cluster={os.getenv('IOMETE_LAKEHOUSE')};"
        f"data_plane={os.getenv('IOMETE_DATA_PLANE')};"
        f"use_ssl=true;"
        f"user_id={os.getenv('IOMETE_USER_ID')};"
        f"api_token={os.getenv('IOMETE_API_TOKEN')}"
    )


def resolve_table(args: Any) -> tuple[str, str, str]:
    """Return (catalog, schema, full_table_name) from CLI args and environment."""
    table = args.table
    parts = table.split(".")
    if len(parts) >= 3:
        catalog = parts[0]
        schema = parts[1]
        full_table = table
    else:
        catalog = args.catalog or os.getenv("IOMETE_CATALOG", "")
        schema = args.schema or os.getenv("IOMETE_NAMESPACE", "")
        full_table = f"{catalog}.{schema}.{table}"
    if not catalog or not schema:
        raise ValueError(
            "Catalog and schema are required (provide --table as catalog.schema.table"
            " or use --catalog/--schema)"
        )
    return catalog, schema, full_table


def seed_knowledge(db_path: Path, repo_root: Path) -> int:
    """Ensure the SQLite knowledge index is seeded from authored markdown."""
    entries = init_db.scan_knowledge_entries(repo_root)
    if not entries:
        return 0
    return init_db.seed_knowledge_index(db_path, entries)


def compute_baseline(spark, table_name: str) -> dict[str, Any]:
    """Baseline score only. Prefer `LegacyAnalyzer.collect` for the full context."""
    from src.analyzer.metrics import collect_raw_metrics, extract_query_patterns
    from src.calculators.baseline_scorer import score as compute_score

    return compute_score(
        collect_raw_metrics(spark, table_name), extract_query_patterns(spark, table_name)
    )


def write_report(
    investigation_id: int,
    db: InvestigationDb,
    output_dir: Path,
    output_path: Path | str | None = None,
) -> Path:
    """Assemble the investigation report and write Markdown + JSON sidecar."""
    report = ReportAssembler(db).assemble(investigation_id)
    return ReportWriter(output_dir).write(report, output_path)


def acquire_spark_session(existing: SparkSession | None = None) -> tuple[SparkSession, bool]:
    """Return a supplied or active session without taking ownership of it."""
    if existing is not None:
        return existing, False
    active = SparkSession.getActiveSession()
    if active is not None:
        return active, False
    session = SparkSession.builder.appName("investigator-cli").remote(build_spark_url()).getOrCreate()
    return session, True


def create_spark_session() -> SparkSession:
    """Create a remote Spark Connect session for IOMETE."""
    return acquire_spark_session()[0]
