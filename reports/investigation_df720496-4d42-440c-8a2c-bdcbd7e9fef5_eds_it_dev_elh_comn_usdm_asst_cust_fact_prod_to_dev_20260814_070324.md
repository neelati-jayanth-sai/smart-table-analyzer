# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 4

## Investigation Metadata
- Investigation ID: 14
- Run ID: df720496-4d42-440c-8a2c-bdcbd7e9fef5
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 07:02:37
- Completed: 2026-08-14 07:03:24

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
### Finding 0: Is the data evenly distributed across the 430 partitions, or are there partitions that contain significantly more rows or data size than others?
- Verdict: found
- Exact result: Across 430 partitions, rows per partition range from 1 to 10,003,571 (average ≈1,552,600). Data size per partition ranges from 11 KB to 453 MB (average ≈71 MB).
- Rationale: The min and max values are orders of magnitude apart, showing a highly uneven distribution of rows and bytes across partitions.
- Recommendation: Consider rebalancing or repartitioning to avoid hotspots and improve query performance.
- Evidence IDs: ['trail:0']
- Validation: valid

### Finding 1: Do any partitions contain a disproportionately large number of data files or a high proportion of very small files, indicating file‑size skew that could affect scan efficiency?
- Verdict: not_found
- Exact result: All 20 sampled partitions have file_count = 1. Only a few partitions contain a single very small file (<1 MiB), but none have a large number of files or a high proportion of small files.
- Rationale: Since every partition reports exactly one file, there is no evidence of partitions with many files or a mix of many small files that would cause file‑size skew.
- Recommendation: No immediate action needed for file‑size skew. If small‑file partitions are undesirable, consider consolidating them during future loads.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 2: Is the table defined with a sort order on any columns, and if so, does the current sort order match the most frequent query predicates or join keys, or could a different sort order improve scan efficiency?
- Verdict: found
- Exact result: sort_order_id = 0 (no sort order defined)
- Rationale: The distinct query returned a single row with sort_order_id = 0, indicating the table has no defined sort order. Without a sort order, scans cannot benefit from ordering that matches frequent predicates or join keys, so a different sort order could improve efficiency.
- Recommendation: Analyze the most common query predicates and join keys on this table and consider defining a sort order (e.g., clustering or Z‑ordering) on those columns to enable more efficient range scans and predicate push‑down.
- Evidence IDs: ['trail:2']
- Validation: valid

## Knowledge References Consulted

- None
