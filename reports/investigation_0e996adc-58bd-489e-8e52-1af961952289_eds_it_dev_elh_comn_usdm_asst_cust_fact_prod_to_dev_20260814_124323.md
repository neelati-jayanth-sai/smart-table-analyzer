# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 2
- Validated findings: 2
- Hook violations: 0
- Total queries: 5

## Investigation Metadata
- Investigation ID: 21
- Run ID: 0e996adc-58bd-489e-8e52-1af961952289
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 12:43:01
- Completed: 2026-08-14 12:43:23

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
### Finding 0: Given the low score in 'scan_efficiency' and 'sort_order', what is the current partitioning scheme of the table, and how does it align with common query access patterns?
- Verdict: could_not_verify
- Exact result: error
- Rationale: No analysis available
- Recommendation: N/A
- Evidence IDs: ['trail:0', 'knowledge:iceberg/partition-transforms@0a94cba344a6', 'knowledge:iceberg/sort-order-optimization@42de3a77462c', 'knowledge:iceberg/table-properties-reference@9e0ad176bc79']
- Validation: valid

### Finding 1: What is the current partitioning scheme of the table, and how does it align with common query access patterns?
- Verdict: found
- Exact result: The current partitioning scheme is defined by the partition column `SRC_SYS_CRT_DTS_month`, which has a value of -10382. The provided knowledge base describes Iceberg Partition Transforms, which define how source column values are converted into partition values, but it does not detail how this specific partition scheme aligns with common query access patterns.
- Rationale: The query result explicitly shows the partition column and its value. The knowledge base explains partition transforms but not query pattern alignment.
- Recommendation: To fully answer the question, information regarding common query access patterns and how they interact with this specific time-based partitioning scheme is needed.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

## Knowledge References Consulted

- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-14 12:43:05)
- `iceberg/sort-order-optimization@42de3a77462c` (fetched 2026-08-14 12:43:05)
- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-14 12:43:05)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-14 12:43:17)
- `iceberg/README@663671d96fdc` (fetched 2026-08-14 12:43:17)
