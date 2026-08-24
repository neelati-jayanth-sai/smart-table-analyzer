# Investigation Report: eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 4
- Total queries: 7

## Investigation Metadata
- Investigation ID: 35
- Run ID: 83aa259d-c847-4599-ab23-31552302c0df
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-18 10:13:38
- Completed: 2026-08-18 10:14:41

## Baseline Score
- Overall: 79.56
- Dimensions:
  - file_size: 100.0
  - scan_efficiency: 50.0
  - delete_overhead: 100.0
  - manifest_organization: 97.39
  - partition_aware: 80.0
  - sort_order: 50.0
  - row_count: 722105849
  - num_data_files: 261
  - total_data_file_bytes: 51355373891
  - partition_count: 40
  - snapshot_count: 3
  - is_empty: False
  - catalog_score: 50.0
  - downstream_count: 0
  - upstream_count: 0
  - has_catalog_context: False

## Findings
### Finding 0: Are the 40 partitions of eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit evenly distributed in terms of row count and file size, or is there significant skew among them?
- Verdict: found
- Exact result: Across the 40 partitions, row counts range from 5,312,488 to 27,147,271 (≈5× difference) with an average of 18,052,646 rows. File sizes range from 352,588,952 bytes to 1,920,425,559 bytes (≈5.4× difference) with an average of 1,283,884,347 bytes.
- Rationale: The max values are roughly five times the min values for both rows and bytes, indicating notable partition and file size skew rather than an even distribution.
- Recommendation: Investigate repartitioning or reclustering the table (e.g., by adding more granular partition keys or using Iceberg’s rewrite‑data-files) to balance row and size distribution and improve query performance.
- Evidence IDs: ['knowledge:iceberg/data-skew-detection@0e14eda1f18a']
- Validation: valid

### Finding 1: What is the distribution of individual file sizes across eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit, and are there a significant number of small files (e.g., <128 MB) that could impact query performance?
- Verdict: found
- Exact result: File size distribution for eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit:
- 128‑256 MB: 239 files (≈49 GB)
- 256‑512 MB: 2 files (≈0.5 GB)
- <128 MB: 20 files (≈1.8 GB)
Total files: 261, total size ≈51.5 GB.
- Rationale: The query shows only 20 small files (<128 MB), representing ~7.6% of files and ~3.5% of data volume, which is below the threshold where small‑file overhead typically degrades performance.
- Recommendation: Small‑file count is low; no immediate action needed. Continue monitoring and consider consolidating the 20 small files during routine compaction to keep file sizes within the recommended 128 MB‑1 GB range.
- Evidence IDs: ['knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

### Finding 2: What is the current manifest organization for eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit (e.g., total number of manifest files, manifest list size, and average entries per manifest), and does it follow best‑practice thresholds to avoid manifest overhead?
- Verdict: found
- Exact result: total_manifest_files=3, manifest_list_size=3, avg_entries_per_manifest=87.0
- Rationale: Iceberg best‑practice suggests keeping manifest files large enough (typically >10 k entries) and the manifest list small (<~100 entries) to minimise planning overhead. While the manifest list size (3) is fine, the average of only 87 entries per manifest is far below the recommended threshold, indicating potential manifest‑overhead.
- Recommendation: Consolidate the three small manifests (e.g., via REWRITE MANIFESTS) to produce fewer, larger manifest files with tens of thousands of entries each, reducing planning cost and adhering to best‑practice thresholds.
- Evidence IDs: ['knowledge:iceberg/manifest-file-structure@9e9b57029b06']
- Validation: valid

## Knowledge References Consulted

- `iceberg/data-skew-detection@0e14eda1f18a` (fetched 2026-08-18 10:13:43)
- `iceberg/delete-file-handling@8f58d0073a71` (fetched 2026-08-18 10:13:54)
- `iceberg/manifest-file-structure@9e9b57029b06` (fetched 2026-08-18 10:13:54)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-18 10:13:54)
- `iceberg/manifest-file-structure@9e9b57029b06` (fetched 2026-08-18 10:14:16)
