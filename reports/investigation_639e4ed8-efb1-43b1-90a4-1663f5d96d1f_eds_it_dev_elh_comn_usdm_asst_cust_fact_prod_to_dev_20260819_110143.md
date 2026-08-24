# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 5

## Investigation Metadata
- Investigation ID: 56
- Run ID: 639e4ed8-efb1-43b1-90a4-1663f5d96d1f
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 10:57:21
- Completed: 2026-08-19 11:01:43

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
- Exact result: No CAPS issues
- Rationale: The query result explicitly states there are no CAPS issues, and no deprecated properties were reported.
- Recommendation: No action needed regarding CAPS or deprecated properties.
- Evidence IDs: ['trail:0', 'knowledge:iceberg/table-properties-reference@9e0ad176bc79']
- Validation: valid

### Finding 1: Which columns have high cardinality and could be good partition candidates?
- Verdict: found
- Exact result: SRC_CUST_PROD_ID, ASST_ID, SVC_TAG_ID
- Rationale: All three columns are unique identifiers, giving them high cardinality and making them strong partition candidates.
- Recommendation: Consider partitioning on SRC_CUST_PROD_ID, ASST_ID, or SVC_TAG_ID using identity transforms.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: What are the recommended partition columns based on column analysis?
- Verdict: found
- Exact result: ORIG_SRC_SITE_ID, MFRR_ID, MFRR_NM
- Rationale: Column analysis returned three recommended partition columns.
- Recommendation: Use ORIG_SRC_SITE_ID, MFRR_ID, and MFRR_NM as partition columns.
- Evidence IDs: ['knowledge:runbooks/partition-strategy-guidelines@a760581385e4']
- Validation: valid

## Knowledge References Consulted

- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-19 10:57:27)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 10:57:37)
- `runbooks/partition-strategy-guidelines@a760581385e4` (fetched 2026-08-19 11:01:35)
