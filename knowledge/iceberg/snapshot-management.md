# Snapshot Management in Apache Iceberg

## Overview

Snapshots are the foundation of Iceberg's ACID guarantees and time travel capabilities. Each snapshot represents the complete state of a table at a specific point in time. Understanding snapshot lifecycle, retention, and management is critical for both query performance and storage cost control.

## Snapshot Structure

Every snapshot contains:
- **snapshot-id:** Unique long identifier
- **parent-snapshot-id:** Links to previous snapshot (omitted for initial snapshot)
- **sequence-number:** Monotonically increasing order tracker (V2+)
- **timestamp-ms:** Creation timestamp for GC and inspection
- **manifest-list:** Location of manifest list tracking all manifests for this snapshot
- **summary:** Operation type and change statistics
- **schema-id:** Schema version active when snapshot created
- **first-row-id, added-rows:** Row lineage metadata (V3+)

## Snapshot Operations

### Append
- **Behavior:** Only adds data files, no removals
- **Use case:** Streaming ingestion, batch appends
- **Fast append:** Adds new manifest instead of rewriting existing one
- **Retention:** Typically expire quickly unless needed for audit

### Replace
- **Behavior:** Adds and removes files WITHOUT changing table data
- **Use case:** Compaction, format conversion, file relocation
- **Retention:** Can be expired immediately after next snapshot (optimization-only)

### Overwrite
- **Behavior:** Logically replaces data (adds and removes files)
- **Use case:** Partition overwrites, INSERT OVERWRITE operations
- **Retention:** Keep longer for rollback capability

### Delete
- **Behavior:** Removes data files or adds delete files
- **Use case:** DELETE statements, row-level deletes
- **Retention:** Keep for audit trail and compliance

## Time Travel

Time travel queries access historical table states using snapshots:

### By Snapshot ID

```sql
SELECT * FROM table VERSION AS OF 1234567890;
```

### By Timestamp

```sql
SELECT * FROM table TIMESTAMP AS OF '2024-01-15 10:30:00';
```

**Mechanism:** Iceberg finds the most recent snapshot with `timestamp-ms <= query_timestamp`

**Requirement:** Snapshots must be retained for time travel to work

## Snapshot Retention

### Why Retention Matters
- **Storage cost:** Each snapshot keeps old files alive via manifest references
- **Metadata overhead:** More snapshots = longer metadata parsing
- **Time travel depth:** Retention determines how far back you can query

### Default Retention Policies
Most implementations default to:
- **Minimum snapshots:** 1-2 (always keep current and previous)
- **Retention time:** 5-7 days
- **Max snapshots:** Unlimited (controlled by time-based expiry)

### Configuring Retention

```properties
# Minimum snapshots to keep (regardless of age)
history.expire.min-snapshots-to-keep=5

# Maximum snapshot age in milliseconds
history.expire.max-snapshot-age-ms=432000000  # 5 days

# Maximum timestamp for time travel queries
history.expire.max-timestamp-ms=<timestamp>
```

## Snapshot Expiry

Snapshot expiry removes old snapshots and unreferenced data files to reclaim storage.

### What Gets Deleted
1. **Snapshot metadata:** Removed from table metadata snapshot list
2. **Manifest files:** Deleted if not referenced by any remaining snapshot
3. **Data files:** Deleted if not referenced by any remaining manifest

### What's Protected
- Snapshots within retention window
- Current snapshot (always protected)
- Files referenced by any retained snapshot
- Files referenced by multiple snapshots (reference counted)

### Expiry Procedure

```sql
-- Spark example
CALL catalog.system.expire_snapshots(
    table => 'db.table',
    older_than => TIMESTAMP '2024-01-01 00:00:00',
    retain_last => 5
);
```

### Safety Mechanisms
- **Dry run mode:** Preview what would be deleted without deleting
- **Minimum retention:** Won't delete if it would drop below min snapshot count
- **Active queries:** Some implementations protect snapshots being actively read

## Branching (V3+)

Format V3 introduces snapshot branching for multi-version table support:

### Branch Use Cases
- **Staging:** Develop changes on a branch before merging to main
- **Experimentation:** Test schema changes or data transformations
- **Multi-tenant:** Different teams work on isolated branches

### Branch Lifecycle
- Branches have independent retention policies
- Merging a branch incorporates its snapshots into target branch
- Deleting a branch expires its snapshots per branch retention policy

## Common Pitfalls

### Pitfall: Expiring Too Aggressively
- **Problem:** Deleting snapshots needed for active queries or rollback
- **Symptom:** "Snapshot not found" errors, broken time travel queries
- **Fix:** Increase retention window, monitor query patterns for time travel usage

### Pitfall: Never Expiring
- **Problem:** Unbounded metadata growth, storage cost explosion
- **Symptom:** Slow query planning, high S3 storage costs
- **Fix:** Implement scheduled expiry (daily or weekly)

### Pitfall: Ignoring Snapshot Operation Type
- **Problem:** Treating all snapshots equally during expiry
- **Symptom:** Deleting compaction snapshots too quickly, keeping useless append snapshots
- **Fix:** Use operation-aware retention (keep DELETE snapshots longer, expire REPLACE sooner)

### Pitfall: Concurrent Expiry and Queries
- **Problem:** Expiring snapshots while queries are reading them
- **Symptom:** Query failures mid-execution
- **Fix:** Coordinate expiry with query schedules, use longer retention for high-traffic tables

## Metadata Overhead

### Snapshot Count Impact
- **< 100 snapshots:** Minimal overhead
- **100-1,000 snapshots:** Noticeable metadata parsing time
- **> 1,000 snapshots:** Significant planning overhead, consider aggressive expiry

### Monitoring

```sql
-- Count snapshots
SELECT COUNT(*) FROM table.metadata.snapshots;

-- Snapshot age distribution
SELECT 
    DATE_TRUNC('day', TIMESTAMP 'epoch' + committed_at * INTERVAL '1 millisecond') as snapshot_day,
    COUNT(*) as snapshot_count,
    SUM(total_data_files) as total_files
FROM table.metadata.snapshots
GROUP BY snapshot_day
ORDER BY snapshot_day DESC;
```

## Best Practices

### Development/Staging Tables
- **Retention:** 1-2 days
- **Min snapshots:** 2-3
- **Expiry frequency:** Daily
- **Rationale:** Lower storage cost, limited rollback needs

### Production Tables
- **Retention:** 7-30 days  
- **Min snapshots:** 5-10
- **Expiry frequency:** Daily or weekly
- **Rationale:** Audit trail, time travel for analysis, rollback capability

### Compliance/Audit Tables
- **Retention:** 90-365+ days
- **Min snapshots:** 10+
- **Expiry frequency:** Monthly
- **Rationale:** Regulatory requirements, long-term rollback

### High-Frequency Streaming Tables
- **Retention:** 1-3 days
- **Min snapshots:** 10-20 (to cover recent fine-grained commits)
- **Expiry frequency:** Daily
- **Rationale:** Many snapshots created, but short-lived value

---

## Provenance

**Based on:**
- `format/spec.md` (Apache Iceberg) - Specification > Snapshots (lines 948-984)
- Iceberg repository commit: `c62a8fc3ee808e95d5493e4ffd19642ac22ea82f`

**Source extracts:**
- `knowledge/iceberg/tree/format/spec-md/iceberg-table-spec/specification/snapshots/README.md`
- `knowledge/iceberg/tree/docs/docs/spark-queries-md/spark-queries/inspecting-tables/snapshots/README.md`
- General snapshot management best practices from Iceberg documentation
