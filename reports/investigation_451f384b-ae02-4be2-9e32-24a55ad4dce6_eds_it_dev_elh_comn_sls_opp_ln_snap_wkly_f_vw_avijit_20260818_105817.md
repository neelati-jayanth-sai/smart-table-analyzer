# Investigation Report: eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 41
- Run ID: 451f384b-ae02-4be2-9e32-24a55ad4dce6
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-18 10:57:35
- Completed: 2026-08-18 10:58:17

## Baseline Score
- Overall: 79.56
- Dimensions:
  - file_size: 100.0
  - scan_efficiency: 50.0
  - delete_overhead: 100.0
  - manifest_organization: 97.39
  - partition_aware: 80.0
  - sort_order: 50.0
  - row_count: 722105849
  - num_data_files: 261
  - total_data_file_bytes: 51355373891
  - partition_count: 40
  - snapshot_count: 3
  - is_empty: False
  - catalog_score: 50.0
  - downstream_count: 0
  - upstream_count: 0
  - has_catalog_context: False

## Findings
### Finding 0: Are the 40 partitions defined for this table aligned with common query predicates and evenly distributed in size to avoid data skew?
- Verdict: inconclusive
- Exact result: The table has 40 partitions with record counts ranging from 5.3 M to 27.1 M (≈5× difference) and sizes from 352 MB to 1.92 GB (≈5× difference). This indicates uneven distribution and potential data skew. No information is provided about the partition columns or typical query predicates, so alignment with common query patterns cannot be determined.
- Rationale: Quality gate rejection: Finding has inconclusive verdict
- Recommendation: N/A
- Evidence IDs: ['trail:0', 'knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 1: Is the data evenly distributed across the 40 partitions in terms of file size, or does any partition contain a disproportionate amount of data indicating skew?
- Verdict: found
- Exact result: The partition file sizes range from 352,588,952 bytes (≈0.35 GB) to 1,920,425,559 bytes (≈1.92 GB), a >5× difference. The average per partition is 1,283,884,347 bytes, while observed percentages of total data per partition are 3.3‑3.7 % (vs. an even share of 2.5 %). This variation indicates a disproportionate amount of data in some partitions, i.e., data skew.
- Rationale: Skew is identified when max/min file sizes differ markedly from the average or expected equal share. Here the max is ~5× the min and exceeds the average, confirming uneven distribution.
- Recommendation: Consider rebalancing the data: increase the number of buckets or adjust the partitioning scheme (e.g., finer time granularity) to distribute data more evenly across partitions and improve query performance.
- Evidence IDs: ['knowledge:iceberg/data-skew-detection@0e14eda1f18a']
- Validation: valid

### Finding 2: Is the manifest organization for this table optimal, with a limited number of consolidated manifest files, to minimize scan overhead and improve query performance?
- Verdict: found
- Exact result: The table has 3 distinct manifest lists for 3 snapshots, indicating each snapshot uses its own manifest list rather than a consolidated set of manifest files.
- Rationale: Optimal manifest organization consolidates manifests to a few lists, reducing the number of files scanned per query. Having a manifest list per snapshot increases scan overhead.
- Recommendation: Consider consolidating manifest files across snapshots (e.g., using Iceberg’s manifest merging or rewrite‑manifest operations) to limit the number of manifest lists and improve query performance.
- Evidence IDs: ['knowledge:iceberg/manifest-file-structure@9e9b57029b06']
- Validation: valid

## Knowledge References Consulted

- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-18 10:57:41)
- `iceberg/data-skew-detection@0e14eda1f18a` (fetched 2026-08-18 10:57:56)
- `iceberg/manifest-file-structure@9e9b57029b06` (fetched 2026-08-18 10:58:10)
