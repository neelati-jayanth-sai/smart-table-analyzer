# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 5

## Investigation Metadata
- Investigation ID: 53
- Run ID: 5e870b64-966f-4868-9722-2f512995f797
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 10:16:38
- Completed: 2026-08-19 10:22:07

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
- Exact result: No CAPS issues or deprecated properties
- Rationale: The query result explicitly states there are no CAPS issues or deprecated properties in the table configuration.
- Recommendation: No action needed regarding CAPS or deprecated properties.
- Evidence IDs: ['trail:0', 'knowledge:iceberg/table-properties-reference@9e0ad176bc79']
- Validation: valid

### Finding 1: Which columns have high cardinality and could be good partition candidates?
- Verdict: found
- Exact result: SRC_CUST_PROD_ID, ASST_ID, SVC_TAG_ID
- Rationale: All three columns are listed as distinct identifiers, indicating high cardinality and suitability for partitioning.
- Recommendation: Consider using identity partition transforms on SRC_CUST_PROD_ID, ASST_ID, and SVC_TAG_ID for efficient pruning.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: What are the recommended partition columns based on column analysis?
- Verdict: found
- Exact result: ORIG_SRC_SITE_ID (5 distinct, 0 nulls), MFRR_ID (56 distinct, 0 nulls), MFRR_NM (56 distinct, 0 nulls)
- Rationale: Low‑cardinality columns are preferred for partitioning. ORIG_SRC_SITE_ID has only 5 distinct values and no nulls, making it the optimal partition column; the 56‑value columns are higher‑cardinality and less ideal.
- Recommendation: Partition on ORIG_SRC_SITE_ID. If further pruning is needed, consider a secondary partition on MFRR_ID (or MFRR_NM) in a multi‑column scheme.
- Evidence IDs: ['knowledge:runbooks/partition-strategy-guidelines@a760581385e4']
- Validation: valid

## Knowledge References Consulted

- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-19 10:16:45)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 10:16:56)
- `runbooks/partition-strategy-guidelines@a760581385e4` (fetched 2026-08-19 10:21:33)
