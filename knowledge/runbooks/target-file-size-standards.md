# Tested File-Size Standards

## Authority and scope

These team-verified profiles were normalized from the 2026-08-24 ingestion
and consumption tests. They override generic defaults where they apply.
There is no universal target file size.

Select a profile from table size, width/row density, partitioning, write mode,
sort order, and whether ingestion or consumption is the priority. A
recommendation must name its selected profile and evidence.

## Verified profiles

| Profile | Target file size | Row group | Tested use |
| --- | ---: | ---: | --- |
| X-small (<=5 GB) or write-oriented balanced | 128 MB | 24-32 MB | Low rewrite cost; small/balanced tables |
| Moderate fact-table ingestion | 128 MB | 32 MB | Faster ingestion; compaction may be frequent |
| Large consumption-oriented COW or MOR | 512 MB | 128 MB | Large scans and consumption priority |
| Narrow, high-row-density table | Test 128/24-32 first | 24-32 MB | CUST_PROD_CMPNT test favoured this over 512/256 |

`128 MB` is a profile value, not a generic defect threshold. `512 MB` is
likewise a profile value, not a platform-wide mandate.

## Compaction urgency

Use file count, file-size distribution, write mode, and the selected profile
together. Do not label a table unhealthy merely because it differs from another
profile's target.

| Observed condition | Action |
| --- | --- |
| Files below 32 MB or more than 50 files in one partition | Investigate and compact urgently |
| 32-64 MB files, or 20-50 files in one partition | Plan targeted compaction |
| 64-128 MB files | Acceptable for a 128 MB profile; review against the selected profile |
| COW with Z-order | Compact after every tested ingestion run |
| MOR incremental loads | Plan compaction after 3-7 loads; SO_DTL_FACT used five |

Scope maintenance to affected partitions whenever possible. Compaction rewrites
data and must not be presented as a no-cost recommendation.

## Required report fields

Every size recommendation must state the selected workload profile, current and
proposed file/row-group size, partition byte/file-count distribution, COW/MOR
mode, compaction cadence, and whether it optimizes ingestion or consumption.

## Configuration examples

```sql
-- 128 MB write-oriented profile
ALTER TABLE db.table SET TBLPROPERTIES (
  'write.target-file-size-bytes' = '134217728',
  'write.parquet.row-group-size-bytes' = '33554432',
  'write.parquet.compression-codec' = 'zstd'
);

-- 512 MB large consumption profile
ALTER TABLE db.table SET TBLPROPERTIES (
  'write.target-file-size-bytes' = '536870912',
  'write.parquet.row-group-size-bytes' = '134217728',
  'write.parquet.compression-codec' = 'zstd'
);
```

Validate examples on a representative workload before production change.

## Provenance

Team-verified ingestion and consumption test matrix supplied 2026-08-24.
