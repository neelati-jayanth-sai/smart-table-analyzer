# Iceberg Table Properties Reference

## Overview

Table properties control Iceberg behavior for writes, reads, compaction, and maintenance. Understanding these properties is critical for diagnosing configuration issues and optimizing table performance.

## Property Categories

### Write Properties

#### write.target-file-size-bytes
**Default:** 536870912 (512 MB)  
**Purpose:** Target size for data files written by writers  
**Impact:** Smaller = more files, more metadata overhead. Larger = less parallelism, worse pruning.

**Investigation Use:**

```sql
SELECT key, value 
FROM table.properties 
WHERE key = 'write.target-file-size-bytes';
```

**Source:** Iceberg write configuration

---

#### write.metadata.delete-after-commit.enabled
**Default:** false  
**Purpose:** Automatically delete old metadata files after each commit  
**Impact:** Keeps metadata file count bounded, prevents orphaned metadata accumulation

**Interaction:** Works with `write.metadata.previous-versions-max`


---

#### write.metadata.previous-versions-max
**Default:** 100  
**Purpose:** Number of previous metadata versions to track in metadata log  
**Impact:** Higher = more metadata files retained, better rollback capability

**Investigation Use:** Check if metadata file count exceeds this threshold:

```sql
-- Metadata files accumulate when this property is high
```


---

#### write.parquet.row-group-size-bytes
**Default:** 134217728 (128 MB)  
**Purpose:** Target row group size for Parquet files  
**Impact:** Affects Parquet file internal structure, compression efficiency

**Best Practice:** Set to ~50% of `write.target-file-size-bytes`

---

#### write.distribution-mode
**Default:** none  
**Values:** `none`, `hash`, `range`  
**Purpose:** Control how data is distributed across writers

- `none`: No distribution, writers produce files independently
- `hash`: Hash-distribute by partition key
- `range`: Range-distribute by sort order

**Investigation Use:** Check if write skew is caused by distribution mode

```sql
SELECT key, value FROM table.properties WHERE key = 'write.distribution-mode';
```

---

### Read Properties

#### read.split.target-size
**Default:** 134217728 (128 MB)  
**Purpose:** Target size for read tasks (splits)  
**Impact:** Controls query parallelism. Smaller = more tasks, more overhead. Larger = fewer tasks, less parallelism.

**Investigation Use:** If queries have low parallelism despite large data, check this property

---

#### read.split.planning-lookback
**Default:** 10  
**Purpose:** Number of bins to consider when planning splits  
**Impact:** Affects how splits are combined during planning

---

#### read.parquet.vectorization.enabled
**Default:** true  
**Purpose:** Enable vectorized Parquet reads  
**Impact:** Significantly improves read performance for columnar queries

**Investigation Use:** If queries are slow, verify vectorization is enabled

---

### Snapshot Management Properties

#### history.expire.max-snapshot-age-ms
**Default:** 432000000 (5 days)  
**Purpose:** Maximum age for snapshots before eligible for expiration  
**Impact:** Controls snapshot retention window, affects storage cost and time travel depth

**Investigation Use:**

```sql
SELECT 
    CAST(value AS BIGINT) / 1000 / 60 / 60 / 24 as retention_days
FROM table.properties 
WHERE key = 'history.expire.max-snapshot-age-ms';
```


---

#### history.expire.min-snapshots-to-keep
**Default:** 1  
**Purpose:** Minimum number of snapshots to retain regardless of age  
**Impact:** Ensures recent snapshots always kept even if older than max age

**Investigation Use:** Check if snapshots expired unexpectedly

```sql
SELECT value FROM table.properties WHERE key = 'history.expire.min-snapshots-to-keep';
```


---

### Compaction/Maintenance Properties

#### commit.retry.num-retries
**Default:** 4  
**Purpose:** Number of times to retry commits on conflict  
**Impact:** Higher = more tolerance for concurrent writes, but longer commit time on conflicts

