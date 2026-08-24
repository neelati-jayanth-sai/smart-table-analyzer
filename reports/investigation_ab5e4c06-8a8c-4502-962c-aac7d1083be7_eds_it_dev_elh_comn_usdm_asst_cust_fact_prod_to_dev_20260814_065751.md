# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 12
- Run ID: ab5e4c06-8a8c-4502-962c-aac7d1083be7
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 06:57:13
- Completed: 2026-08-14 06:57:51

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
- Exact result: Each partition (src_sys_crt_dts_month) contains exactly one file, with sizes ranging from 280,532,228 bytes to 453,211,739 bytes. The variation in file size indicates that the data files are not evenly sized across partitions.
- Rationale: The query shows file_count = 1 for every partition and the min, max, and avg bytes differ per partition, confirming size disparity.
- Recommendation: If uniform file sizes are desired for balanced processing, consider adjusting the partitioning logic or splitting larger files to achieve more even distribution.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 1: What is the distribution of row counts across the src_sys_crt_dts_month partitions, and are there partitions with significantly higher or lower row counts indicating data skew?
- Verdict: found
- Exact result: Across 430 src_sys_crt_dts_month partitions the row counts range from a minimum of 1 row to a maximum of 10,003,571 rows. The overall average per partition is ~1,552,600 rows. The top few partitions (e.g., months 621, 626, 611) each contain ~9–10 M rows, while many partitions sit in the 6–9 M range. A handful of partitions have extremely low counts (as low as 1 row), indicating notable skew between the largest and smallest partitions.
- Rationale: The query returns min_rows = 1, max_rows = 10,003,571, avg_rows ≈ 1.55 M for 430 partitions, with the highest‑count partitions listed first and many mid‑range counts, showing a wide spread.
- Recommendation: Investigate the partitions with very low row counts to understand if they represent valid sparse data or missing data. Consider rebalancing or adjusting the partitioning strategy if the skew impacts query performance.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 2: Does the table define a sort order, and if so, how well does that sort order align with the most common query predicates (e.g., filters on src_sys_crt_dts_month or other columns) to improve scan efficiency?
- Verdict: inconclusive
- Exact result: The only information retrieved is that the table has a column `sort_order_id` with a single distinct value of 0. No metadata about defined sort keys or clustering is available.
- Rationale: Without schema or table metadata indicating a defined sort order (e.g., clustering columns), we cannot determine whether the table is sorted on `src_sys_crt_dts_month` or any other column, nor assess alignment with common query predicates.
- Recommendation: Inspect the table definition or catalog metadata (e.g., DESCRIBE TABLE, SHOW CREATE TABLE) to identify any clustering or sort order specifications. Then compare those columns to the most frequent filter predicates to evaluate scan efficiency.
- Evidence IDs: ['trail:2']
- Validation: valid

## Knowledge References Consulted

- None
