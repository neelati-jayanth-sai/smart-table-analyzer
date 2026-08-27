# Smart Table Analyzer Runtime Contract

This contract is derived from [STA_SPARK_SURFACE.md](STA_SPARK_SURFACE.md).
It is deliberately an analysis seam, not a Spark-shaped interface.

## Interface

`AnalysisRuntime` owns these operations:

| Operation | Caller-visible result | Proven usage |
|---|---|---|
| `describe_table(table)` | canonical schema, partition specs, files, partition statistics, snapshots, history, and properties | deterministic collection |
| `sample_rows(table, limit)` | JSON-compatible bounded sample | metadata evidence |
| `profile_columns(table, columns)` | per-column cardinality, null count, optional min/max | deep profile |
| `latest_snapshot_id(table)` | current snapshot ID or `None` | snapshot pinning |
| `query_patterns(table)` | workload patterns or explicit unavailable result | optional IOMETE signal |
| `execute_readonly(query, limit, full_count)` | rows, schema, count, truncation | validated Investigator evidence query |

Adapters must return canonical Python models or JSON-compatible values. They
must not expose Spark Rows/DataFrames, Arrow Tables, PyIceberg objects, or
DuckDB relations to analyzer, Investigator, scoring, or reporting modules.

## Canonical models

The smallest supported model set is `ColumnMetadata`, `DataFileMetadata`,
`PartitionStats`, `SnapshotMetadata`, `HistoryEntry`, `PartitionSpec`, and
`TableMetadata`. It preserves `field_id`, `spec_id`, `snapshot_id`,
`sequence_number`, and `sort_order_id` when the backing catalog exposes them.
Delete files are represented as files with a non-data content type.

## Adapter obligations

`SparkIometeRuntime` wraps the existing Spark/Iomete semantics and normalizes
results at this seam. `LocalIcebergRuntime` uses PyIceberg for table metadata
and DuckDB only for scans/aggregates. It must fail explicitly when a requested
operation cannot preserve the supported semantics.

`execute_readonly` is an audited escape hatch for the Investigator’s existing
read-only query workbench. Callers still validate SQL, table scope, and snapshot
pinning before invoking it. The local adapter supports only its documented
DuckDB subset; no SQL rewriting or compatibility translation is permitted.
