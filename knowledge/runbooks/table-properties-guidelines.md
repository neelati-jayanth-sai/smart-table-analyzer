# Table Properties Guidelines

## Overview

This runbook defines team standards for Iceberg table properties on the IOMETE platform beyond file sizing. Following these conventions ensures optimal ingestion (write) and consumption (read) performance while preventing metadata bloat and concurrency issues.

## Distribution Mode & Sorting

Iceberg’s distribution mode dictates how data is shuffled across Spark executors before writing.

### 1. Partitioned + Sorted Tables
**Rule:** Use `range` distribution for write and `hash` or `none` for merge.

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.distribution-mode' = 'range',
    'write.merge.distribution-mode' = 'hash' -- Using range for merge increases ingestion time
);
```

**Rationale:** Range distribution guarantees that data is globally sorted across files, which maximizes min/max filtering and avoids overlapping file boundaries.

### 2. Partitioned + Unsorted Tables
**Rule:** Use `hash` distribution.

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.distribution-mode' = 'hash'
);
```

**Rationale:** Hash ensures that all records for a specific partition are routed to a single task, preventing the "small files" problem (one task writing to many partitions).

## Compression & Vectorization

### Compression
**Rule:** Always use `zstd` (which is the default).

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.parquet.compression-codec' = 'zstd',
    'write.parquet.compression-level' = '5' -- Can be increased to 7 or 8 for large tables
);
```

### Read Vectorization
**Rule:** Set vectorization batch size to 20,000 for large tables, or 10,000 for standard tables.

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'read.parquet.vectorization.batch-size' = '20000'
);
```

**Rationale:** Iceberg reads Parquet in vectorized batches. Increasing this from defaults improves read throughput on dense analytic queries.

## Concurrency & Isolation

To avoid conflicts during concurrent ingestion, isolation levels should be set to `snapshot`.

**Rule:** Ensure write isolation levels are set to `snapshot`.

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.delete.isolation-level' = 'snapshot',
    'write.merge.isolation-level' = 'snapshot',
    'write.update.isolation-level' = 'snapshot'
);
```

## Metadata & Snapshot Retention

**Rule:** Control snapshot history to prevent metadata bloat, ensuring `min-snapshots-to-keep` is less than `previous-versions-max`.

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.metadata.previous-versions-max' = '10',
    'history.expire.min-snapshots-to-keep' = '5',
    'write.metadata.delete-after-commit.enabled' = 'true'
);
```

## Column Metrics

Iceberg collects min/max statistics for every column by default. On wide tables (> 100 columns), this bloats the manifest files and slows down planning.

**Rule:** Truncate metrics for wide tables unless full metrics are specifically needed.

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.metadata.metrics.default' = 'truncate(16)'
);
```

**Exception:** For specific heavily queried driver columns, you can override the default:

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.metadata.metrics.column.visit_id' = 'full'
);
```

## Merge-On-Read (MOR) vs. Copy-On-Write (COW)

**Rule:** Do NOT use Merge-On-Read (MOR) if your incremental load contains more than 90% new records, or if the load touches only a few partitions.

If you use MOR, you must schedule frequent compaction jobs to collapse the delete files.

**MOR Configuration:**

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.delete.mode' = 'merge-on-read',
    'write.merge.mode' = 'merge-on-read',
    'write.update.mode' = 'merge-on-read'
);
```

---

## Default Values & Configuration Pedantry
**CRITICAL RULE:** Do NOT pedantically recommend setting properties to their open-source default values unless there is a specific reason to override them.
- Iceberg's default `write.parquet.compression-codec` is `zstd`. If the table is using defaults, explicitly state that defaults are fine.
- Do NOT flag the absence of a property as a "missing critical configuration" if the system default is perfectly adequate.

## Provenance

**Based on:**
- Internal EDS Iceberg Recommendations Summary
- Performance optimizations for IOMETE Spark ingestion and consumption
