# Target File Size Standards

## Overview

This runbook defines team standards for target file sizes across different table types and use cases. Consistent file sizing improves query performance and reduces maintenance overhead.

## Standard Targets by Table Type

### Production OLAP Tables (Medium/Balanced)

**Target:** 256 MB per file
**Row Group Size:** 128 MB

**Configuration:**

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.target-file-size-bytes' = '268435456',
    'write.parquet.row-group-size-bytes' = '134217728'
);
```

**Rationale:** Balances S3 API cost, query planning overhead, and partition pruning effectiveness

### X-Small Tables (<= 5 GB) & High-Frequency Streaming

**Target:** 128 MB per file
**Row Group Size:** 32 MB (or 24 MB)

**Configuration:**

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.target-file-size-bytes' = '134217728',
    'write.parquet.row-group-size-bytes' = '33554432'
);
```

**Rationale:** Smaller files are acceptable for low-latency streaming and small datasets. Using 32 MB row groups allows 4 row groups per file.

### Large Fact Tables (> 1 TB)

**Target:** 512 MB per file
**Row Group Size:** 128 MB

**Configuration:**

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.target-file-size-bytes' = '536870912',
    'write.parquet.row-group-size-bytes' = '134217728'
);
```

**Rationale:** Larger files reduce metadata overhead on very large tables; pruning still effective

### Development/Staging Tables

**Target:** 128 MB per file

**Configuration:**

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.target-file-size-bytes' = '134217728'
);
```

**Rationale:** Lower cost to rewrite during experimentation; smaller files acceptable for dev workloads

## Compaction Thresholds

### When to Trigger Compaction

| File Size | Action |
|-----------|--------|
| < 32 MB | Compact immediately (critical) |
| 32-64 MB | Compact within 24 hours (high priority) |
| 64-128 MB | Compact within 1 week (medium priority) |
| 128-512 MB | Monitor (acceptable range) |
| > 512 MB | Consider splitting if > 1 GB (low priority) |

### File Count Thresholds by Partition

- **Critical:** > 50 files per partition → compact within 24 hours
- **Warning:** 20-50 files per partition → compact within 1 week
- **Healthy:** < 20 files per partition

## Monitoring Standards

### Weekly Review

Run file health query every Monday:

```sql
SELECT 
    table_name,
    partition,
    COUNT(*) as file_count,
    MIN(file_size_in_bytes) / 1024 / 1024 as min_mb,
    AVG(file_size_in_bytes) / 1024 / 1024 as avg_mb,
    MAX(file_size_in_bytes) / 1024 / 1024 as max_mb,
    CASE 
        WHEN COUNT(*) > 50 OR AVG(file_size_in_bytes) < 67108864 THEN 'CRITICAL'
        WHEN COUNT(*) > 20 OR AVG(file_size_in_bytes) < 134217728 THEN 'WARNING'
        ELSE 'HEALTHY'
    END as status
FROM (
    SELECT 
        '{table_name}' as table_name,
        partition,
        file_size_in_bytes
    FROM db.table.files
)
GROUP BY table_name, partition
HAVING status IN ('CRITICAL', 'WARNING')
ORDER BY status, file_count DESC;
```

### Alerting Thresholds

- **Critical alert:** Any partition with > 100 files or avg file size < 32 MB
- **Warning alert:** Any partition with > 50 files or avg file size < 64 MB

## Configuration Best Practices

### Default Values & Configuration Pedantry

**CRITICAL RULE:** Do NOT pedantically recommend setting properties to their open-source default values unless there is a specific reason to override them.
- Iceberg's default `write.target-file-size-bytes` is 512MB. If the table is using defaults and those defaults are acceptable, explicitly state that defaults are fine.
- Only recommend setting missing properties if they represent a serious misconfiguration.
- Do NOT flag the absence of a property as a "missing critical configuration" if the system default is perfectly adequate.

### Coordinate Target with Compaction

Set compaction min threshold to 50% of target:

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.target-file-size-bytes' = '268435456',  -- 256 MB target
    'iomete.compact.min-file-size-mb' = '128'      -- Compact files < 128 MB
);
```

### Parquet Row Group Alignment

Set row group size to ~50% of target file size:

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.target-file-size-bytes' = '268435456',    -- 256 MB
    'write.parquet.row-group-size-bytes' = '134217728'  -- 128 MB
);
```

**Rationale:** Allows 2 row groups per file; enables within-file parallelism while maintaining target

## Special Cases

### Wide Tables (> 100 columns)

**Target:** 512 MB per file

**Reason:** More columns = larger minimum viable file size for compression effectiveness

### Narrow Tables (< 10 columns)

**Target:** 128 MB per file

**Reason:** Less data per row = can use smaller files while maintaining row count

### Compressed Data (e.g., JSON text)

**Target:** 384 MB per file

**Reason:** Text compresses well; can use larger files without proportional query cost increase

## Override Process

### When to Deviate from Standards

- Table characteristics fundamentally different from standard cases
- Proven query performance benefit from different sizing
- Cost optimization for rarely-queried cold storage tables

### Approval Required For

- Target file size < 64 MB (except streaming tables)
- Target file size > 1 GB
- Disabling compaction on production table

### Documentation Required

```sql
COMMENT ON TABLE db.table IS '...
File size: 128 MB (override from 256 MB standard).
Rationale: Streaming ingestion with 5-minute latency requirement.
Approved by: <name>, Date: 2024-01-15';
```

## Cost Impact

### Storage Cost

- File size doesn't affect storage cost (pay for bytes stored)
- Smaller files = more snapshots retained longer = higher cost
- Compaction rewrites data = temporary 2x storage during operation

### Compute Cost

- Smaller files = more manifest entries = longer planning = higher driver cost
- Smaller files = more S3 API calls = higher API cost
- Larger files = less effective pruning = more data scanned = higher executor cost

**Optimal balance:** 256 MB default target minimizes total cost for typical queries

---

## Provenance

**Based on:**
- Team operational experience with production Iceberg tables
- Cost analysis of various file size configurations
- Performance benchmarks on representative queries

**Source:** Team runbook, maintained by data platform team
