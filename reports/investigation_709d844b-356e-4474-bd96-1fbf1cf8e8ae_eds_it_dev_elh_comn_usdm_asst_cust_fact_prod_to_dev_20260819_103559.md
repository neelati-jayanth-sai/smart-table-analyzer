# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 6

## Investigation Metadata
- Investigation ID: 54
- Run ID: 709d844b-356e-4474-bd96-1fbf1cf8e8ae
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 10:29:17
- Completed: 2026-08-19 10:35:59

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
- Exact result: No CAPS issues; No deprecated properties
- Rationale: The table configuration report shows both caps_status and deprecated_status as negative, indicating no problems.
- Recommendation: No action required; the table configuration is clean.
- Evidence IDs: ['trail:0', 'knowledge:iceberg/table-properties-reference@9e0ad176bc79']
- Validation: valid

### Finding 1: Which columns have high cardinality and could be good partition candidates?
- Verdict: found
- Exact result: SRC_CUST_PROD_ID, ASST_ID, SVC_TAG_ID
- Rationale: All three columns are identifier fields (customer‑product, asset, service‑tag) that typically contain many distinct values, i.e., high cardinality, making them strong partition candidates.
- Recommendation: Consider identity partitioning on SRC_CUST_PROD_ID, ASST_ID, or SVC_TAG_ID (or a combination) to improve query pruning.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: What are the recommended partition columns based on column analysis?
- Verdict: found
- Exact result: {"row_count": 10, "schema": ["column_name", "distinct_cnt"], "rows": [{"column_name": "DW_SRC_SITE_ID", "distinct_cnt": 1}, {"column_name": "DW_ETL_SESS_NM", "distinct_cnt": 1}, {"column_name": "CURR_FLG", "distinct_cnt": 1}]}
- Rationale: All analyzed columns have a distinct count of 1, indicating very low cardinality; such columns are poor partition candidates.
- Recommendation: No partition columns are recommended based on the analysis; none of the columns provide sufficient cardinality for effective partitioning.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

## Knowledge References Consulted

- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-19 10:29:23)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 10:29:37)
