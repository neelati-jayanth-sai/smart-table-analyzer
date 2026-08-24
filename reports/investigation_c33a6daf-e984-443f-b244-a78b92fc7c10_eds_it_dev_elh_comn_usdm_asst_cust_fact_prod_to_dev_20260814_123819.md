# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 2
- Validated findings: 2
- Hook violations: 7
- Total queries: 7

## Investigation Metadata
- Investigation ID: 19
- Run ID: c33a6daf-e984-443f-b244-a78b92fc7c10
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 12:37:56
- Completed: 2026-08-14 12:38:19

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
### Finding 0: ```json
{
  "question": "Given the low score in 'scan_efficiency' and 'sort_order', what is the current partitioning scheme of the table, and how does it align with common query patterns?",
  "check_type": "partitioning"
}
```?
- Verdict: could_not_verify
- Exact result: hook_failed
- Rationale: No analysis available
- Recommendation: N/A
- Evidence IDs: ['trail:0', 'knowledge:iceberg/partition-transforms@0a94cba344a6', 'knowledge:iceberg/sort-order-optimization@42de3a77462c', 'knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

### Finding 1: ```json
{
  "question": "What is the current partitioning scheme of the table, and how does it align with common query patterns, especially considering the low 'scan_efficiency' and 'sort_order' scores?",
  "check_type": "partitioning"
}
```?
- Verdict: could_not_verify
- Exact result: hook_failed
- Rationale: No analysis available
- Recommendation: N/A
- Evidence IDs: ['trail:1', 'knowledge:iceberg/partition-transforms@0a94cba344a6', 'knowledge:iceberg/sort-order-optimization@42de3a77462c', 'knowledge:iceberg/table-properties-reference@9e0ad176bc79']
- Validation: valid

## Knowledge References Consulted

- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-14 12:38:01)
- `iceberg/sort-order-optimization@42de3a77462c` (fetched 2026-08-14 12:38:01)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-14 12:38:01)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-14 12:38:13)
- `iceberg/sort-order-optimization@42de3a77462c` (fetched 2026-08-14 12:38:13)
- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-14 12:38:13)
