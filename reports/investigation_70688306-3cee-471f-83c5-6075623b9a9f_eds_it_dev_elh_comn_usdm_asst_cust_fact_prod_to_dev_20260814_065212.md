# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 1
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 10
- Run ID: 70688306-3cee-471f-83c5-6075623b9a9f
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 06:51:32
- Completed: 2026-08-14 06:52:12

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
### Finding 0: Is there significant size skew among the 430 partitions, i.e., do some partitions contain disproportionately large or small data files compared to the average?
- Verdict: found
- Exact result: Among 430 partitions, average size is 71,135,037 bytes, minimum 11,321 bytes, maximum 453,211,739 bytes. The largest partition is ~6.4× the average, while the average is ~6,283× the smallest.
- Rationale: The max‑to‑avg ratio of 6.37 and avg‑to‑min ratio of 6,283 indicate a few partitions are far larger and many are far smaller than typical, showing strong size skew.
- Recommendation: Investigate partitioning strategy and consider rebalancing or consolidating very small partitions to improve data distribution and query performance.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 1: What is the distribution of data file sizes across the 430 partitions—specifically, how many partitions contain many very small files versus a few large files?
- Verdict: found
- Exact result: Out of the 430 partitions, 221 (≈51%) have very small average file sizes (<10 MB), 122 (≈28%) have small average file sizes (10–100 MB), and 87 (≈20%) have large average file sizes (≥100 MB). This shows that the majority of partitions contain many very small files, while a smaller subset contains a few larger files.
- Rationale: The query grouped partitions by average file size and returned counts: 221 partitions in the ‘very small avg file (<10 MB)’ bucket, 122 in the ‘small avg file (10–100 MB)’ bucket, and 87 in the ‘large avg file (≥100 MB)’ bucket.
- Recommendation: Consider consolidating the 221 partitions with very small files to reduce file‑system overhead and improve query performance.
- Evidence IDs: []
- Validation: INVALID
  - Errors: ['Finding has no evidence IDs']

### Finding 2: What is the average number of data files per partition, and how does the file count distribution vary across the 430 partitions (e.g., min, max, median, and standard deviation of files per partition)?
- Verdict: found
- Exact result: Average files per partition: 1.0; Min: 1; Max: 1; Median: 1.0; Standard deviation: 0.0
- Rationale: The query returned avg_files_per_partition=1.0, min_files_per_partition=1, max_files_per_partition=1, median_files_per_partition=1.0, and stddev_files_per_partition=0.0, directly answering the question.
- Recommendation: No further analysis needed; the file count is uniform across all 430 partitions.
- Evidence IDs: []
- Validation: INVALID
  - Errors: ['Finding has no evidence IDs']

## Knowledge References Consulted

- None
