# IOMETE Table Maintenance Behavior (CORRECTED)

## Overview

IOMETE provides automated Iceberg table maintenance through a catalog-level service that runs four operations: Rewrite Data Files, Rewrite Manifest Files, Expire Snapshots, and Cleanup Orphan Files. This document describes the ACTUAL platform behavior based on official IOMETE documentation.

## Execution Architecture

### Compute Resources
- **Rewrite Data Files** and **Rewrite Manifest Files** run as **Spark SQL jobs** on user-configured compute clusters
- **Expire Snapshots** and **Cleanup Orphan Files** run directly on the `iom-maintenance` service (no compute cluster needed)


### Service Account
- User must configure a service account with:
  - `CONSUME` permission on the compute cluster
  - Write access on tables being maintained
- Maintenance runs with service account credentials, not user credentials


## Configuration Hierarchy

Property values are resolved through a **5-level precedence chain**:

1. **Table maintenance config** (IOMETE UI, highest priority)
2. **Iceberg table properties** (via `ALTER TABLE SET TBLPROPERTIES`)
3. **Catalog maintenance config** (IOMETE UI, catalog-level)
4. **Iceberg catalog properties**
5. **Platform defaults** (fallback)


## Platform Defaults (ACTUAL)

### Rewrite Data Files
- **Strategy:** `binpack`
- **Target File Size Bytes:** `512 MB` (NOT 256 MB)
- **Min File Size Bytes:** `128 MB`
- **Max File Size Bytes:** `1 GB`
- **Min Input Files:** `5`
- **Max Concurrent File Group Rewrites:** `5`
- **Delete File Threshold:** `2,147,483,647`
- **Delete Ratio Threshold:** `0.3`


### Expire Snapshots
- **Older Than:** `5 days` (NOT 7 days)
- **Retain Last:** `1` (NOT 5)


### Cleanup Orphan Files
- **Older Than:** `3 days` (enforced minimum)
- **Cron Schedule:** `0 0 * * 7` (weekly, Sunday midnight)
- **Orphan percentage threshold:** 30% (operation aborts if exceeded)


## Scheduling

### NO Default Schedule
**CRITICAL:** IOMETE does not provide a default maintenance schedule. Users MUST configure a cron schedule for:
- Rewrite Data Files
- Rewrite Manifest Files  
- Expire Snapshots

Cleanup Orphan Files has a default weekly schedule (`0 0 * * 7`).


### Schedule Format

Uses 5-field UNIX cron syntax:

```text
minute hour day-of-month month day-of-week
```

Examples:
- `0 2 * * *` - Daily at 2 AM
- `0 */4 * * *` - Every 4 hours
- `0 0 * * 0` - Weekly on Sunday at midnight


## Enabling Maintenance

### Prerequisites
1. Catalog must have an **owner domain** assigned
2. User must select a compute cluster from the owner domain
3. User must select a service account with required permissions
4. Master toggle "Enable maintenance" must be ON

### Per-Table Enablement
Even when catalog-level maintenance is enabled, each table must be **explicitly enabled** for maintenance. This is a deliberate safeguard.


## Iceberg Property Mapping

IOMETE reads certain native Iceberg properties as defaults:

| IOMETE Property | Operation | Iceberg Property |
|----------------|-----------|------------------|
| Target File Size Bytes | Rewrite Data Files | `write.target-file-size-bytes` |
| Older Than | Expire Snapshots | `history.expire.max-snapshot-age-ms` |
| Retain Last | Expire Snapshots | `history.expire.min-snapshots-to-keep` |

If these Iceberg properties exist on a table and IOMETE properties are NOT overridden, Iceberg property values are used.


## Safety Mechanisms

### Cleanup Orphan Files
- **Minimum retention:** 3 days enforced (configuring below this fails the run)
- **Orphan percentage threshold:** 30% (aborts if orphan files exceed 30% of total)
- **Batched deletion:** Files deleted in batches with cooldown to avoid overwhelming storage
- **Flink exclusion:** Files matching active Flink job checkpoint patterns (`flink.job-id.*`) are skipped


### Rewrite Data Files
- **Partial progress enabled:** Can commit incrementally to avoid all-or-nothing failures on large tables
- **Partial progress max commits:** Default 10 incremental commits per run
- **Max concurrent rewrites:** Default 5 to balance parallelism vs. commit conflicts


## Monitoring

### Run History
Query maintenance run history:
- Per-catalog history view (all tables in catalog)
- Per-table history view (specific table)
- Detail page per run showing metrics


### Key Metrics
Different metrics per operation:
- **Rewrite Data Files:** File Count, Snapshot Count, Rewritten Data Files, Rewritten Bytes
- **Rewrite Manifest Files:** Manifest Count, Snapshot Count
- **Expire Snapshots:** Snapshot Count
- **Cleanup Orphan Files:** Orphan File Count, Deleted Files


## Common Mistakes

### Mistake: Assuming Default Schedule
**Problem:** Users enable maintenance and expect it to run automatically  
**Reality:** NO default schedule for most operations - user must configure cron  
**Fix:** Explicitly configure schedule for each enabled operation

### Mistake: Wrong File Size Target
**Problem:** Assuming 256 MB target (common in generic Iceberg advice)  
**Reality:** IOMETE platform default is 512 MB  
**Fix:** Use platform default or override via table/catalog config

### Mistake: Missing Service Account Permissions
**Problem:** Maintenance enabled but runs fail with permission errors  
**Reality:** Service account needs CONSUME permission on compute cluster AND write access on tables  
**Fix:** Grant required permissions before enabling maintenance

## What This Entry REPLACES

This entry **REPLACES** the following fabricated claims:
- ❌ "Default schedule: Daily at 2:00 AM UTC" - FALSE
- ❌ "Default target file size: 256 MB" - FALSE (512 MB)
- ❌ "Dedicated compaction job pools" - FALSE (uses user compute clusters)
- ❌ "Default retention: Keep 5 most recent snapshots" - FALSE (1 snapshot, 5 days)
- ❌ "Quirk: Snapshot Retention Override" - FABRICATED
- ❌ "Quirk: Metadata Refresh Delay" - FABRICATED
- ❌ "Quirk: Cross-Partition Ordering" - FABRICATED

---

## Provenance

**Based on:**

**Validation Date:** 2026-02-20  
**Status:** Validated against actual IOMETE user guide documentation
