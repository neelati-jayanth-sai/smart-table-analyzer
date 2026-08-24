# Tested Table-Property Profiles

## Cross-cutting rules

- Use `zstd` compression in all tested profiles.
- Use snapshot isolation for update, delete, and merge operations.
- Keep `history.expire.min-snapshots-to-keep` below
  `write.metadata.previous-versions-max`; the tested relationship is 5 below 10.
- Use `write.metadata.metrics.default = full` when consumption needs rich
  metrics; use `truncate(16)` where write-oriented metadata cost is the trade-off.

## Property-key casing is an effective-configuration check

Write every Iceberg configuration property with its exact lowercase canonical
key. A mixed- or uppercase key can appear in `SHOW TBLPROPERTIES` or DDL yet
not be read as the intended configuration. DDL presence is therefore not proof
that a setting is active.

- Treat a mis-cased known configuration key (for example,
  `Write.Target-File-Size-Bytes`) as a high-severity configuration risk.
- If both `write.target-file-size-bytes` and a case variant exist, retain the
  canonical key as the effective setting and report the variant as a collision.
- Keep the exact raw DDL keys in evidence; do not normalize them before
  checking effectiveness.
- A mis-cased unknown custom property is a naming caution, not evidence that a
  table behavior is wrong.

## Distribution and sorting

| Table layout | Write distribution | Merge distribution | Notes |
| --- | --- | --- | --- |
| Partitioned and sorted | `range` | `hash` | Range improves sorted consumption; hash avoids tested merge-ingestion cost |
| Partitioned, no sort | `hash` | `hash` | Keeps a partition's writes together |
| Unpartitioned or balanced, no sort | `hash` | `hash` | Tested alternatives showed no consumption advantage for `none` |
| Large, consumption-oriented sorted table | `range` | `hash` | Report the expected ingestion cost |

Never recommend `range` merely because it exists. It requires a justified sort
order and consumption benefit; otherwise prefer `hash`.

## Write-mode selection

| Condition | Profile |
| --- | --- |
| Incremental load is more than 90% new records, or touches few partitions | Prefer COW |
| Row-level updates/deletes need lower ingest latency | MOR only with a stated compaction cadence |
| COW with Z-order | Compact after every ingestion in the tested profile |
| MOR | Compact after 3-7 incremental loads; validate the table-specific cadence |

Use a sort order for DEL/INSERT or MERGE/UPSERT workloads when the access
pattern supports it. A sort order is not automatically a partition key.

## Consumption additions

Use these only for the matching tested profile:

- `read.parquet.vectorization.batch-size = 10000` for standard consumption;
  `20000` for large, dense consumption workloads.
- Bloom filters are candidates for heavily queried equality driver columns;
  the CUST_PROD_CMPNT test used a false-positive probability of `0.01`.
- `write.summary-partition-limit = 10` was used in large tested profiles.

## Example: sorted partitioned writer

```sql
ALTER TABLE db.table SET TBLPROPERTIES (
  'write.distribution-mode' = 'range',
  'write.merge.distribution-mode' = 'hash',
  'write.parquet.compression-codec' = 'zstd',
  'history.expire.min-snapshots-to-keep' = '5',
  'write.metadata.previous-versions-max' = '10'
);
```

This is proposed SQL. Check actual DDL, workload, and platform support before
execution.

## Provenance

Team-verified ingestion and consumption test matrix supplied 2026-08-24.
