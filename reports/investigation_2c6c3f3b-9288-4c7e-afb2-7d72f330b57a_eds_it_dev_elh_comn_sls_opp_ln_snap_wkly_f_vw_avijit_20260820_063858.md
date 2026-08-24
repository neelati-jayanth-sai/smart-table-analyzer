# Investigation Report: eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit

## Summary
- Total findings: 5
- Validated findings: 4
- Hook violations: 1
- Total queries: 10

## Investigation Metadata
- Investigation ID: 59
- Run ID: 2c6c3f3b-9288-4c7e-afb2-7d72f330b57a
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-20 06:36:17
- Completed: 2026-08-20 06:38:58

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
- Verdict: inconclusive
- Exact result: error
- Rationale: Quality gate rejection: Exact result contains placeholder: 'error'
- Recommendation: N/A
- Evidence IDs: []
- Validation: INVALID
  - Errors: ['Finding has no evidence IDs']

### Finding 1: Which columns have high cardinality and could be good partition candidates?
- Verdict: found
- Exact result: opp_id, prod_grp_id, sls_acct_id
- Rationale: opp_id shows the highest distinct count (likely one‑to‑one), making it a high‑cardinality column and a strong partition candidate; prod_grp_id and sls_acct_id have lower distinct counts and are less ideal.
- Recommendation: Use opp_id as the primary partition column (identity transform). Consider prod_grp_id or sls_acct_id only if query patterns frequently filter on them.
- Evidence IDs: ['trail:1', 'knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: What are the recommended partition columns based on column analysis?
- Verdict: found
- Exact result: Distinct snapshot_dt_month values observed: 640, 678, 679 (3 unique values in 40 rows)
- Rationale: snapshot_dt_month is a low‑cardinality, time‑based column (3 distinct months) making it an ideal partition key for month‑level queries, per the partition‑strategy guidelines.
- Recommendation: Partition the table on snapshot_dt_month. If queries also filter on another dimension, consider a multi‑column partition (e.g., snapshot_dt_month + a high‑cardinality categorical column).
- Evidence IDs: ['trail:2', 'knowledge:runbooks/partition-strategy-guidelines@a760581385e4']
- Validation: valid

### Finding 3: Is the current partitioning on snapshot_dt_month resulting in balanced partition sizes, or are there partitions that are disproportionately large or small?
- Verdict: found
- Exact result: min_records=5,312,488; max_records=27,147,271; avg_records≈18,052,646; partition_cnt=40
- Rationale: The largest partition holds ~5× more rows than the smallest, indicating significant skew; balanced partitions would have a narrower range around the average.
- Recommendation: Re‑evaluate the snapshot_dt_month partitioning—add a finer granularity (e.g., snapshot_dt_day) or combine with a bucket transform to even out partition sizes.
- Evidence IDs: ['trail:3']
- Validation: valid

### Finding 4: What is the distribution of file sizes across the 40 partitions, and are there any partitions with unusually large or small files?
- Verdict: found
- Exact result: The three shown partitions (snapshot_dt_month 640, 641, 642) have avg file sizes of 255 MB, 197 MB, and 198 MB respectively, each classified as "Normal" against the overall average of 198 MB. No unusually large or small files appear in these rows.
- Rationale: The result rows include avg_file_size_bytes and size_category, allowing a direct comparison to the overall average. All three are within normal bounds, so no outliers are present in the displayed subset.
- Recommendation: Collect the missing 37 partition rows to see the full distribution. If any partition’s avg_file_size deviates >2× the overall average (≈400 MB) or <0.5× (≈100 MB), flag it as an outlier and consider re‑partitioning or file compaction per Iceberg file‑size best practices.
- Evidence IDs: ['trail:4']
- Validation: valid

## Knowledge References Consulted

- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-20 06:36:20)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-20 06:36:38)
- `runbooks/partition-strategy-guidelines@a760581385e4` (fetched 2026-08-20 06:38:24)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-20 06:38:49)
