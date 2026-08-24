# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 2
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 50
- Run ID: 648d0ca9-87fa-430b-a21e-2ad24704d1a9
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 09:36:00
- Completed: 2026-08-19 09:36:38

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
### Finding 0: Are the 430 current partitions aligned with typical query patterns, or would consolidating them improve performance and manageability?
- Verdict: inconclusive
- Exact result: 430 partitions, avg 1.55 M records/partition, 1 file per partition, total 667 M records
- Rationale: Quality gate rejection: Finding has inconclusive verdict
- Recommendation: N/A
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 1: Given the 430 partitions and no downstream dependencies, would consolidating partitions (e.g., reducing to a smaller set) improve query performance and manageability for this table?
- Verdict: found
- Exact result: Consolidating the 430 partitions (especially the many tiny ones) would likely improve query performance and manageability.
- Rationale: 430 partitions with a min of 1 record and avg size ~71 MB indicate many small files; reducing partition count lowers metadata overhead and file‑open cost, benefiting scans.
- Recommendation: Repartition the table to eliminate ultra‑small partitions (e.g., target ~100‑200 partitions of ~150 MB each) using a suitable transform; this will streamline maintenance and speed up queries.
- Evidence IDs: ['knowledge:iceberg/partition-transforms@0a94cba344a6']
- Validation: valid

### Finding 2: What is the distribution of file sizes across the 430 partitions (e.g., min, max, median, and average), and are there a significant number of very small files that could be impacting query performance?
- Verdict: found
- Exact result: min=11 321 B, max=453 211 739 B, avg≈71 135 037 B, median≈7 400 708 B, small files=341/430 (≈79%).
- Rationale: The median and average file sizes are far below the Iceberg sweet‑spot (128 MB‑1 GB). Over three‑quarters of files are classified as small, which can cause high metadata overhead and slower scans.
- Recommendation: Rewrite the table to merge small files into target sizes of 256‑512 MB (or at least ≥128 MB). Use write options like `write.target-file-size-bytes=268435456` and enable automatic compaction or Spark’s `coalesce`/`repartition` before write. Monitor file size distribution after compaction to keep the small‑file count low.
- Evidence IDs: ['knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

## Knowledge References Consulted

- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-19 09:36:06)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-19 09:36:30)
