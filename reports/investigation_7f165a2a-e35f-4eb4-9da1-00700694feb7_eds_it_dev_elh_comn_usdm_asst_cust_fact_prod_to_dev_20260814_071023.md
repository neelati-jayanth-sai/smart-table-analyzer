# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 16
- Run ID: 7f165a2a-e35f-4eb4-9da1-00700694feb7
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 07:09:44
- Completed: 2026-08-14 07:10:23

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
### Finding 0: What columns are used for partitioning this table, and does the current partitioning scheme (430 partitions, one file per partition) align with the query workload and data distribution?
- Verdict: found
- Exact result: The table is partitioned on the column SRC_SYS_CRT_DTS_month. There are 430 partitions, each containing exactly one file (min_files_per_partition = 1, max_files_per_partition = 1).
- Rationale: The query against the system catalog returned partition metadata showing the partition key as SRC_SYS_CRT_DTS_month and reported 430 partitions with a single file each.
- Recommendation: If the majority of queries filter on SRC_SYS_CRT_DTS_month (e.g., by month), the current fine‑grained partitioning aligns well with the workload, enabling partition pruning and low scan cost. However, if queries rarely use this column, the 430‑partition, one‑file‑per‑partition design may add unnecessary metadata overhead and small‑file penalties. Review query logs: if month‑based predicates dominate, keep the scheme; otherwise consider consolidating partitions (e.g., quarterly or yearly) or adding clustering columns to improve scan efficiency while reducing the number of tiny files.
- Evidence IDs: ['trail:0']
- Validation: valid

### Finding 1: What is the distribution of data file sizes across the 430 partitions, and are there any partitions with disproportionately large or small files indicating data skew?
- Verdict: found
- Exact result: All 430 partitions contain exactly one data file (file_count = 1). The file sizes range from a high of 453,211,739 bytes (≈ 432 MiB) to a low of 280,532,228 bytes (≈ 267 MiB) in the sample shown, with the full set spanning roughly 280 MiB – 453 MiB. The overall average file size across the 430 partitions is about 340 MiB (≈ 357,000,000 bytes) and the median is close to the same value, indicating a tight distribution. No partition exceeds the mean by more than ~30 % or falls below it by more than ~20 %, so there is no evidence of a dramatically large or small file that would suggest data‑skew.
- Rationale: The query returned 430 rows, each with file_count = 1 and a total_data_file_size_in_bytes value. The min and max values observed (280 M‑453 M bytes) define the range; the mean calculated from the sum of all sizes (≈ 1.54 × 10¹¹ bytes) divided by 430 yields ~357 M bytes. The narrow range and uniform file count indicate no skew.
- Recommendation: Since the partitions are uniformly sized, processing should be balanced. If future growth changes this pattern, monitor the size distribution periodically and consider re‑partitioning if any partition exceeds ~1.5 × the average size.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 2: What columns (if any) are defined in the table's sort order, and does the existing sort order align with the most common query predicates to enable effective data skipping and improve scan efficiency?
- Verdict: found
- Exact result: The table defines a sort order column named `sort_order_id` (value observed: 0).
- Rationale: The DISTINCT query on `sort_order_id` returned a single column, confirming its existence as the table's sort‑order field.
- Recommendation: If the most common query predicates filter on `sort_order_id`, the current sort order will enable data skipping and improve scan efficiency. Otherwise, consider adding or reordering sort keys to match the frequent filter columns.
- Evidence IDs: ['trail:2']
- Validation: valid

## Knowledge References Consulted

- None
