# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 13
- Run ID: 392ee12b-fd8b-4206-a7d5-27741bb442cc
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 06:58:22
- Completed: 2026-08-14 06:59:00

## Baseline Score
- Overall: 71.45
- Dimensions:
  - file_size: 53.0
  - scan_efficiency: 50.0
  - delete_overhead: 100.0
  - manifest_organization: 95.7
  - partition_aware: 80.0
  - sort_order: 50.0
  - row_count: 667617969
  - num_data_files: 430
  - total_data_file_bytes: 30588066095
  - partition_count: 430
  - snapshot_count: 1

## Findings
### Finding 0: Are the data files evenly sized across all partitions, or do some partitions contain significantly larger or smaller files?
- Verdict: found
- Exact result: Each partition (identified by month) contains exactly one file, but file sizes range from about 280 MB to 453 MB, indicating noticeable variation across partitions.
- Rationale: The query shows file_count = 1 for every month, yet min/max/avg sizes differ widely, so files are not evenly sized.
- Recommendation: Consider normalizing file sizes or adjusting partitioning strategy if uniform file size is required for performance.
- Evidence IDs: ['trail:0']
- Validation: valid

### Finding 1: Do any partitions contain data files that exceed the recommended optimal file size (e.g., 256 MB) and could this variance be impacting scan efficiency?
- Verdict: found
- Exact result: 61 partitions have at least one file larger than 256 MB (max sizes range from ~272 MB to ~440 MB, each with a single oversized file).
- Rationale: The query returned rows where max_file_size_bytes > 268,435,456 (256 MB) for many src_sys_crt_dts_month values, indicating oversized files exist.
- Recommendation: Re‑partition or compact the oversized files to target ~256 MB per file to improve scan parallelism and reduce I/O latency.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 2: What is the distribution of row counts across the month partitions, and are there any partitions that contain a disproportionately large number of rows compared to the others?
- Verdict: found
- Exact result: The 430 month partitions each contain roughly 6 million to 10 million rows. The largest partition (month 621) has 10,003,571 rows (~1.5 % of the total), and the next several partitions are in the 9–7 million‑row range (≈1.4 %–1.1 %). The bulk of partitions fall between 6 million and 8 million rows (≈0.9 %–1.2 % of total). No single partition stands out as dramatically larger than the rest; the distribution is relatively even.
- Rationale: Row counts per month range from ~6 M to ~10 M, each representing about 1 % of total rows, indicating no disproportionate outlier.
- Recommendation: No immediate action needed; data is evenly distributed across month partitions.
- Evidence IDs: ['trail:2']
- Validation: valid

## Knowledge References Consulted

- None
