# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 6

## Investigation Metadata
- Investigation ID: 58
- Run ID: 8f7c9f38-f8db-49c8-b560-9ceecdf09c6e
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 11:47:11
- Completed: 2026-08-19 11:52:31

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
- Exact result: No CAPS issues and no deprecated properties
- Rationale: The table status explicitly reports no CAPS naming problems and no use of deprecated Iceberg properties.
- Recommendation: No action needed; continue monitoring for future property changes.
- Evidence IDs: ['trail:0', 'knowledge:iceberg/table-properties-reference@9e0ad176bc79']
- Validation: valid

### Finding 1: Which columns have high cardinality and could be good partition candidates?
- Verdict: found
- Exact result: SRC_CUST_PROD_ID, ASST_ID, SVC_TAG_ID
- Rationale: All three columns are identifier fields (customer‑product, asset, service‑tag) and typically have many distinct values, making them high‑cardinality and strong partition candidates.
- Recommendation: Consider partitioning on SRC_CUST_PROD_ID, ASST_ID, and/or SVC_TAG_ID using identity transforms to improve query pruning.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: What are the recommended partition columns based on column analysis?
- Verdict: found
- Exact result: SRC_SYS_CRT_DTS, ORIG_SRC_SITE_ID, MFRR_ID
- Rationale: Guidelines advise using a timestamp column for time‑based partitioning; SRC_SYS_CRT_DTS fits this. Categorical IDs (ORIG_SRC_SITE_ID, MFRR_ID) can be added as secondary partitions if queries filter on them.
- Recommendation: Primary partition on SRC_SYS_CRT_DTS (day granularity). Consider adding ORIG_SRC_SITE_ID or MFRR_ID as secondary partition columns based on query filters.
- Evidence IDs: ['knowledge:runbooks/partition-strategy-guidelines@a760581385e4']
- Validation: valid

## Knowledge References Consulted

- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-19 11:47:17)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 11:47:29)
- `runbooks/partition-strategy-guidelines@a760581385e4` (fetched 2026-08-19 11:51:58)
