"""Discover tables in IOMETE catalog and classify them by profile."""
import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
load_dotenv(repo_root / ".env")

from scripts import _investigation_cli as cli
from pyspark.sql import SparkSession


def discover_tables(spark, catalog: str, schema: str, limit: int = 100):
    """Query the IOMETE catalog to list tables with basic metrics."""
    # Try Spark's built-in catalog first
    try:
        df = spark.sql(f"SHOW TABLES IN {catalog}.{schema}")
        tables = [row["tableName"] for row in df.collect()]
        print(f"Found {len(tables)} tables via SHOW TABLES")

        # Get metrics for each table using Iceberg metadata
        table_metrics = []
        for table_name in tables[:limit]:
            full_name = f"{catalog}.{schema}.{table_name}"
            try:
                # Get row count and file size from Iceberg metadata
                row_count = spark.sql(f"SELECT COUNT(*) FROM {full_name}").first()[0]
                size_result = spark.sql(
                    f"SELECT COALESCE(SUM(file_size_in_bytes), 0) as total_bytes "
                    f"FROM {full_name}.files WHERE content = 0"
                ).first()
                size_bytes = size_result[0] if size_result else 0

                table_metrics.append({
                    "table_name": table_name,
                    "row_count": row_count,
                    "size_bytes": size_bytes,
                })
            except Exception as e:
                print(f"Error getting metrics for {table_name}: {e}")
                # Still add the table with zero metrics
                table_metrics.append({
                    "table_name": table_name,
                    "row_count": 0,
                    "size_bytes": 0,
                })

        return table_metrics

    except Exception as e:
        print(f"Error querying catalog: {e}")
        return []


def classify_table_profile(row_count: int, size_bytes: int) -> str:
    """Classify a table based on its metrics."""
    if row_count == 0 or row_count < 100:
        return "empty"
    elif size_bytes > 10_000_000_000:  # > 10GB
        return "huge"
    elif size_bytes > 1_000_000_000:  # > 1GB
        return "large"
    elif size_bytes > 100_000_000:  # > 100MB
        return "medium"
    else:
        return "small"


def main():
    cert_path = cli.setup_ssl(repo_root)
    if not cert_path:
        print(f"Certificate not found: {os.getenv('IOMETE_CERT_FILE')}")
        return 1

    catalog = os.getenv("IOMETE_CATALOG")
    schema = os.getenv("IOMETE_NAMESPACE")

    print(f"Discovering tables in {catalog}.{schema}...")
    spark = cli.create_spark_session()

    try:
        tables = discover_tables(spark, catalog, schema, limit=50)
        print(f"\nFound {len(tables)} tables:\n")

        profiles = {
            "empty": [],
            "small": [],
            "medium": [],
            "large": [],
            "huge": [],
        }

        for row in tables:
            table_name = row["table_name"]
            row_count = row["row_count"]
            size_bytes = row["size_bytes"]
            profile = classify_table_profile(row_count, size_bytes)

            profiles[profile].append({
                "table_name": table_name,
                "row_count": row_count,
                "size_bytes": size_bytes,
                "size_mb": size_bytes / (1024 * 1024),
            })

        for profile_type, table_list in profiles.items():
            if table_list:
                print(f"\n=== {profile_type.upper()} tables ({len(table_list)}) ===")
                for t in table_list[:5]:  # Show top 5 per category
                    print(f"  {t['table_name']}: {t['row_count']:,} rows, {t['size_mb']:.2f} MB")

        return 0

    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
