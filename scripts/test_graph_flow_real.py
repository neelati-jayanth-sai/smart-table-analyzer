"""Run an investigation on a real IOMETE table using the Dell AIA Gateway LLM."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv

load_dotenv(repo_root / ".env", override=True)

from pyspark.sql import SparkSession

from scripts import init_investigation_db as init_db
from src.connectors import DellAIAAdapter
from src.database import InvestigationDb
from src.database.knowledge_store import KnowledgeStore
from src.investigator import Investigator
from src.metadata.loader import load_table_metadata
from src.query import QueryWorkbench, create_investigation_hooks


def setup_ssl() -> Path | None:
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
    return (
        f"sc://{os.getenv('IOMETE_HOST')}:443/;"
        f"cluster={os.getenv('IOMETE_LAKEHOUSE')};"
        f"data_plane={os.getenv('IOMETE_DATA_PLANE')};"
        f"use_ssl=true;"
        f"user_id={os.getenv('IOMETE_USER_ID')};"
        f"api_token={os.getenv('IOMETE_API_TOKEN')}"
    )


def pick_table(spark, catalog: str, namespace: str) -> str:
    tables = spark.sql(f"SHOW TABLES IN {catalog}.{namespace}").collect()
    if not tables:
        raise RuntimeError(f"No tables found in {catalog}.{namespace}")
    name = tables[0].tableName
    print(f"Selected table: {catalog}.{namespace}.{name}")
    return name


def build_baseline(spark, catalog: str, namespace: str, table: str) -> dict:
    ref = f"{catalog}.{namespace}.{table}"
    row_count, num_files, total_bytes = 0, 0, 0
    try:
        row_count = int(spark.sql(f"SELECT COUNT(*) FROM {ref}").collect()[0][0])
    except Exception:
        pass
    try:
        row = spark.sql(
            f"SELECT COUNT(*) AS cnt, SUM(file_size_in_bytes) AS total FROM {ref}.files WHERE content = 0"
        ).first()
        if row:
            num_files = int(row["cnt"] or 0)
            total_bytes = int(row["total"] or 0)
    except Exception:
        pass
    avg_file_size = float(total_bytes) / num_files if num_files else 0.0
    file_score = min((avg_file_size / 134_217_728) * 100, 100.0) if avg_file_size else 50.0
    return {
        "overall": file_score,
        "row_count": row_count,
        "num_data_files": num_files,
        "total_data_file_bytes": total_bytes,
        "avg_file_size": avg_file_size,
        "dimensions": {
            "file_size": file_score,
            "scan_efficiency": 50.0,
            "delete_overhead": 50.0,
            "manifest_organization": 50.0,
            "partition_aware": 50.0,
            "sort_order": 50.0,
        },
    }


def initialize_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    InvestigationDb(db_path)
    entries = init_db.scan_knowledge_entries(repo_root)
    if entries:
        init_db.seed_knowledge_index(db_path, entries)


def main() -> int:
    if not setup_ssl():
        print(f"Certificate not found: {os.getenv('IOMETE_CERT_FILE')}")
        return 1

    catalog = os.getenv("IOMETE_CATALOG")
    namespace = os.getenv("IOMETE_NAMESPACE")
    if not catalog or not namespace:
        print("IOMETE_CATALOG and IOMETE_NAMESPACE must be set")
        return 1

    print("Connecting to Spark Connect...")
    spark = SparkSession.builder.appName("investigator-real-graph-test").remote(build_spark_url()).getOrCreate()

    try:
        table = pick_table(spark, catalog, namespace)
        table_name = f"{catalog}.{namespace}.{table}"
        baseline = build_baseline(spark, catalog, namespace, table)

        print(f"Loading metadata for {table_name}...")
        table_metadata = load_table_metadata(spark, table_name)

        db_path = repo_root / "data" / "investigation.db"
        print(f"Initializing database: {db_path}")
        initialize_database(db_path)

        db = InvestigationDb(db_path)
        knowledge = KnowledgeStore(db_path, repo_root=repo_root)
        llm = DellAIAAdapter.from_env()
        workbench = QueryWorkbench(
            spark,
            hooks=create_investigation_hooks([catalog], [namespace]),
            timeout_seconds=int(os.getenv("QUERY_TIMEOUT_SECONDS", "30")),
            table_name=table_name,
        )

        inv_id = db.create_investigation(
            run_id=str(uuid.uuid4()),
            table_name=table_name,
            catalog_name=catalog,
            schema_name=namespace,
            max_checks=3,
        )
        print(f"Created investigation {inv_id}")

        investigator = Investigator(
            llm=llm,
            workbench=workbench,
            knowledge_retrieval=knowledge,
            db=db,
            db_path=db_path,
            max_checks=3,
        )

        result = investigator.run_investigation(
            inv_id, table_name, baseline, table_metadata=table_metadata
        )
        print(f"\nInvestigation status: {result.status}")
        print(f"Checks completed: {result.checks_completed}\n")

        print("Generated queries and execution results:")
        for check in result.checks:
            if check.get("node_name") == "execute_query":
                print(f"  Check {check['check_num']}: {check.get('query')}")
                if check.get("error"):
                    print(f"    ERROR ({check.get('status')}): {check['error']}")
                else:
                    print(f"    STATUS: {check.get('status')}, rows: {check.get('result', {}).get('row_count')}")

        print("\nFinal verdicts:")
        validated = 0
        for finding in result.findings:
            print(f"  Check {finding['check_num']}: {finding['verdict']} - {finding['question']}")
            print(f"    Validated: {finding['validated']}")
            print(f"    Rationale: {finding['rationale']}")
            if finding["validated"] and finding["verdict"] != "could_not_verify":
                validated += 1

        print(f"\nValidated non-could_not_verify findings: {validated}")
        return 0 if validated > 0 else 1

    except Exception as exc:
        import traceback
        print(f"Real graph test failed: {exc}")
        traceback.print_exc()
        return 1

    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
