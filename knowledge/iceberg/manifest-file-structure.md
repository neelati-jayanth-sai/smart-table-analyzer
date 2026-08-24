# Manifest File Structure in Apache Iceberg

## Overview

Manifests are immutable Avro files that list data files or delete files for a snapshot. Understanding manifest structure is essential for diagnosing query planning performance and understanding how Iceberg tracks table files.

## Two-Level Metadata Architecture

Iceberg uses a two-level structure to track files efficiently:

1. **Manifest List:** Points to all manifest files for a snapshot
2. **Manifest Files:** Each lists a subset of data/delete files with statistics

This design enables:
- Parallel manifest scanning during query planning
- Efficient fast appends (add new manifest instead of rewriting)
- Partition-spec evolution (each manifest has its own partition spec)

## Manifest File Properties

### Stored in Avro Metadata
Every manifest file stores these properties in Avro key-value metadata:

- **schema:** JSON table schema at manifest creation time
- **schema-id:** ID of schema used (V2+)
- **partition-spec:** JSON of partition fields array
- **partition-spec-id:** ID of partition spec used (V2+)
- **format-version:** Table format version (V2+)
- **content:** "data" or "deletes" (V2+)

### Content Type Separation
Manifests store EITHER data files OR delete files, never both.

**Reason:** Delete manifests are scanned first during planning, so separating them improves planning performance.

## Manifest Entry Schema

Each entry in a manifest tracks one data/delete file:

### Core Fields
- **status:** added, existing, or deleted (for incremental manifest updates)
- **snapshot_id:** Snapshot that added this file
- **sequence_number:** Sequence number when file was added (V2+)
- **file_sequence_number:** Sequence number of file content (V2+)
- **data_file:** Nested struct with file metadata

### Data File Metadata
Each data_file struct contains:
- **file_path:** Full URI to the file
- **file_format:** Parquet, ORC, Avro
- **partition:** Partition tuple values
- **record_count:** Total rows in file
- **file_size_in_bytes:** Physical file size
- **column_sizes:** Map of column ID to compressed size
- **value_counts:** Map of column ID to non-null value count
- **null_value_counts:** Map of column ID to null count
- **nan_value_counts:** Map of column ID to NaN count (for float/double)
- **lower_bounds:** Map of column ID to min value
- **upper_bounds:** Map of column ID to max value
- **key_metadata:** Encryption key metadata
- **split_offsets:** File split boundaries for parallel reading
- **equality_ids:** Column IDs for equality delete files (V2+)
- **sort_order_id:** ID of sort order used (V2+)

## Manifest Lists

A manifest list is itself an Avro file that lists all manifest files for a snapshot.

### Manifest List Entry Fields
- **manifest_path:** Location of manifest file
- **manifest_length:** Manifest file size in bytes
- **partition_spec_id:** Which partition spec this manifest uses
- **content:** "data" or "deletes"  
- **sequence_number:** Manifest's sequence number (V2+)
- **min_sequence_number:** Minimum sequence number of files in manifest (V2+)
- **added_snapshot_id:** Snapshot that added this manifest
- **added_files_count:** Count of added entries
- **existing_files_count:** Count of existing entries  
- **deleted_files_count:** Count of deleted entries
- **added_rows_count:** Total rows in added files
- **existing_rows_count:** Total rows in existing files
- **deleted_rows_count:** Total rows in deleted files
- **partitions:** List of partition field summaries (min/max values per partition field)

### Partition Statistics in Manifest Lists
Each manifest list entry includes partition-level statistics:
- **contains_null:** Whether null partition values exist
- **contains_nan:** Whether NaN values exist (for numeric partitions)
- **lower_bound:** Minimum partition value in this manifest
- **upper_bound:** Maximum partition value in this manifest

**Purpose:** Enables partition pruning at manifest-list scan time without opening manifest files.

## Query Planning Flow

1. **Read manifest list:** Snapshot points to manifest list file
2. **Filter manifests:** Use partition statistics to skip manifests that can't match query predicate
3. **Read relevant manifests:** Open only manifests that might contain matching data
4. **Filter files:** Within each manifest, use file-level statistics to skip files
5. **Plan tasks:** Assign matched files to execution tasks

## Fast Append Mechanism

When appending data, Iceberg can create a NEW manifest with only new files, then reference both old and new manifests in the new snapshot's manifest list.

**Benefits:**
- Avoids rewriting existing manifest with thousands of entries
- Append commits faster (only write new manifest)
- Metadata writes scale with append size, not table size

**Tradeoff:** More manifests accumulate over time, requiring eventual compaction.

## Manifest Compaction

Over time, fast appends create many small manifests. Manifest compaction merges them.

### When to Compact Manifests
- Manifest count > 20-30 per snapshot
- Many manifests with < 100 entries each
- Query planning time increasing (metadata overhead)

### Compaction Process
1. Read multiple small manifests
2. Merge entries into fewer larger manifests
3. Write new snapshot pointing to compacted manifests
4. Old manifests deleted during snapshot expiry

## Common Patterns

### Pattern: One Manifest Per Append
**Symptom:** Snapshot has hundreds of tiny manifests
**Cause:** Frequent fast appends without compaction
**Impact:** Slow query planning (open/read many files)
**Fix:** Scheduled manifest compaction

### Pattern: Giant Manifest
**Symptom:** Single manifest file > 100 MB
**Cause:** Never splitting manifests despite table growth
**Impact:** Cannot parallelize manifest reading, slow planning
**Fix:** Configure manifest split size (e.g., max 8 MB per manifest)

### Pattern: Mixed Partition Specs  
**Symptom:** Some manifests use spec ID 0, others use spec ID 1
**Cause:** Partition evolution (changed partitioning strategy)
**Impact:** Normal and expected; queries handle this transparently
**Fix:** No action needed (design feature)

## Monitoring Manifest Health

```sql
-- Manifest count per snapshot
SELECT 
    snapshot_id,
    COUNT(*) as manifest_count,
    SUM(added_data_files_count) as total_files
FROM table.metadata.manifest_lists
GROUP BY snapshot_id;

-- Manifest size distribution
SELECT 
    MIN(manifest_length / 1024 / 1024) as min_mb,
    AVG(manifest_length / 1024 / 1024) as avg_mb,
    MAX(manifest_length / 1024 / 1024) as max_mb
FROM table.metadata.manifest_lists
WHERE snapshot_id = <current_snapshot_id>;
```

---

## Provenance

**Based on:**
- `format/spec.md` (Apache Iceberg) - Specification > Manifests (lines 657-680)
- `format/spec.md` - Specification > Manifest Lists
- Iceberg repository commit: `c62a8fc3ee808e95d5493e4ffd19642ac22ea82f`

**Source extracts:**
- `knowledge/iceberg/tree/format/spec-md/iceberg-table-spec/specification/manifests/README.md`
- `knowledge/iceberg/tree/format/spec-md/iceberg-table-spec/specification/manifest-lists/README.md`
- `knowledge/iceberg/tree/format/spec-md/iceberg-table-spec/specification/manifests/manifest--c7753e07/data-file-fields/README.md`
