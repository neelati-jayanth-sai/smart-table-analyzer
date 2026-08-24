# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 2
- Validated findings: 2
- Hook violations: 0
- Total queries: 2

## Investigation Metadata
- Investigation ID: 23
- Run ID: 12ac033a-3f32-452a-9b7e-fe7fb8588da9
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 12:49:23
- Completed: 2026-08-14 12:49:48

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
### Finding 0: Which columns are defined as the sort order for the Iceberg table eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev?
- Verdict: not_found
- Exact result: 
- Rationale: The provided query result only contains table statistics (record counts, file sizes, etc.) and does not include any information about the sort order columns for the Iceberg table.
- Recommendation: Run a command that returns table metadata, such as `SHOW CREATE TABLE eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev` or query the Iceberg catalog for the table's sort order property, to retrieve the defined sort order columns.
- Evidence IDs: ['trail:0', 'knowledge:iceberg/sort-order-optimization@42de3a77462c']
- Validation: valid

### Finding 1: What columns are defined as partition fields for the Iceberg table eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev?
- Verdict: found
- Exact result: SRC_SYS_CRT_DTS_month
- Rationale: The query on the Iceberg table returned a single column named SRC_SYS_CRT_DTS_month, indicating this column is defined as a partition field for the table.
- Recommendation: Use SRC_SYS_CRT_DTS_month when filtering or writing data to this Iceberg table to take advantage of partition pruning.
- Evidence IDs: ['trail:1', 'knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

## Knowledge References Consulted

- `iceberg/sort-order-optimization@42de3a77462c` (fetched 2026-08-14 12:49:28)
- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-14 12:49:40)
