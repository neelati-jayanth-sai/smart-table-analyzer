# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 1
- Total queries: 4

## Investigation Metadata
- Investigation ID: 11
- Run ID: 0ad1ade0-a17f-47d1-8f62-c54220a742e9
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 06:54:10
- Completed: 2026-08-14 06:55:03

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
### Finding 0: Is the data evenly distributed across the 430 partitions, or do some partitions contain significantly more rows or data size than others, indicating partition skew?
- Verdict: found
- Exact result: Across 430 partitions, rows range from 1 to 10,003,571 (avg ≈ 1,552,600) and bytes range from 11,321 to 453,211,739 (avg ≈ 71,135,037).
- Rationale: The min‑max gap is orders of magnitude larger than the average, showing strong partition skew.
- Recommendation: Investigate the partitioning key and consider redistributing data or using a more balanced partitioning strategy to avoid performance issues.
- Evidence IDs: ['trail:0']
- Validation: valid

### Finding 1: What is the distribution of data file sizes across the 430 data files, and are there a significant number of small files (e.g., <128 MB) that could be impacting scan efficiency?
- Verdict: found
- Exact result: Out of 430 files, 343 (≈80%) are <128 MB, 26 are 128‑256 MB, 61 are 256‑512 MB, and none >1 GB. Small files (<128 MB) hold ~13 % of total data (4.0 GB of 30.6 GB).
- Rationale: The query returned bucket counts and byte totals showing a heavy skew toward <128 MB files (343 of 430) despite their modest share of total bytes, indicating many small files that can degrade scan efficiency.
- Recommendation: Consider consolidating the 343 small files (e.g., via coalesce/repartition or using a larger file format) to reduce file‑open overhead and improve scan performance.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 2: Do the partitions with the highest row counts or data sizes also contain a disproportionate number of small files (<128 MB), indicating that file‑size skew is concentrated in the largest partitions?
- Verdict: not_found
- Exact result: The top 20 partitions by record count each have a single file (total_files = 1) and zero files under 128 MB (small_files = 0, small_file_pct = 0.0).
- Rationale: All high‑row‑count partitions show no small files, so file‑size skew is not concentrated in the largest partitions.
- Recommendation: Focus investigation on smaller or medium‑sized partitions for file‑size skew, and consider consolidating files in those partitions if needed.
- Evidence IDs: ['trail:1']
- Validation: valid

## Knowledge References Consulted

- None
