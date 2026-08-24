# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 45
- Run ID: 4ed2a75b-fec2-4fe3-acf1-4bfe3bbb8abf
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 07:36:09
- Completed: 2026-08-19 07:36:48

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
### Finding 0: Are the 430 partitions of the table evenly distributed in terms of row count and file size, or does significant skew exist among them?
- Verdict: found
- Exact result: 430 partitions: record count min = 1, max = 10,003,571, avg ≈ 1,552,600; file size min ≈ 11 KB, max ≈ 453 MB, avg ≈ 71 MB
- Rationale: The max record count and file size are orders of magnitude larger than the minima and far exceed the average, indicating strong partition and file size skew per Iceberg data‑skew guidelines.
- Recommendation: Re‑evaluate partitioning strategy (e.g., add more granular keys) and enforce target file sizes to reduce skew and improve query parallelism.
- Evidence IDs: ['knowledge:iceberg/data-skew-detection@0e14eda1f18a']
- Validation: valid

### Finding 1: What is the distribution of individual data file sizes in eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev, and does the table contain a high proportion of very small files (e.g., <128 MB) that could degrade read performance?
- Verdict: found
- Exact result: The table has 430 data files: 343 (<128 MB), 26 (128‑256 MB), 61 (256‑512 MB), and 0 (≥512 MB). Approximately 80 % of files are smaller than 128 MB.
- Rationale: Query shows a dominant share of sub‑128 MB files, which exceeds recommended minimums and can increase scan overhead. Iceberg best‑practice advises most files be 128 MB–1 GB, ideally 256‑512 MB for optimal read performance.
- Recommendation: Consider compacting the 343 small files into larger ones (target 256‑512 MB) via rewrite or merge operations. This will reduce file‑open costs and improve query latency.
- Evidence IDs: ['knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

### Finding 2: What is the current delete file count and total size relative to data files in eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev, and does this indicate significant delete overhead that could degrade query performance?
- Verdict: found
- Exact result: Delete file count: 0, Delete file size: 0 bytes (0 % of data file size ~30.6 GB).
- Rationale: The query shows no delete files; Iceberg docs state delete files add read overhead only when present, so zero deletes imply no performance impact.
- Recommendation: No immediate action needed; monitor for future delete file accumulation.
- Evidence IDs: ['knowledge:iceberg/delete-file-handling@8f58d0073a71']
- Validation: valid

## Knowledge References Consulted

- `iceberg/data-skew-detection@0e14eda1f18a` (fetched 2026-08-19 07:36:14)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-19 07:36:26)
- `iceberg/delete-file-handling@8f58d0073a71` (fetched 2026-08-19 07:36:42)
