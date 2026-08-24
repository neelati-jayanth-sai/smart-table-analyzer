# Investigation Report: eds_it_dev.elh_comn.sls_opp_ln_snap_wkly_f_vw_avijit

## Summary
- Total findings: 2
- Validated findings: 2
- Hook violations: 1
- Total queries: 3

## Investigation Metadata
- Investigation ID: 32
- Run ID: dfcbcc0f-dac3-4d5d-b44e-caaccb34ba56
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-18 10:01:43
- Completed: 2026-08-18 10:02:23

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
### Finding 0: Do the data files for this Iceberg table have a balanced size distribution, or are there many small files that could be inflating storage and query overhead?
- Verdict: found
- Exact result: Out of 261 files, 239 (≈92%) are 128‑256 MB, 19 are 64‑128 MB, 2 are 256‑512 MB, and only 1 is <64 MB, indicating a balanced size distribution with very few small files.
- Rationale: The table’s file size histogram shows the vast majority of files fall within the recommended 128‑256 MB range; only ~8% are under 128 MB, so small‑file overhead is minimal.
- Recommendation: Current file sizing is appropriate. Consider compacting the single sub‑64 MB file and the two 256‑512 MB files if they cause any downstream issues, but no major changes are needed.
- Evidence IDs: ['knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

### Finding 1: What is the proportion of delete files versus data files in this Iceberg table, and are there many small delete files that could be causing metadata overhead?
- Verdict: found
- Exact result: The table has 261 data files and 0 delete files (0.0% delete‑file proportion). There are no delete files at all, so there are also 0 small delete files.
- Rationale: The query result shows delete_file_count = 0 and delete_file_percentage = 0.0, with no small delete files reported. According to Iceberg delete‑file handling, metadata overhead from deletes only arises when many delete files (especially small ones) exist, which is not the case here.
- Recommendation: No action needed regarding delete‑file cleanup; focus on other potential performance factors.
- Evidence IDs: ['knowledge:iceberg/delete-file-handling@8f58d0073a71']
- Validation: valid

## Knowledge References Consulted

- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-18 10:01:48)
- `iceberg/delete-file-handling@8f58d0073a71` (fetched 2026-08-18 10:02:05)
