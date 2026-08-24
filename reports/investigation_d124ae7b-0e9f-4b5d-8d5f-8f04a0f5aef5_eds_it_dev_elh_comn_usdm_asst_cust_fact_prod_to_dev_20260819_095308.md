# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 51
- Run ID: d124ae7b-0e9f-4b5d-8d5f-8f04a0f5aef5
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 09:52:28
- Completed: 2026-08-19 09:53:08

## Baseline Score
- Overall: 78.12
- Dimensions:
  - file_size: 53.0
  - scan_efficiency: 90.0
  - delete_overhead: 100.0
  - manifest_organization: 95.7
  - partition_aware: 80.0
  - sort_order: 50.0
  - row_count: 667617969
  - num_data_files: 430
  - total_data_file_bytes: 30588066095
  - partition_count: 430
  - snapshot_count: 1
  - is_empty: False
  - catalog_score: 50.0
  - downstream_count: 0
  - upstream_count: 0
  - has_catalog_context: True

## Findings
### Finding 0: Are the 430 partitions of `eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev` evenly sized, or is there evidence of data skew across partitions?
- Verdict: found
- Exact result: min_records=1, max_records=10003571, min_bytes=11321, max_bytes=453211739 (430 partitions, total_records=667617969, total_bytes=30588066095)
- Rationale: The gap between the smallest and largest partition (1 vs 10 M records, 11 KB vs 453 MB) shows extreme imbalance, confirming data skew.
- Recommendation: Re‑evaluate the partitioning strategy—use higher‑cardinality columns, increase partition count, or apply bucketing to achieve more uniform partition sizes.
- Evidence IDs: ['knowledge:iceberg/data-skew-detection@0e14eda1f18a']
- Validation: valid

### Finding 1: What is the distribution of file sizes across the 430 partitions of `eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev`, and are there a large number of very small files that could impact read performance?
- Verdict: found
- Exact result: Across the 430 partitions, each partition contains a single data file. File sizes range from ~15 MB to ~55 MB (min = 15 MB, max = 55 MB, average ≈ 30 MB). Every file is counted as a "small file" (small_file_count = 1 per partition). This means the table consists of ~430 very small files, well below Iceberg’s recommended 128 MB–1 GB per file.
- Rationale: Iceberg performance guidelines advise keeping files ≥128 MB to avoid excessive file‑open overhead; the observed ~30 MB average indicates many small files that can degrade read performance.
- Recommendation: Consider compacting the existing files into larger ones (e.g., 256 MB–512 MB) using an Iceberg rewrite or MERGE operation, and adjust future write settings to target the recommended file size range.
- Evidence IDs: ['knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

### Finding 2: What is the total number of manifest files for `eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev`, and how are their sizes distributed? Are there many small manifest files that could increase query planning overhead?
- Verdict: found
- Exact result: The table `eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev` has exactly **1 manifest file** (manifest_file_count = 1). With only a single manifest, there are no numerous small manifest files that could add query‑planning overhead.
- Rationale: The query result reports manifest_file_count = 1, and Iceberg’s manifest architecture shows that planning cost grows with many small manifests. Since only one manifest exists, overhead is minimal.
- Recommendation: No immediate action needed; the manifest count is low. Continue monitoring after future data loads to ensure manifest count remains modest.
- Evidence IDs: ['knowledge:iceberg/manifest-file-structure@9e9b57029b06']
- Validation: valid

## Knowledge References Consulted

- `iceberg/data-skew-detection@0e14eda1f18a` (fetched 2026-08-19 09:52:34)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-19 09:52:45)
- `iceberg/manifest-file-structure@9e9b57029b06` (fetched 2026-08-19 09:52:56)
- `iceberg/delete-file-handling@8f58d0073a71` (fetched 2026-08-19 09:52:56)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 09:52:56)
