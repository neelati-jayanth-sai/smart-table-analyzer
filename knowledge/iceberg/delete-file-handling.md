# Delete File Handling in Apache Iceberg

## Overview

Iceberg V2+ supports row-level deletes without rewriting entire data files by using **delete files**. Understanding delete file accumulation, types, and merge behavior is critical for diagnosing query performance issues and planning maintenance.

## Delete File Types

### Position Deletes (content = 1)
**Purpose:** Mark specific row positions in data files as deleted

**Structure:**
- `file_path`: Path to data file containing deleted rows
- `pos`: Row position within that file (long)
- Additional columns: Optional (e.g., row values for debugging)

**Example Use Case:**

```sql
DELETE FROM table WHERE user_id = 12345;
```

If only a few rows per file match, Iceberg writes position delete files instead of rewriting entire data files.

**Storage:**
- Sorted by (file_path, pos) for efficient lookups
- Multiple position deletes for same data file can exist across different delete files


---

### Equality Deletes (content = 2)
**Purpose:** Mark rows matching specific column values as deleted

**Structure:**
- Contains actual row values for equality columns
- `equality_ids`: List of field IDs used for equality matching
- Only rows with matching values on ALL equality columns are considered deleted

**Example Use Case:**

```sql
DELETE FROM table WHERE order_id = 999 AND order_date = '2024-01-15';
```

**Storage:**
- Can contain subset of table columns (only equality columns required)
- Applied at read time by comparing data file row values to delete file values


---

## Delete File Application During Reads

### Sequence Number Ordering
Delete files are applied based on **sequence numbers**:
- `data_sequence_number`: When the data file content was written
- `file_sequence_number`: When the file was added to table

**Rule:** A delete file applies to a data file if:

```text
delete_file.data_sequence_number >= data_file.data_sequence_number
```

This prevents deletes from incorrectly applying to data written AFTER the delete.


### Scan Flow
1. **Manifest list scan:** Identify delete manifests (content = "deletes")
2. **Delete manifest scan:** Read all delete files BEFORE scanning data manifests
3. **Data manifest scan:** Read data manifests, filter files based on delete file coverage
4. **Row-level filtering:** Apply position/equality deletes during data file reads

**Critical:** Delete manifests are scanned **first** to enable early pruning.


---

## Performance Implications

### Delete File Proliferation Problem
**Symptom:** Query planning time increases despite selective partition filters

**Cause:** Accumulation of many small delete files forces scan of all delete manifests

**Detection:**

```sql
-- Count delete files vs data files
SELECT 
    COUNT(*) FILTER (WHERE content = 0) as data_files,
    COUNT(*) FILTER (WHERE content = 1) as position_delete_files,
    COUNT(*) FILTER (WHERE content = 2) as equality_delete_files
FROM table.entries;
```

**Threshold:** > 10 delete files per partition suggests compaction needed

---

### Delete File Size Impact
**Small delete files (< 10 MB):**
- High metadata overhead (one manifest entry per file)
- Many small reads during query execution
- Increases planning time

**Large delete files (> 100 MB):**
- Cannot prune deleted data files early
- Must scan entire delete file even if only one data file affected

**Optimal:** 32-64 MB delete files, grouped by affected data files

---

### Equality Delete Cost
Equality deletes have **higher read-time cost** than position deletes:
- Must scan equality delete file values
- Compare against every row in data file
- Cannot skip rows based on position alone

**Mitigation:** Use position deletes when possible (if data file locations known)

---

## Metadata Table Queries

### Detect Delete File Accumulation

```sql
SELECT 
    partition,
    COUNT(*) FILTER (WHERE content = 1) as position_deletes,
    COUNT(*) FILTER (WHERE content = 2) as equality_deletes,
    SUM(record_count) FILTER (WHERE content = 1) as total_position_delete_count,
    SUM(file_size_in_bytes) FILTER (WHERE content > 0) / 1024 / 1024 as delete_mb
FROM table.entries
GROUP BY partition
HAVING COUNT(*) FILTER (WHERE content > 0) > 5
ORDER BY delete_mb DESC;
```

### Find Data Files with High Delete Ratio

