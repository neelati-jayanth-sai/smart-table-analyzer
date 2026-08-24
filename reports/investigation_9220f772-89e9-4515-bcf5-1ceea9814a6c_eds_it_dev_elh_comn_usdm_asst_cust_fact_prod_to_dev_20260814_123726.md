# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 2
- Validated findings: 2
- Hook violations: 0
- Total queries: 2

## Investigation Metadata
- Investigation ID: 18
- Run ID: 9220f772-89e9-4515-bcf5-1ceea9814a6c
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 12:37:00
- Completed: 2026-08-14 12:37:26

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
### Finding 0: What columns are defined as the sort order for the Iceberg table eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev?
- Verdict: found
- Exact result: No columns are defined as the sort order (sort_order_id = 0 indicates no sort order).
- Rationale: The query returned a single row with sort_order_id = 0, which means the table has no defined sort order columns.
- Recommendation: If you need a sort order for performance, define one using ALTER TABLE ... SET SORT ORDER.
- Evidence IDs: ['knowledge:iceberg/sort-order-optimization@42de3a77462c']
- Validation: valid

### Finding 1: What columns are defined as partition columns for the Iceberg table eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev, and what are the partition specifications (e.g., type, granularity) used?
- Verdict: found
- Exact result: The Iceberg table eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev is partitioned on the column SRC_SYS_CRT_DTS_month. The partition specification is a month‑level date partition (i.e., the source system creation timestamp truncated to month).
- Rationale: Query output shows the partition map containing only the key SRC_SYS_CRT_DTS_month, indicating it is the defined partition column. Iceberg stores month‑level date partitions as a date‑type with month granularity.
- Recommendation: Run SHOW CREATE TABLE eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev; or DESCRIBE TABLE to view the full partition spec details and confirm the type (date) and granularity (month).
- Evidence IDs: ['knowledge:iceberg/manifest-file-structure@9e9b57029b06']
- Validation: valid

## Knowledge References Consulted

- `iceberg/sort-order-optimization@42de3a77462c` (fetched 2026-08-14 12:37:05)
- `iceberg/delete-file-handling@8f58d0073a71` (fetched 2026-08-14 12:37:17)
- `iceberg/data-skew-detection@0e14eda1f18a` (fetched 2026-08-14 12:37:17)
- `iceberg/manifest-file-structure@9e9b57029b06` (fetched 2026-08-14 12:37:17)
