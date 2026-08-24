# File Sizing Best Practices in Apache Iceberg

## Overview

File sizing significantly impacts query performance, metadata overhead, and table maintenance cost in Apache Iceberg. The table format supports arbitrarily small or large files, but optimal performance requires intentional file size management.

## Target File Sizes

### General Guidelines
- **Recommended range:** 128 MB to 1 GB per data file
- **Sweet spot:** 256 MB to 512 MB for most workloads
- **Minimum viable:** 64 MB (below this, metadata overhead dominates)
- **Maximum practical:** 1 GB (above this, pruning benefits diminish)

### Why File Size Matters

**Too small (< 64 MB):**
- Metadata overhead grows: more manifest entries, longer planning time
- More file handles during reads
- Higher cloud storage API costs (one request per file)
- S3/cloud storage optimized for larger sequential reads

**Too large (> 1 GB):**
- Reduced partition pruning effectiveness
- Cannot skip data within a file (row-level filtering still reads entire file)
- Higher memory pressure during writes
- Longer task execution times

## Compaction Triggers

Compaction consolidates small files into larger ones and should run when:

### File Count Threshold
- **Trigger:** Partition has > 20-50 small files
- **Why:** Metadata overhead becomes visible in query planning
- **Action:** Combine files in same partition to target size

### Size Distribution Skew  
- **Trigger:** Wide file size variance (some 10 MB, some 500 MB)
- **Why:** Uneven task distribution during reads
- **Action:** Rewrite to uniform size distribution

### Post-Stream-Ingestion
- **Trigger:** After streaming writes (typically produce small files)
- **Why:** Streaming optimizes for latency, not file size
- **Action:** Scheduled compaction (e.g., hourly or daily)

### Write Amplification Budget
- **Trigger:** Total file size in partition < 5 GB but file count > 50
- **Why:** Cost/benefit analysis: rewriting 5 GB to improve 50-file manifest is worthwhile
- **Action:** Compact to 10-20 optimally-sized files

## Small File Problems

### Symptom: Planning Time Dominates Query Time
- **Observation:** Query takes 30s to plan, 5s to execute
- **Root cause:** Thousands of small files requiring manifest entry scanning
- **Diagnosis:** Check `SELECT * FROM table.metadata.files` - look for file count and size distribution

### Symptom: Cloud Storage Throttling
- **Observation:** Intermittent S3 503 errors or rate limit errors
- **Root cause:** Each file = one GET request; 10,000 files = 10,000 requests
- **Diagnosis:** Monitor storage API call volume during queries

### Symptom: High Memory Usage During Planning
- **Observation:** Spark driver OOM during query planning
- **Root cause:** Manifest metadata for thousands of files doesn't fit in memory
- **Diagnosis:** Enable manifest caching, or compact files first

## Write-Time Strategies

### Batch Writers
Configure target file size explicitly:

```properties
write.target-file-size-bytes=268435456  # 256 MB
write.parquet.row-group-size-bytes=134217728  # 128 MB
```

### Streaming Writers
Accept small files during ingestion, compact periodically:

```properties
# Accept smaller files for low latency
write.target-file-size-bytes=67108864  # 64 MB

# Compact hourly
compact.schedule=0 * * * *
```

### Mixed Workload
Partition by time, compact older partitions:

```sql
-- Current hour: accept small files
-- Previous hours: compact to 256 MB target
```

## Compaction Strategies

### Full Partition Compaction
- **When:** Partition has settled (no more writes expected)
- **Cost:** Rewrites all data in partition
- **Benefit:** Optimal file layout, uniform file sizes
- **Frequency:** Daily or weekly for active partitions

### Incremental Compaction  
- **When:** Continuous writes to partition
- **Cost:** Only rewrites small files, leaves large files alone
- **Benefit:** Lower write amplification
- **Frequency:** Hourly or as file count threshold reached

### Bin-Packing Compaction
- **When:** Files have mixed sizes
- **Cost:** Reads multiple small files, writes few large files
- **Benefit:** Achieves uniform target size with minimal rewrites
- **Frequency:** On-demand or scheduled

## Monitoring File Health

### Key Metrics

```sql
-- File count per partition
SELECT partition, COUNT(*) as file_count
FROM table.metadata.files
GROUP BY partition
ORDER BY file_count DESC;

-- File size distribution
SELECT 
    partition,
    MIN(file_size_in_bytes) / 1024 / 1024 as min_mb,
    AVG(file_size_in_bytes) / 1024 / 1024 as avg_mb,
    MAX(file_size_in_bytes) / 1024 / 1024 as max_mb,
    COUNT(*) as file_count
FROM table.metadata.files
GROUP BY partition
HAVING file_count > 20 OR avg_mb < 64;
```

### Health Signals
- **Healthy:** 5-20 files per partition, 200-400 MB average size
- **Warning:** 20-50 files per partition, 64-200 MB average size  
- **Critical:** >50 files per partition, <64 MB average size

## Platform-Specific Considerations

### Cloud Object Storage (S3, GCS, Azure Blob)
- Larger files preferred (256-512 MB) to reduce API calls
- Sequential reads perform better than random access
- LIST operations cost scales with object count

### HDFS
- Smaller files acceptable (128-256 MB) due to lower metadata overhead
- Block size alignment matters: file size should be multiple of block size (typically 128 MB)

### Local SSD
- File size less critical, but smaller files still increase seek overhead
- Can use smaller targets (64-128 MB) if query selectivity is high

## Common Mistakes

### Mistake: Compacting Too Frequently
- **Problem:** Writing same data multiple times (write amplification)
- **Example:** Compacting every 5 minutes for streaming table
- **Fix:** Batch compactions (hourly or daily) to amortize rewrite cost

### Mistake: Ignoring File Count
- **Problem:** Focusing only on total partition size, ignoring file count
- **Example:** 10 GB partition with 1,000 files (10 MB each) is unhealthy
- **Fix:** Monitor both total size AND file count

### Mistake: One-Size-Fits-All Target
- **Problem:** Using same file size for all tables
- **Example:** 1 GB files for narrow tables with selective queries
- **Fix:** Tune target size based on table width, query patterns, and partition size

---

## Provenance

**Based on:**
- Apache Iceberg best practices documentation
- Observed operational patterns from cloud object storage deployments
- Performance tuning guidelines from Iceberg community

**Source extracts:**
- Derived from general Iceberg documentation and operational knowledge
- File metadata structure from `format/spec.md` manifest specifications
