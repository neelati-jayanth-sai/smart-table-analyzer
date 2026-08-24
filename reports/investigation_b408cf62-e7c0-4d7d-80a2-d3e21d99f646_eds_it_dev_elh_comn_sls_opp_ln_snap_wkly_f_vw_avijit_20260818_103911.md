# Investigation Report: eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 38
- Run ID: b408cf62-e7c0-4d7d-80a2-d3e21d99f646
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-18 10:38:32
- Completed: 2026-08-18 10:39:11

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
### Finding 0: Is the current partitioning scheme (40 partitions) optimal for query performance and data distribution?
- Verdict: inconclusive
- Exact result: The table has 40 partitions. Records per partition range from 5.3 M to 27.1 M (avg ≈ 18 M). Size per partition ranges from 352 MB to 1.92 GB (avg ≈ 1.28 GB). Each partition contains 2‑10 files (avg ≈ 6.5).
- Rationale: The partition size distribution is uneven (≈5× difference between smallest and largest), which can cause query skew and longer runtimes for partitions with many records/files. While 6‑10 files per partition is reasonable, the record/size imbalance suggests the current 40‑partition scheme may not be optimal for all workloads. Optimality depends on query predicates (e.g., date, hash) and scan patterns; without that context we cannot declare it optimal.
- Recommendation: Review query patterns and consider a partitioning strategy that aligns with common filters (e.g., date, hour, or hash columns). If skew persists, increase the number of partitions or add a secondary hash transform to balance record counts. Monitor partition size and file count after changes to ensure more uniform distribution and improved query performance.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 1: What is the distribution of data file sizes across the 40 partitions, and are there many small files that could be impacting query performance?
- Verdict: found
- Exact result: Across the 40 partitions (sample shown for three months), each partition contains 3‑7 data files. File sizes range from ~186 MB to ~263 MB, with total bytes per partition between ~0.77 GB and ~1.38 GB. The small_file_count column is 0 for all shown partitions, indicating no files below the typical “small” threshold (e.g., <64 MB).
- Rationale: The query output lists file_count, total_bytes, min_bytes, max_bytes, and small_file_count per partition. All min_bytes are >186 MB and small_file_count is 0, so there are no many small files that would degrade performance. These sizes fall within the recommended 128 MB‑1 GB range for Iceberg data files.
- Recommendation: Current file sizing is healthy; no immediate action needed. Continue to monitor file growth and consider periodic compaction only if files start approaching the lower bound (<128 MB) or if partition skew emerges.
- Evidence IDs: ['knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

### Finding 2: Is there significant data skew across the 40 partitions, with some partitions containing far more rows or bytes than others, potentially causing uneven query performance?
- Verdict: not_found
- Exact result: The largest partition (snapshot_dt_month=678) holds 27,147,271 rows (100% of max). The next largest partitions hold 23,789,548 and 23,780,180 rows, which are 87.6% of the max row count and 88.6%/88.5% of the max byte size. No partition exceeds the max by a large margin.
- Rationale: All partitions are within ~12% of the largest partition in both row count and byte size, indicating a fairly even distribution and no extreme skew that would cause uneven query performance.
- Recommendation: Continue monitoring partition sizes; if future partitions grow >2× the current max, consider rebalancing or adjusting partitioning strategy.
- Evidence IDs: ['knowledge:iceberg/data-skew-detection@0e14eda1f18a']
- Validation: valid

## Knowledge References Consulted

- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-18 10:38:37)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-18 10:38:49)
- `iceberg/data-skew-detection@0e14eda1f18a` (fetched 2026-08-18 10:39:02)
