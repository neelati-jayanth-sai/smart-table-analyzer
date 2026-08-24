# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 6

## Investigation Metadata
- Investigation ID: 55
- Run ID: 83e8be9a-de8b-4c8f-b2df-5d93a97ec04c
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 10:44:54
- Completed: 2026-08-19 10:49:33

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
- Exact result: No CAPS issues or deprecated properties detected in the listed table properties.
- Rationale: All property names are lower‑case as required and correspond to active Iceberg settings (commit.retry.* and current-snapshot-id) with no deprecation noted.
- Recommendation: No changes needed; the table configuration is valid.
- Evidence IDs: ['knowledge:iceberg/table-properties-reference@9e0ad176bc79']
- Validation: valid

### Finding 1: Which columns have high cardinality and could be good partition candidates?
- Verdict: found
- Exact result: SRC_CUST_PROD_ID, ASST_ID, SVC_TAG_ID
- Rationale: All three columns are identifier fields, typically high‑cardinality and suitable for identity partitioning in Iceberg.
- Recommendation: Use identity partition transforms on SRC_CUST_PROD_ID, ASST_ID, and SVC_TAG_ID as potential partition columns.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: What are the recommended partition columns based on column analysis?
- Verdict: found
- Exact result: ORIG_SRC_SITE_ID, MFRR_ID, MFRR_NM
- Rationale: IDs are typically high‑cardinality and stable, making them ideal partition keys; names often have lower cardinality and are less suitable.
- Recommendation: Use ORIG_SRC_SITE_ID and MFRR_ID as partition columns (optionally add MFRR_NM if query patterns frequently filter on it).
- Evidence IDs: ['knowledge:runbooks/partition-strategy-guidelines@a760581385e4']
- Validation: valid

## Knowledge References Consulted

- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-19 10:45:00)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 10:45:13)
- `runbooks/partition-strategy-guidelines@a760581385e4` (fetched 2026-08-19 10:49:19)
