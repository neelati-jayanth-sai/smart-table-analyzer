# Investigation Report: eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 36
- Run ID: 317f8195-dae0-4fc1-a4d4-e0a21ec9cd64
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-18 10:25:35
- Completed: 2026-08-18 10:26:14

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
### Finding 0: Is the data distribution across the 40 partitions balanced, or does the table exhibit significant partition skew?
- Verdict: found
- Exact result: skew_ratio = 5.11 (max_records/min_records), indicating a >5‑fold difference between the smallest and largest partitions
- Rationale: A skew_ratio far greater than 1 (e.g., >2–3) signals significant partition skew per Iceberg data‑skew detection guidelines.
- Recommendation: Re‑evaluate the partitioning strategy (e.g., add more granular keys, rebalance data, or use bucketing) to achieve a more even record distribution across partitions.
- Evidence IDs: ['knowledge:iceberg/data-skew-detection@0e14eda1f18a']
- Validation: valid

### Finding 1: Are the partition columns used for eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit aligned with the most common query predicates, and is the partitioning scheme optimal for query performance?
- Verdict: inconclusive
- Exact result: The table is partitioned by the column snapshot_dt_month, but no information is provided about the most common query predicates to determine alignment.
- Rationale: While Iceberg supports partition transforms (e.g., identity on a date column) that can improve pruning when queries filter on that column, we lack query workload data to confirm that snapshot_dt_month is frequently used in predicates. Therefore we cannot assert optimality.
- Recommendation: Review query logs to identify the most frequent filter columns. If queries commonly filter by month or date, the current partition on snapshot_dt_month is appropriate. Otherwise, consider adding or changing partitions (e.g., year, month, or identity on other high‑cardinality columns) to improve pruning and reduce scanned data.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: Is the data within each of the 40 partitions sorted on a column (e.g., a date or primary key) that matches common query predicates, to enable efficient pruning and improve performance for potential downstream consumers?
- Verdict: found
- Exact result: All 261 data files have a sort order defined, and there is only one distinct sort order across them.
- Rationale: The query shows files_with_sort_order equals total_files and distinct_sort_orders is 1, indicating every file is sorted on the same column(s). This matches Iceberg’s sort‑order optimization, which enables effective min/max pruning for common predicates.
- Recommendation: Downstream consumers can rely on the existing sort order for efficient range filtering and partition pruning; ensure queries target the sorted column (e.g., date or primary key) to maximize performance.
- Evidence IDs: ['knowledge:iceberg/sort-order-optimization@42de3a77462c']
- Validation: valid

## Knowledge References Consulted

- `iceberg/data-skew-detection@0e14eda1f18a` (fetched 2026-08-18 10:25:40)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-18 10:25:52)
- `iceberg/sort-order-optimization@42de3a77462c` (fetched 2026-08-18 10:26:06)
