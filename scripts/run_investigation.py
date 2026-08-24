"""CLI orchestrator for running a full table investigation."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv

load_dotenv(repo_root / ".env")

from scripts import _investigation_cli as cli
from src.analyzer.pipeline import SmartTableAnalyzer
from src.connectors import DellAIAAdapter
from src.database import InvestigationDb, resolve_investigation_db_path
from src.database.knowledge_store import KnowledgeStore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an investigation on an IOMETE table")
    parser.add_argument("--table", required=True, help="Full three-part table name (catalog.schema.table)")
    parser.add_argument("--catalog", default=os.getenv("IOMETE_CATALOG"), help="Catalog override")
    parser.add_argument("--schema", default=os.getenv("IOMETE_NAMESPACE"), help="Schema override")
    parser.add_argument("--alation-table", default=None, help="Actual table name in Alation (for replica tables)")
    parser.add_argument("--db", default=None, help="Optional SQLite database override")
    parser.add_argument("--max-checks", type=int, default=5, help="Maximum investigation checks")
    parser.add_argument("--snapshot", default=None, help="Optional snapshot ID to pin")
    parser.add_argument("--query-metrics-table", default=None, dest="query_metrics_table",
                        help="Production table name to use for IOMETE query log metrics (defaults to --table)")
    parser.add_argument("--metadata-profile", choices=("fast", "deep"), default=None,
                        help="Collection profile; fast is metadata-only (default), deep reads table data")
    parser.add_argument("--output", default=None, help="Optional report output path")
    parser.add_argument("--log-level", default=None, help="Logging level (default LOG_LEVEL or INFO)")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    cli.setup_logging(args.log_level, repo_root / "logs" / "investigation.log")

    if args.alation_table:
        os.environ["ALATION_ACTUAL_TABLE_NAME"] = args.alation_table

    cert_path = cli.setup_ssl(repo_root)
    if not cert_path:
        print(f"Certificate not found: {os.getenv('IOMETE_CERT_FILE')}")
        return 1

    catalog, schema, table_name = cli.resolve_table(args)

    if args.query_metrics_table:
        os.environ["IOMETE_QUERY_METRICS_TABLE"] = args.query_metrics_table

    spark, owns_spark = cli.acquire_spark_session()
    from src.query.snapshot_pinning import fetch_current_snapshot

    snapshot_id = args.snapshot or fetch_current_snapshot(spark, table_name)
    if snapshot_id:
        print(f"Pinning investigation to snapshot {snapshot_id}")

    try:
        db_path = resolve_investigation_db_path(repo_root, args.db)
        db = InvestigationDb(db_path)
        print(f"Seeded {cli.seed_knowledge(db_path, repo_root)} knowledge entries")

        output_path = None
        if args.output:
            output_path = Path(args.output)
            if not output_path.is_absolute():
                output_path = repo_root / output_path

        analyzer = SmartTableAnalyzer(
            spark=spark,
            db=db,
            llm=DellAIAAdapter.from_env(),
            knowledge=KnowledgeStore(db_path, repo_root=repo_root),
            max_checks=args.max_checks,
            max_retries=int(os.getenv("MAX_CHECK_RETRIES", "3")),
            metadata_profile=args.metadata_profile,
        )

        print(f"Investigating {table_name}...")
        outcome = analyzer.analyze(
            table_name=table_name,
            catalog_name=catalog,
            schema_name=schema,
            snapshot_id=snapshot_id,
            output_dir=repo_root / "reports",
            output_path=output_path,
        )

        findings = db.list_findings(outcome.investigation_id)
        validated = len(findings) - outcome.unvalidated_findings
        if outcome.unvalidated_findings:
            print(
                f"Warning: {outcome.unvalidated_findings} finding(s) have unverified evidence "
                "IDs and appear as unvalidated in the report."
            )

        signals = ", ".join(
            f"{s['name']}={s['severity']}" for s in outcome.context.signals
        ) or "none"
        print(f"\nSignals detected: {signals}")
        print(f"Investigation {outcome.investigation_id} status: {outcome.result.status}")
        print(f"Checks completed: {outcome.result.checks_completed}")
        print(f"Findings: {len(findings)} ({validated} validated)")
        if outcome.report_path:
            print(f"Report written to: {outcome.report_path}")
            print(f"JSON sidecar: {outcome.report_path.with_suffix('.json')}")
        else:
            print("No report was written; findings remain in the database.")
        return 0 if outcome.result.status == "completed" else 2

    except Exception as exc:
        print(f"Investigation failed: {exc}")
        traceback.print_exc()
        return 1

    finally:
        if owns_spark:
            spark.stop()


if __name__ == "__main__":
    sys.exit(main())
