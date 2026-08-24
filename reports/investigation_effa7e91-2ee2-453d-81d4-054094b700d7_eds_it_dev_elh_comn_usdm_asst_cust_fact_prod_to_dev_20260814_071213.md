# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 17
- Run ID: effa7e91-2ee2-453d-81d4-054094b700d7
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 07:10:55
- Completed: 2026-08-14 07:12:13

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
### Finding 0: Is there significant size skew among the 430 partitions (i.e., do some partitions contain disproportionately large data files compared to others)?
- Verdict: found
- Exact result: 430 partitions; min size 11,321 bytes, max size 453,211,739 bytes, average size ≈71,135,037 bytes; max/min size ratio ≈40,033
- Rationale: The largest partition is ~453 MB while the smallest is only ~11 KB, giving a size ratio of over 40,000‑to‑1, which indicates strong skew.
- Recommendation: Investigate the partitioning strategy and consider redistributing data or using a more balanced partition key to reduce skew.
- Evidence IDs: ['trail:0']
- Validation: valid

### Finding 1: Does the table have a defined sort order, and if so, does it align with the most common query predicates to improve scan efficiency?
- Verdict: not_found
- Exact result: The table only shows a single distinct sort_order_id value (0) and provides no information about a defined sort order or its alignment with query predicates.
- Rationale: No evidence indicates a defined sort order or its optimization for common predicates; only a column value is present.
- Recommendation: Review table metadata or schema definitions to determine if a sort order is defined and whether it matches frequent query filters.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 2: Do the 430 partitions each correspond to a single data file, or are there partitions that contain multiple small files that could be compacted to improve scan efficiency?
- Verdict: found
- Exact result: All 430 partitions have file_count = 1 (i.e., each partition contains exactly one data file).
- Rationale: The query grouped partitions by file_count and returned a single row: file_count 1 with partition_cnt 430, indicating every partition holds a single file.
- Recommendation: No compaction needed for these partitions, as each already contains only one file.
- Evidence IDs: ['trail:2']
- Validation: valid

## Knowledge References Consulted

- None
