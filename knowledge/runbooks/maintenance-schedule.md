# Table Maintenance Schedule

## Overview

This runbook defines when and how to run maintenance operations (compaction, snapshot expiry, manifest compaction) on Iceberg tables. Following this schedule prevents performance degradation and controls storage costs.

## Standard Maintenance Windows

### Daily Maintenance (2:00 AM - 4:00 AM UTC)
**Operations:**
- Automatic compaction jobs (managed by IOMETE)
- Snapshot expiry (platform-managed)

**Tables affected:** All production tables with `iomete.compact.enabled = true`

### Weekly Maintenance (Sunday 1:00 AM - 6:00 AM UTC)
**Operations:**
- Manifest compaction
- Partition statistics refresh
- Metadata cleanup

**Tables affected:** All production tables > 100 GB

### Monthly Maintenance (First Saturday 10:00 PM - 6:00 AM UTC)
**Operations:**
- Deep compaction (rewrite all files to target size)
- Orphan file cleanup
- Table health review

**Tables affected:** Tables flagged in weekly review as needing deep maintenance

## Compaction Frequency by Table Type

### High-Frequency Streaming Tables
- **Frequency:** Every 2 hours
- **Scope:** Recent partitions only (last 24 hours)
- **Target:** Consolidate micro-batches from streaming writes
- **Schedule:** `0 */2 * * *`

### Daily Batch Tables
- **Frequency:** Daily at 3:00 AM
- **Scope:** Yesterday's partition only
- **Target:** Consolidate files from daily load
- **Schedule:** `0 3 * * *`

### Weekly Batch Tables
- **Frequency:** Weekly on Sunday
- **Scope:** Last week's partitions
- **Target:** Consolidate weekly load
- **Schedule:** `0 2 * * 0`

### Append-Only Archive Tables
- **Frequency:** Monthly
- **Scope:** All partitions
- **Target:** Periodic consolidation only
- **Schedule:** `0 1 1 * *`

## Snapshot Expiry Schedule

### Production Tables
**Expiry policy:**

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'iomete.snapshot.min-to-keep' = '5',
    'iomete.snapshot.max-age-days' = '7'
);
```

**Rationale:** 7-day retention for rollback, minimum 5 snapshots for safety

### Development Tables
**Expiry policy:**

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'iomete.snapshot.min-to-keep' = '3',
    'iomete.snapshot.max-age-days' = '2'
);
```

**Rationale:** Aggressive expiry to minimize dev environment storage cost

### Compliance Tables
**Expiry policy:**

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
    'iomete.snapshot.min-to-keep' = '30',
    'iomete.snapshot.max-age-days' = '90'
);
```

**Rationale:** Extended retention for audit trail and compliance

## Manifest Compaction

### When to Run
- Manifest count > 30 per snapshot
- Average manifest size < 2 MB
- Query planning time > 10 seconds

### How to Run

```sql
CALL system.rewrite_manifests(
    table => 'db.table',
    options => map(
        'target-manifest-size', '8388608',  -- 8 MB target
        'min-manifests-to-compact', '10'
    )
);
```

### Frequency
- **Default:** Monthly for all tables
- **High-frequency:** Weekly for tables with > 50 writes/day

## Orphan File Cleanup

### When to Run
After snapshot expiry to reclaim storage from deleted files

### How to Run

```sql
CALL system.remove_orphan_files(
    table => 'db.table',
    older_than => TIMESTAMP '2024-01-01 00:00:00',
    dry_run => true  -- First run dry_run to preview
);
```

**Safety:** Always run with `dry_run => true` first, review output, then run with `dry_run => false`

### Frequency
- **Default:** Monthly, 1 week after snapshot expiry
- **High-write tables:** Weekly

## Maintenance Checklist

### Before Scheduled Maintenance
- [ ] Verify no critical queries running in maintenance window
- [ ] Check available compute capacity (compaction needs resources)
- [ ] Review last maintenance run for any failures
- [ ] Confirm backup/snapshot retention is adequate

### During Maintenance
- [ ] Monitor job progress via IOMETE console
- [ ] Check for errors or timeouts
- [ ] Verify resource utilization stays within limits
- [ ] Track storage delta (temporary increase normal)

### After Maintenance
- [ ] Verify job completed successfully
- [ ] Check file count decreased (for compaction)
- [ ] Confirm snapshot count within retention policy
- [ ] Validate query performance improved or maintained
- [ ] Document any issues or anomalies

## Emergency Maintenance

### When to Run Unscheduled Maintenance
- **Critical file health:** Partition has > 100 files or average < 32 MB
- **Query performance degradation:** Planning time > 30 seconds
- **Storage cost spike:** Unexplained storage increase > 20%
- **Failed scheduled job:** Needs immediate retry

### Emergency Procedure
1. Identify affected table and issue
2. Post in #data-platform Slack channel
3. Run targeted maintenance (single partition or table)
4. Monitor during execution
5. Document root cause and prevention

## Monitoring and Alerts

### Pre-Maintenance Alerts (1 hour before)
Notify team via Slack:
- Which tables will be maintained
- Expected duration
- Potential query impact (if any)

### Post-Maintenance Report (within 1 hour after)
Automated report includes:
- Tables processed
- Files compacted (before/after count)
- Snapshots expired
- Storage reclaimed
- Any failures or warnings

### Health Metrics Dashboard
Real-time dashboard tracking:
- File count per partition
- Average file size per table
- Snapshot count per table
- Last compaction timestamp
- Last expiry timestamp

## Troubleshooting

### Compaction Timeout
**Symptom:** Job exceeds 4-hour limit, partial completion

**Fix:** Reduce scope to single partition or increase timeout

### Snapshot Expiry Not Running
**Symptom:** Snapshot count keeps growing

**Fix:** Check `iomete.snapshot.auto-expire` property, verify scheduler status

### Storage Cost Not Decreasing After Expiry
**Symptom:** Snapshots expired but storage usage unchanged

**Fix:** Run orphan file cleanup (expiry deletes metadata, cleanup deletes files)

---

## Provenance

**Based on:**
- Team operational runbooks
- Observed maintenance patterns on production IOMETE cluster
- Incident post-mortems and lessons learned

**Source:** Team runbook, maintained by data platform team