**Investigation Use:** If compaction jobs fail with commit conflicts, check this value

---

#### commit.retry.min-wait-ms
**Default:** 100  
**Purpose:** Minimum wait time between commit retries  
**Impact:** Affects how quickly retries happen after conflicts

---

### Format Properties

#### format-version
**Values:** 1, 2, 3  
**Purpose:** Iceberg table format version  
**Impact:** Determines available features (V2 = row-level deletes, V3 = new data types)

**Investigation Use:** Check format version to understand available features

```sql
SELECT value FROM table.properties WHERE key = 'format-version';
```

**Critical:** Cannot downgrade format version once upgraded

---

#### write.delete.mode
**Default:** copy-on-write  
**Values:** `copy-on-write`, `merge-on-read`  
**Purpose:** How to handle deletes

- `copy-on-write`: Rewrite data files immediately, remove deleted rows
- `merge-on-read`: Write delete files, merge at read time

**Investigation Use:** Check if delete strategy is causing performance issues

```sql
SELECT value FROM table.properties WHERE key = 'write.delete.mode';
```

**Trade-off:**
- CoW: Fast reads, slow deletes
- MoR: Fast deletes, slower reads (delete file application cost)

---

#### write.update.mode
**Default:** copy-on-write  
**Values:** `copy-on-write`, `merge-on-read`  
**Purpose:** How to handle updates

Same trade-off as `write.delete.mode`

---

### Partitioning Properties

#### write.metadata.metrics.default
**Default:** truncate(16)  
**Purpose:** How to truncate metrics (min/max bounds) for string columns  
**Impact:** Affects metadata file size and pruning effectiveness

**Values:**
- `none`: No metrics
- `counts`: Only value counts
- `truncate(N)`: Truncate strings to N characters
- `full`: Full min/max values

---

## Investigation Scenarios

### Scenario: Small File Problem
**Check:**

```sql
SELECT 
    key, 
    value,
    CASE 
        WHEN key = 'write.target-file-size-bytes' THEN CAST(value AS BIGINT) / 1024 / 1024 || ' MB'
        ELSE value
    END as interpreted_value
FROM table.properties
WHERE key IN (
    'write.target-file-size-bytes',
    'write.parquet.row-group-size-bytes'
);
```

**Look for:**
- Target file size < 128 MB (may produce too many small files)
- No target file size set (using default)

---

### Scenario: Query Planning Slow
**Check:**

```sql
SELECT key, value FROM table.properties
WHERE key IN (
    'read.split.target-size',
    'read.split.planning-lookback',
    'write.metadata.previous-versions-max'
);
```

**Look for:**
- Very small split target size (< 64 MB) = too many tasks
- High previous-versions-max (> 100) = many metadata files

---

### Scenario: Snapshot Accumulation
**Check:**

```sql
SELECT 
    key,
    CASE
        WHEN key LIKE '%max-snapshot-age-ms' THEN 
            CAST(value AS BIGINT) / 1000 / 60 / 60 / 24 || ' days'
        ELSE value
    END as interpreted_value
FROM table.properties
WHERE key IN (
    'history.expire.max-snapshot-age-ms',
    'history.expire.min-snapshots-to-keep',
    'write.metadata.delete-after-commit.enabled'
);
```

**Look for:**
- Very high max-snapshot-age (> 30 days) without expiry job
- High min-snapshots-to-keep (> 20) preventing expiry
- Metadata delete-after-commit disabled (accumulating metadata files)

---

### Scenario: Commit Conflicts
**Check:**

```sql
SELECT key, value FROM table.properties
WHERE key IN (
    'commit.retry.num-retries',
    'commit.retry.min-wait-ms',
    'write.distribution-mode'
);
```

**Look for:**
- Low retry count (< 4) = less tolerance for concurrent writes
- Hash distribution on skewed key = write conflicts

---

## Setting Properties

