# Tested Maintenance Schedule

## Principle

Maintenance is profile- and workload-driven. Do not claim that it runs
automatically or at a universal platform time. Each table needs an enabled,
owned maintenance plan and an observed trigger.

## Tested compaction triggers

| Condition | Maintenance action |
| --- | --- |
| COW with Z-order | Compact after every ingestion |
| MOR incremental writes | Compact after 3-7 loads; SO_DTL_FACT used five |
| Files under 32 MB or more than 50 files per partition | Urgent targeted compaction |
| 32-64 MB files or 20-50 files per partition | Schedule targeted compaction |
| High active-write partition | Compact only settled/recent partitions where possible |

The report must say whether cadence is measured, a tested profile rule, or a
proposed trial. Never present a compaction interval as a platform default
without configured-job evidence.

## Safe maintenance workflow

1. Confirm current DDL, table properties, COW/MOR mode, and active partition
   spec.
2. Identify affected partitions from file counts, bytes, and delete files.
3. Confirm no conflicting ingestion or critical consumption job is running.
4. Run scoped maintenance and record files/bytes before and after.
5. Re-check query planning and consumption performance.

## Snapshot and metadata settings

The tested relationship is:

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
  'history.expire.min-snapshots-to-keep' = '5',
  'write.metadata.previous-versions-max' = '10',
  'write.metadata.delete-after-commit.enabled' = 'true'
);
```

This is a configuration profile, not evidence that expiry or cleanup has run.
Verify maintenance-job enablement and run history separately.

## Escalation

Escalate for an explicit maintenance review when planning time exceeds the
service objective, a compaction job fails or times out, delete files grow, or a
partition cannot form files suitable for its selected profile.

## Provenance

Team-verified ingestion and consumption test matrix supplied 2026-08-24.
