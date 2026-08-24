# Validated Workload Profiles

## Purpose

This runbook is the decision seam for the team-verified tests supplied on
2026-08-24. It prevents one file-size, distribution, or compaction rule from
being applied to every Iceberg table.

## Profile matrix

| Profile | Key evidence | File / row-group | Layout | Maintenance |
| --- | --- | --- | --- | --- |
| X-small | <=5 GB or low rewrite cost | 128 MB / 24-32 MB | Hash without sort; range when sorted for consumption | Frequent only when writes create small files |
| Balanced ingestion | Moderate table, write priority | 128 MB / 32 MB | Hash unless sorted consumption needs range | Based on file health |
| Large consumption | Large scans or consumption priority | 512 MB / 128 MB | Range with tested sort; merge distribution hash | Monitor ingestion cost and compact MOR |
| Narrow high-density | Few columns, high rows relative to dataset size | Test 128 MB / 24-32 MB first | Monthly partitioning is a candidate when workload permits | Compare against 512/128 |
| MOR | Row-level changes need ingest latency | Select surrounding size profile | Range only with justified sort; otherwise hash | Compact after 3-7 loads |
| COW with Z-order | Consumption ordering requires Z-order | 128 MB / 32 MB in tested case | `none` in tested rewrite flow | Compact after every ingestion |

## Selection process

1. Read DDL and table properties.
2. Measure file and partition capacity from Iceberg metadata.
3. Identify driver predicates and whether reads are consumption-heavy.
4. Classify COW or MOR and the proportion of new records.
5. Select one profile or mark the result `needs_review`.
6. Validate any change on representative data; do not apply the matrix as an
   automatic DDL rewrite.

## Common tested settings

- Compression: `zstd`.
- Snapshot isolation for update, delete, and merge.
- Range distribution for partitioned + sorted consumption layouts.
- Hash distribution for partitioned/no-sort and unpartitioned layouts.
- `full` column metrics for consumption-oriented profiles; `truncate(16)` when
  write-oriented metadata cost is the trade-off.

## Evidence limitations

The tests establish useful profiles, not universal causality. Do not claim a
profile fits a table without matching DDL, workload, and metadata evidence.
Exact bloom-filter and vectorization settings require the matching profile.

## Provenance

Normalized from team-verified ingestion and consumption test screenshots
supplied 2026-08-24.
