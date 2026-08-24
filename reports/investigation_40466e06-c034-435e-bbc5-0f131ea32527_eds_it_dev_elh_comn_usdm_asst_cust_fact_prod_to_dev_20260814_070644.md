# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 15
- Run ID: 40466e06-c034-435e-bbc5-0f131ea32527
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-14 07:06:03
- Completed: 2026-08-14 07:06:44

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
### Finding 0: Are the 430 partitions evenly sized, or is there significant data skew across partitions that could affect query performance?
- Verdict: found
- Exact result: 430 partitions; records per partition range from 1 to 10,003,571 (avg ≈1.55 M); size per partition ranges from 11 KB to 453 MB (avg ≈71 MB).
- Rationale: The min‑max gap (1 vs 10 M records, 11 KB vs 453 MB) is orders of magnitude larger than the average, indicating strong data skew that could impact query performance.
- Recommendation: Investigate repartitioning or bucketing to balance data distribution, and consider pruning or clustering strategies to mitigate skew‑related performance issues.
- Evidence IDs: ['trail:0']
- Validation: valid

### Finding 1: What is the distribution of data file sizes across the 430 partitions (e.g., number of files <10 MB, 10‑100 MB, >100 MB), and does the presence of many small files contribute to the low scan efficiency score?
- Verdict: found
- Exact result: Out of 430 files: 221 files (<10 MB), 122 files (10‑100 MB), 87 files (>100 MB).
- Rationale: The query result shows that over half of the files are smaller than 10 MB, which typically leads to higher per‑file overhead and lower scan efficiency.
- Recommendation: Consolidate the 221 small files (e.g., via file compaction or larger batch writes) to reduce file count and improve scan efficiency. Also consider partition pruning and using columnar formats with appropriate file sizing.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 2: How many manifest files are present in the current snapshot, what is the size distribution of those manifests, and are they aggregated into a few large manifests or many small ones that could be impacting scan efficiency?
- Verdict: found
- Exact result: 430 manifest files total ~30.6 GB. Avg size 71 MB, min 11 KB, max 453 MB. 221 files <10 MB, 122 files 10‑100 MB, 87 files >100 MB.
- Rationale: The query returns counts and size stats showing a large number of small manifests (221) alongside medium and large ones, indicating many small files that may hurt scan efficiency.
- Recommendation: Consider consolidating the 221 small manifest files into larger ones (e.g., target size >100 MB) to reduce file count and improve scan performance.
- Evidence IDs: ['trail:2']
- Validation: valid

## Knowledge References Consulted

- None
