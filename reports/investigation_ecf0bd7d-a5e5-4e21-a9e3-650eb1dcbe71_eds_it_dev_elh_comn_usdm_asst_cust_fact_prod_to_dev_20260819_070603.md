# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 44
- Run ID: ecf0bd7d-a5e5-4e21-a9e3-650eb1dcbe71
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 07:05:27
- Completed: 2026-08-19 07:06:03

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
### Finding 0: Are the 430 partitions evenly sized and aligned with the most common query predicates to avoid data skew and improve pruning?
- Verdict: found
- Exact result: 430 partitions (distinct=430) with record counts ranging from 1 to 10,003,571 (avg≈1.55M) and sizes from 11 KB to 453 MB (avg≈71 MB).
- Rationale: The wide range in record counts and partition sizes indicates significant imbalance; partitions are not evenly sized nor likely aligned with common query predicates, which can cause data skew and reduce pruning effectiveness.
- Recommendation: Reevaluate partitioning strategy: use Iceberg partition transforms (e.g., bucket, truncate, day) aligned with frequent query filters to create more uniform partition sizes and improve pruning.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 1: What is the distribution of data file sizes across the 430 partitions, and are there many small or overly large files that could cause read skew or performance overhead?
- Verdict: found
- Exact result: Across the 430 partitions there are 430 data files. The smallest file is 11 KB, the largest is 432 MB, and the average size is ~68 MB. 341 files are classified as small and none are classified as large.
- Rationale: The query shows a high proportion (≈79%) of files are small (below Iceberg’s recommended 128 MB–1 GB range) and no files exceed the large‑file threshold, indicating potential read‑skew and metadata overhead.
- Recommendation: Consolidate the many small files (e.g., via Iceberg’s rewrite‑data‑files or Spark/Databricks OPTIMIZE) to target 256‑512 MB per file. This will reduce file‑open costs, improve scan efficiency, and balance read distribution across partitions.
- Evidence IDs: ['knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

### Finding 2: Is the table sorted on columns that are frequently used in range or equality predicates (e.g., date, customer_id) to enable efficient data pruning and reduce scan overhead?
- Verdict: not_found
- Exact result: sort_order_id = 0 indicates the table has no defined sort order.
- Rationale: Without a sort order, rows are not clustered on range/equality columns, so pruning is limited.
- Recommendation: Define a sort order on frequently filtered columns such as date and customer_id to improve pruning and scan efficiency.
- Evidence IDs: ['knowledge:iceberg/sort-order-optimization@42de3a77462c']
- Validation: valid

## Knowledge References Consulted

- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 07:05:32)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-19 07:05:44)
- `iceberg/sort-order-optimization@42de3a77462c` (fetched 2026-08-19 07:05:58)
