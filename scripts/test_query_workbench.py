"""Test query hooks and workbench."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from src.query import QueryWorkbench, create_investigation_hooks
from src.query.query_hooks import (
    NoFilePathHook,
    ReadOnlyHook,
    SchemaWhitelistHook,
    SingleStatementHook,
)


def test_read_only_hook() -> int:
    hook = ReadOnlyHook()
    assert hook.validate("SELECT * FROM table").is_valid
    assert not hook.validate("INSERT INTO table VALUES (1)").is_valid
    assert not hook.validate("UPDATE table SET x=1").is_valid
    assert not hook.validate("DELETE FROM table").is_valid
    assert not hook.validate("DROP TABLE table").is_valid
    assert not hook.validate("CREATE TABLE table (x INT)").is_valid
    assert not hook.validate("ALTER TABLE table ADD COLUMN y INT").is_valid
    assert not hook.validate("TRUNCATE TABLE table").is_valid
    assert hook.validate("SHOW DATABASES").is_valid
    assert hook.validate("DESCRIBE table").is_valid
    print("✅ ReadOnlyHook")
    return 0


def test_single_statement_hook() -> int:
    hook = SingleStatementHook()
    assert hook.validate("SELECT 1").is_valid
    assert not hook.validate("SELECT 1; SELECT 2").is_valid
    assert not hook.validate("SELECT 1; DROP TABLE x").is_valid
    print("✅ SingleStatementHook")
    return 0


def test_no_file_path_hook() -> int:
    hook = NoFilePathHook()
    assert hook.validate("SELECT * FROM table").is_valid
    assert not hook.validate("LOAD DATA FROM 'file://data.csv'").is_valid
    assert not hook.validate("COPY INTO table FROM 'file://path'").is_valid
    print("✅ NoFilePathHook")
    return 0


def test_schema_whitelist_hook() -> int:
    hook = SchemaWhitelistHook({"eds_it_dev"}, {"elh_comn"})
    assert hook.validate("SELECT * FROM eds_it_dev.elh_comn.table").is_valid
    assert not hook.validate("SELECT * FROM other_catalog.schema.table").is_valid
    print("✅ SchemaWhitelistHook")
    return 0


def test_full_pipeline() -> int:
    hooks = create_investigation_hooks(["eds_it_dev"], ["elh_comn"])
    wb = type("WB", (), {"hooks": hooks})()

    def validate(query: str) -> bool:
        for h in wb.hooks:
            result = h.validate(query)
            if not result.is_valid:
                print(f"   Blocked by {h.__class__.__name__}: {result.error_message}")
                return False
        return True

    assert validate("SELECT * FROM eds_it_dev.elh_comn.table")
    assert not validate("DROP TABLE eds_it_dev.elh_comn.table")
    assert not validate("SELECT 1; DROP TABLE x")
    assert not validate("LOAD DATA FROM 'file://x'")
    assert not validate("SELECT * FROM other_db.schema.table")
    print("✅ Full hook pipeline")
    return 0


def test_with_real_spark() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    try:
        from pyspark.sql import SparkSession
    except ImportError:
        print("⚠️ PySpark not installed, skipping real Spark test")
        return 0

    cert_path = Path(__file__).resolve().parents[1] / "certs" / "CertificateAuthoritykob.cer"
    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = str(cert_path)
    os.environ["REQUESTS_CA_BUNDLE"] = str(cert_path)
    os.environ["SSL_CERT_FILE"] = str(cert_path)

    host = os.getenv("IOMETE_HOST")
    user_id = os.getenv("IOMETE_USER_ID")
    api_token = os.getenv("IOMETE_API_TOKEN")
    lakehouse = os.getenv("IOMETE_LAKEHOUSE")
    data_plane = os.getenv("IOMETE_DATA_PLANE")
    catalog = os.getenv("IOMETE_CATALOG")
    schema = os.getenv("IOMETE_NAMESPACE")

    if not all([host, user_id, api_token, lakehouse, data_plane, catalog, schema]):
        print("⚠️ IOMETE env vars missing, skipping real Spark test")
        return 0

    spark_url = (
        f"sc://{host}:443/;"
        f"cluster={lakehouse};"
        f"data_plane={data_plane};"
        f"use_ssl=true;"
        f"user_id={user_id};"
        f"api_token={api_token}"
    )

    print("Connecting to IOMETE for workbench test...")
    spark = SparkSession.builder.appName("Workbench-Test").remote(spark_url).getOrCreate()

    hooks = create_investigation_hooks([catalog], [schema])
    wb = QueryWorkbench(spark, hooks=hooks, timeout_seconds=60)

    # Valid query
    result = wb.execute_query(f"SELECT 1 AS test_value, 'Hello' AS message")
    assert result.success, f"Valid query failed: {result.error}"
    assert result.rows == [{"test_value": 1, "message": "Hello"}]
    print(f"✅ Valid query: {result.row_count} rows, {result.execution_time_ms}ms")

    # Invalid query blocked
    bad_result = wb.execute_query("DROP TABLE test")
    assert not bad_result.success
    assert "ReadOnlyHook" in bad_result.error
    print(f"✅ Invalid query blocked: {bad_result.error}")

    # Schema whitelist
    other_result = wb.execute_query("SELECT * FROM other_catalog.other_schema.table")
    assert not other_result.success
    assert "SchemaWhitelistHook" in other_result.error
    print(f"✅ Schema whitelist blocked: {other_result.error}")

    spark.stop()
    return 0


def main() -> int:
    tests = [
        test_read_only_hook,
        test_single_statement_hook,
        test_no_file_path_hook,
        test_schema_whitelist_hook,
        test_full_pipeline,
    ]

    for test in tests:
        if test() != 0:
            return 1

    # Optional real Spark test
    test_with_real_spark()

    print("\n✅ All query workbench tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