```sql
WITH data_files AS (
    SELECT file_path, record_count
    FROM table.files
    WHERE content = 0  -- data files only
),
delete_counts AS (
    SELECT referenced_data_file, SUM(record_count) as delete_count
    FROM table.files
    WHERE content = 1  -- position deletes
    GROUP BY referenced_data_file
)
SELECT 
    d.file_path,
    d.record_count as data_rows,
    COALESCE(dc.delete_count, 0) as deleted_rows,
    COALESCE(dc.delete_count, 0) * 100.0 / d.record_count as delete_ratio
FROM data_files d
LEFT JOIN delete_counts dc ON d.file_path = dc.referenced_data_file
WHERE COALESCE(dc.delete_count, 0) * 100.0 / d.record_count > 20
ORDER BY delete_ratio DESC;
```

**Action:** Files with > 30% delete ratio are candidates for rewrite (compaction)

---

### Identify Orphaned Equality Deletes

```sql
-- Equality deletes not merged into data files
SELECT 
    snapshot_id,
    file_path,
    record_count,
    equality_ids
FROM table.entries
WHERE content = 2
  AND status != 2  -- not marked deleted
ORDER BY snapshot_id;
```

If equality deletes exist from old snapshots, consider compaction to merge them.

---

## Delete File Compaction Strategies

### Position Delete Compaction
**Goal:** Merge many small position delete files into fewer larger files

**Trigger:** > 10 position delete files in partition

**Spark Procedure:**

```sql
CALL catalog.system.rewrite_position_delete_files(
    table => 'db.table',
    options => map('target-file-size-bytes', '67108864')  -- 64 MB
);
```

**Effect:** Reduces manifest entry count, faster planning

---

### Merge Deletes into Data Files
**Goal:** Rewrite data files with deletes applied, remove delete files

**Trigger:** Data file delete ratio > 30%

**Spark Procedure:**

```sql
CALL catalog.system.rewrite_data_files(
    table => 'db.table',
    options => map('delete-file-threshold', '5')
);
```

**Effect:**
- Physically removes deleted rows
- Deletes delete files
- Improves scan performance (no delete application at read time)

---

## Common Pitfalls

### Pitfall: Ignoring Delete File Count
**Problem:** Focusing only on data file count, ignoring delete file proliferation  
**Symptom:** Query planning slow despite reasonable data file count  
**Fix:** Monitor delete file count separately, compact when count > 10 per partition

### Pitfall: Never Compacting Position Deletes
**Problem:** Small position delete files accumulate over time from streaming deletes  
**Symptom:** Metadata overhead increases, planning time grows  
**Fix:** Schedule position delete compaction weekly or when count exceeds threshold

### Pitfall: Mixing Delete Types
**Problem:** Using both position and equality deletes on same table  
**Symptom:** Complex delete application logic, hard to debug performance  
**Fix:** Prefer position deletes when possible; use equality deletes only for delete-by-key patterns

### Pitfall: Large Equality Delete Files
**Problem:** Writing one giant equality delete file covering entire table  
**Symptom:** Every query must scan entire delete file  
**Fix:** Partition equality deletes by data file or partition boundary

---

## Investigation Checklist

When investigating slow queries or high planning time:

1. **Check delete file count:**

   ```sql
   SELECT COUNT(*) FROM table.entries WHERE content > 0;
   ```

2. **Check delete ratio per partition:**

   ```sql
   SELECT partition, 
          SUM(record_count) FILTER (WHERE content = 1) / NULLIF(SUM(record_count) FILTER (WHERE content = 0), 0) as delete_ratio
   FROM table.entries
   GROUP BY partition;
   ```

3. **Check delete file sizes:**

   ```sql
   SELECT AVG(file_size_in_bytes) / 1024 / 1024 as avg_delete_mb
   FROM table.files
   WHERE content > 0;
   ```

4. **Check sequence number distribution:**

   ```sql
   SELECT 
       MIN(sequence_number) as min_seq,
       MAX(sequence_number) as max_seq,
       MAX(sequence_number) - MIN(sequence_number) as seq_range
   FROM table.entries
   WHERE content > 0;
   ```

If delete file count > 10 per partition OR delete ratio > 20%, **compaction is needed**.

---

## Format Version Requirements

- **V1:** No delete file support
- **V2:** Position deletes and equality deletes supported
- **V3:** Same as V2, no additional delete features

**Upgrade:** V1 tables must upgrade to V2 to use row-level deletes

---

## Provenance

**Based on:**

**Why This Entry Was Missing:**
The original knowledge base had NO coverage of delete files, despite this being a critical V2+ feature that directly impacts:
- Query planning performance
- Read-time performance  
- Maintenance strategy

**Investigation Impact:**
Without this knowledge, investigators cannot:
- Diagnose why queries are slow despite small data file count
- Understand when compaction is needed
- Detect delete file proliferation early
