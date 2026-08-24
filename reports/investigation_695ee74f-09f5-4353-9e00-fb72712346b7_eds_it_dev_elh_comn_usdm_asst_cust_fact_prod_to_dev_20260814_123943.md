# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 2
- Validated findings: 2
- Hook violations: 0
- Total queries: 2

## Investigation Metadata
- Investigation ID: 20
- Run ID: 695ee74f-09f5-4353-9e00-fb72712346b7
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 12:39:15
- Completed: 2026-08-14 12:39:42

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
- Rationale: The provided table summary includes record counts, file sizes, and partition changes but does not list any sort‑order definition. Without a DESCRIBE or SHOW CREATE output that includes a SORT BY clause, the sort‑order columns cannot be identified.
- Recommendation: Run a DESCRIBE TABLE or SHOW CREATE TABLE command for eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev to view its sort‑order definition.
- Evidence IDs: ['knowledge:iceberg/sort-order-optimization@42de3a77462c']
- Validation: valid

### Finding 1: What is the distribution of data file sizes (e.g., number of files in size ranges such as <128 MB, 128‑256 MB, >256 MB) for the Iceberg table eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev?
- Verdict: found
- Exact result: 343 files <128 MB, 26 files 128‑256 MB, 61 files >256 MB
- Rationale: The query returned counts for each size bucket matching the requested distribution.
- Recommendation: Consider consolidating very small (<128 MB) and very large (>256 MB) files to keep most files in the 128‑256 MB range for better Iceberg performance.
- Evidence IDs: ['trail:1', 'knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

## Knowledge References Consulted

- `iceberg/sort-order-optimization@42de3a77462c` (fetched 2026-08-14 12:39:20)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-14 12:39:34)
