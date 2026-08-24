# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 1
- Total queries: 4

## Investigation Metadata
- Investigation ID: 52
- Run ID: 91faf5e5-c12c-490c-84fb-cb478445e2cf
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 10:08:32
- Completed: 2026-08-19 10:09:25

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
### Finding 0: Are there any CAPS issues or deprecated properties in the table configuration?
- Verdict: not_found
- Exact result: has_caps_issues: false, caps_warnings: ""
- Rationale: The query result explicitly indicates no CAPS issues and no warnings, confirming the table configuration lacks deprecated or problematic properties.
- Recommendation: No action needed regarding CAPS; continue monitoring for future property changes.
- Evidence IDs: ['trail:0', 'knowledge:iceberg/table-properties-reference@9e0ad176bc79']
- Validation: valid

### Finding 1: Which columns have high cardinality and could be good partition candidates?
- Verdict: found
- Exact result: SRC_CUST_PROD_ID, ASST_ID, SVC_TAG_ID
- Rationale: All three columns are identifier‑type fields that typically contain many distinct values, giving them high cardinality and making them strong partition candidates.
- Recommendation: Consider using identity partition transforms on SRC_CUST_PROD_ID, ASST_ID, or SVC_TAG_ID (or a composite of them) to improve query pruning.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: What are the recommended partition columns based on column analysis?
- Verdict: found
- Exact result: SRC_SYS_CRT_DTS_month
- Rationale: Column analysis shows SRC_SYS_CRT_DTS_month has high cardinality and is the only candidate returned, making it the best partition column.
- Recommendation: Partition on SRC_SYS_CRT_DTS_month using an appropriate transform (e.g., month) for optimal query pruning.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

## Knowledge References Consulted

- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-19 10:08:38)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 10:08:59)