### At Table Creation

```sql
CREATE TABLE db.table (...)
TBLPROPERTIES (
    'write.target-file-size-bytes' = '268435456',  -- 256 MB
    'history.expire.max-snapshot-age-ms' = '604800000',  -- 7 days
    'write.delete.mode' = 'merge-on-read'
);
```

### After Table Creation

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'write.target-file-size-bytes' = '268435456'
);
```

### Check Current Properties

```sql
SELECT * FROM db.table.properties;
```

---

## Property Interactions

### File Sizing Consistency
**Properties:**
- `write.target-file-size-bytes`
- `write.parquet.row-group-size-bytes`

**Rule:** Row group size should be ~50% of target file size  
**Why:** Ensures multiple row groups per file for better parallelism

**Example:**

```text
write.target-file-size-bytes = 536870912  (512 MB)
write.parquet.row-group-size-bytes = 268435456  (256 MB)
Result: ~2 row groups per file
```

---

### Snapshot Retention Coordination
**Properties:**
- `history.expire.max-snapshot-age-ms`
- `history.expire.min-snapshots-to-keep`
- `write.metadata.delete-after-commit.enabled`

**Rule:** A snapshot is retained if EITHER condition is true:
- Snapshot age < max-snapshot-age-ms
- Snapshot is in most recent N (min-snapshots-to-keep)

**Effect:** Retention is the MAXIMUM of both policies, not minimum

---

### Delete Strategy Alignment
**Properties:**
- `write.delete.mode`
- `write.update.mode`

**Best Practice:** Use same mode for both (CoW or MoR consistently)  
**Why:** Mixing modes creates complex maintenance requirements

---

## Common Misconfigurations

### Misconfiguration: Tiny Target File Size
**Property:** `write.target-file-size-bytes = 10485760` (10 MB)  
**Symptom:** Thousands of tiny files, slow query planning  
**Fix:** Increase to 256-512 MB

### Misconfiguration: Huge Row Group Size
**Property:** `write.parquet.row-group-size-bytes = 1073741824` (1 GB)  
**Symptom:** Poor read parallelism, high memory usage  
**Fix:** Set to ~50% of target file size

### Misconfiguration: Infinite Snapshot Retention
**Property:** `history.expire.max-snapshot-age-ms = 31536000000000` (1000 years)  
**Symptom:** Unbounded metadata growth, high storage cost  
**Fix:** Set realistic retention (7-30 days for most tables)

### Misconfiguration: Zero Commit Retries
**Property:** `commit.retry.num-retries = 0`  
**Symptom:** Compaction jobs fail frequently with commit conflicts  
**Fix:** Set to 4-10 retries

---

## Provenance

**Based on:**

**Why This Entry Was Missing:**
Original knowledge base had NO comprehensive property reference, making it impossible for investigators to:
- Check if table is misconfigured
- Understand why certain behaviors occur
- Know what properties to adjust

**Investigation Impact:**
Without this knowledge, investigators cannot diagnose root causes of:
- Small file proliferation (target file size too small)
- Snapshot accumulation (retention properties not set)
- Commit conflicts (retry properties too low)
- Slow queries (split size or vectorization issues)

---

## Quick Reference Table

| Problem Symptom | Check These Properties |
|----------------|------------------------|
| Too many small files | `write.target-file-size-bytes` |
| Query planning slow | `write.metadata.previous-versions-max`, `read.split.target-size` |
| Snapshots accumulating | `history.expire.max-snapshot-age-ms`, `history.expire.min-snapshots-to-keep` |
| Commit conflicts | `commit.retry.num-retries`, `write.distribution-mode` |
| Slow reads | `read.parquet.vectorization.enabled`, `read.split.target-size` |
| Delete performance | `write.delete.mode`, `write.update.mode` |
| Metadata file accumulation | `write.metadata.delete-after-commit.enabled`, `write.metadata.previous-versions-max` |
