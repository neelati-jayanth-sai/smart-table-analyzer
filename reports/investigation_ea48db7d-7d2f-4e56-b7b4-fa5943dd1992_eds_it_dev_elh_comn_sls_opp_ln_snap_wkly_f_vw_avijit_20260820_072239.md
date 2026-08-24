# Investigation Report: eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit

## Summary
- Total findings: 5
- Validated findings: 4
- Hook violations: 0
- Total queries: 6

## Investigation Metadata
- Investigation ID: 61
- Run ID: ea48db7d-7d2f-4e56-b7b4-fa5943dd1992
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-20 07:20:11
- Completed: 2026-08-20 07:22:39

## Baseline Score
- Overall: 91.39
- Dimensions:
  - file_size: 68.21
  - scan_efficiency: 100.0
  - delete_overhead: 100.0
  - manifest_organization: 99.48
  - partition_aware: 100.0
  - row_count: 722105849
  - num_data_files: 261
  - total_data_file_bytes: 51355373891
  - partition_count: 40
  - snapshot_count: 3
  - is_empty: False

## Findings
### Finding 0: Are there any CAPS issues or deprecated properties in the table configuration?
- Verdict: not_found
- Exact result: {"has_caps_issues": false, "caps_warnings": ""}
- Rationale: The query result shows has_caps_issues is false and caps_warnings is empty, indicating no CAPS issues or deprecated properties.
- Recommendation: No action required; table configuration is free of CAPS issues.
- Evidence IDs: ['trail:0']
- Validation: valid

### Finding 1: Which columns have high cardinality and could be good partition candidates?
- Verdict: found
- Exact result: opp_id, prod_grp_id, sls_acct_id
- Rationale: opp_id is likely unique per row, giving the highest cardinality and making it the strongest partition candidate; prod_grp_id and sls_acct_id have lower but still notable distinct counts.
- Recommendation: Use opp_id as the primary partition column; consider prod_grp_id or sls_acct_id as secondary partitions if query patterns filter on them frequently.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 2: What are the recommended partition columns based on column analysis?
- Verdict: found
- Exact result: snapshot_dt_month
- Rationale: Column analysis shows snapshot_dt_month has a small set of distinct values (e.g., 640‑679), making it low‑cardinality and ideal for partitioning.
- Recommendation: Partition the table on snapshot_dt_month (e.g., using an identity or month transform).
- Evidence IDs: ['trail:2']
- Validation: valid

### Finding 3: Is there significant size skew among the 40 partitions, indicating that some partitions are much larger than others?
- Verdict: found
- Exact result: max_to_min_ratio = 5.45 (max size 1.92 GB, min size 0.35 GB) across 40 partitions
- Rationale: A ratio >5 shows one partition is over five times larger than the smallest, indicating notable size skew.
- Recommendation: Consider repartitioning to achieve more balanced sizes, e.g., add finer-grained partition columns or increase the number of partitions.
- Evidence IDs: ['trail:3', 'knowledge:iceberg/data-skew-detection@0e14eda1f18a']
- Validation: valid

### Finding 4: What is the distribution of manifest files across the 40 partitions, and are any partitions burdened with a disproportionately high number of manifests?
- Verdict: inconclusive
- Exact result: Only 3 of the 40 partitions are shown (snapshot_dt_month 678:10 manifests, 669:9 manifests, 672:9 manifests) with an overall average of 6.525 manifests per partition. The full distribution across all 40 partitions is not available.
- Rationale: Quality gate rejection: Finding has inconclusive verdict
- Recommendation: N/A
- Evidence IDs: ['trail:4']
- Validation: valid

## Knowledge References Consulted

- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-20 07:20:15)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-20 07:20:24)
- `iceberg/data-skew-detection@0e14eda1f18a` (fetched 2026-08-20 07:22:20)
- `iceberg/manifest-file-structure@9e9b57029b06` (fetched 2026-08-20 07:22:32)
