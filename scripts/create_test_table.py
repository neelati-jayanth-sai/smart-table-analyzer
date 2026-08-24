"""Create a small Iceberg test table in IOMETE for end-to-end checks.

Connection details come from the environment (see ENV_QUICK_START.md); nothing
is hardcoded here.
"""

from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
from pyspark.sql import SparkSession

load_dotenv(repo_root / ".env")

from scripts import _investigation_cli as cli

TABLE = "eds_it_dev.elh_comn.smart_table_test1"


def main() -> int:
    if not cli.setup_ssl(repo_root):
        print("Certificate not found; set IOMETE_CERT_FILE")
        return 1

    print("Connecting to IOMETE via Spark Connect...")
    spark = SparkSession.builder.remote(cli.build_spark_url()).getOrCreate()

    try:
        print(f"Creating {TABLE}")
        spark.sql(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id INT,
                name STRING,
                value DOUBLE,
                category STRING,
                created_at TIMESTAMP
            ) USING iceberg
            PARTITIONED BY (days(created_at))
            TBLPROPERTIES ('write.target-file-size-bytes'='134217728')
        """)

        print("Inserting sample rows...")
        spark.sql(f"""
            INSERT INTO {TABLE} VALUES
            (1, 'test1', 100.5, 'A', CAST('2024-01-01 10:00:00' AS TIMESTAMP)),
            (2, 'test2', 200.3, 'B', CAST('2024-01-02 11:00:00' AS TIMESTAMP)),
            (3, 'test3', 150.7, 'A', CAST('2024-01-03 12:00:00' AS TIMESTAMP)),
            (4, 'test4', 300.2, 'C', CAST('2024-01-04 13:00:00' AS TIMESTAMP)),
            (5, 'test5', 250.9, 'B', CAST('2024-01-05 14:00:00' AS TIMESTAMP))
        """)

        spark.sql(f"DESCRIBE EXTENDED {TABLE}").show(truncate=False)
        spark.sql(f"SELECT * FROM {TABLE} LIMIT 5").show()
        print(f"\n{TABLE} is ready for analysis")
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
