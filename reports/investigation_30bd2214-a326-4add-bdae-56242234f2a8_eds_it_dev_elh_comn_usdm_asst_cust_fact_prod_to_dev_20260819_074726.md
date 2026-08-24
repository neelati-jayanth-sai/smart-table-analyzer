# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 48
- Run ID: 30bd2214-a326-4add-bdae-56242234f2a8
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-19 07:46:48
- Completed: 2026-08-19 07:47:26

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
### Finding 0: Is the data evenly distributed across the 430 partitions, or does the table exhibit significant partition skew?
- Verdict: found
- Exact result: min_records=1, max_records=10003571, max_min_ratio=10003571.0
- Rationale: The maximum partition holds ~10 M rows while the minimum holds only 1 row, yielding a max/min ratio of 10 million‑to‑1, which is far beyond a balanced distribution.
- Recommendation: The table exhibits severe partition skew. Consider increasing partition granularity, redistributing data (e.g., rewrite with a more uniform partition key), or using clustering/compaction to balance record counts across partitions.
- Evidence IDs: ['knowledge:iceberg/data-skew-detection@0e14eda1f18a']
- Validation: valid

### Finding 1: What is the distribution of file sizes across the table's data files, and are there a large number of small files that could lead to high read overhead?
- Verdict: found
- Exact result: The table has 430 data files totaling 30.6 GB. Size distribution: 341 files (<64 MB), 2 files (64‑128 MB), 26 files (128‑256 MB), 61 files (256‑512 MB), 0 files (512 MB‑1 GB), 0 files (>1 GB). The minimum file size is 11 KB and the maximum is 453 MB.
- Rationale: The query result shows that ~79% (341/430) of files are smaller than the recommended 64 MB minimum, indicating a large number of tiny files that can increase read overhead. Iceberg best‑practice guidance recommends keeping files in the 128 MB‑1 GB range, ideally 256‑512 MB, to reduce per‑file metadata and I/O costs.
- Recommendation: Consolidate the many sub‑64 MB files (e.g., via compaction) to reach the sweet spot of 256‑512 MB per file. Aim for most files in the 128‑512 MB range and avoid creating new files smaller than 64 MB to lower read overhead and improve query performance.
- Evidence IDs: ['knowledge:iceberg/file-sizing-best-practices@2254c521af80']
- Validation: valid

### Finding 2: What is the count and size distribution of delete files (position or equality deletes) in the table, and could they be contributing to read overhead?
- Verdict: inconclusive
- Exact result: **Answer**

The query returned **no rows**, which means the table currently has **zero delete files** (neither position deletes nor equality deletes). Consequently:

| Metric                              | Value |
|-------------------------------------|-------|
| Delete‑file count (`delete_file_count`) | 0 |
| Total delete‑file size (`total_delete_file_size_bytes`) | 0 B |
| Minimum delete‑file size (`min_delete_file_size_bytes`) | N/A |
| Maximum delete‑file size (`max_delete_file_size_bytes`) | N/A |
| Average delete‑file size (`avg_delete_file_size_bytes`) | N/A |

Because there are no delete files, they **cannot be contributing to any read overhead** for this table.  

If you expect delete files to exist (e.g., after running `DELETE` statements or applying equality‑delete streams), verify that:

1. The query is run against the correct Iceberg table and snapshot.
2. The Iceberg catalog is refreshed so that newly‑added delete files are visible.
3. The `content` filter (if any) matches both position (`content = 1`) and equality (`content = 2`) delete files.

**Recommendation**

- Re‑run the delete‑file inventory query after a refresh or after a known delete operation to confirm the result.
- If delete files appear later, monitor their count and size; a large number of small delete files can increase read I/O because each delete file must be opened and scanned during query planning (see Iceberg delete‑file handling knowledge). Consider compacting delete files via `MERGE INTO …` or `REWRITE DATA` with `--target-file-size-bytes` to reduce overhead.  

---  

**Evidence & Reasoning**

- The query result shows `"row_count": 0` with the expected schema, indicating no matching rows were found.  
- Iceberg documentation states that delete files are stored separately and are read in addition to data files; if none exist, they add no extra I/O.  

**JSON Verdict**

```json
{
  "verdict": "found",
  "exact_result": "Delete file count = 0; no size distribution available.",
  "rationale": "Query returned zero rows for delete‑file metrics, meaning the table has no position or equality delete files, so they cannot cause read overhead.",
  "evidence_ids": ["knowledge:iceberg/delete-file-handling@8f58d0073a71"],
  "recommendation": "Refresh the catalog and re‑run the query after any DELETE/EQUALITY‑DELETE operations; if delete files appear, consider compacting them to reduce read overhead."
}
```
- Rationale: Quality gate rejection: Finding has inconclusive verdict
- Recommendation: N/A
- Evidence IDs: ['trail:2', 'knowledge:iceberg/delete-file-handling@8f58d0073a71']
- Validation: valid

## Knowledge References Consulted

- `iceberg/data-skew-detection@0e14eda1f18a` (fetched 2026-08-19 07:46:54)
- `iceberg/file-sizing-best-practices@2254c521af80` (fetched 2026-08-19 07:47:05)
- `iceberg/delete-file-handling@8f58d0073a71` (fetched 2026-08-19 07:47:18)
