# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 1
- Total queries: 7

## Investigation Metadata
- Investigation ID: 57
- Run ID: d302f5ca-c9ce-42b8-91c2-ac635a8af72f
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 11:10:17
- Completed: 2026-08-19 11:39:28

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
- Rationale: All three columns are identifier fields, typically high‑cardinality and thus suitable for partitioning in Iceberg.
- Recommendation: Consider using SRC_CUST_PROD_ID, ASST_ID, or SVC_TAG_ID (or a combination) as partition columns with identity transform.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: What are the recommended partition columns based on column analysis?
- Verdict: found
- Exact result: Recommended partition columns: src_sys_crt_dts_day_card (day), eff_strt_utc_dt_card (date), asst_shipd_utc_dt_card (date)
- Rationale: These columns have the highest distinct counts (≈12k) and represent dates, matching the guideline to prefer time‑based partitions for high‑cardinality date fields.
- Recommendation: Use src_sys_crt_dts_day_card as the primary partition (day granularity). If query patterns also filter on effective start or shipped dates, add eff_strt_utc_dt_card or asst_shipd_utc_dt_card as secondary partitions.
- Evidence IDs: ['knowledge:runbooks/partition-strategy-guidelines@a760581385e4']
- Validation: valid

## Knowledge References Consulted

- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-19 11:10:23)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 11:10:35)
- `runbooks/partition-strategy-guidelines@a760581385e4` (fetched 2026-08-19 11:37:57)
