# Investigation Report: eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev

## Summary
- Total findings: 3
- Validated findings: 3
- Hook violations: 0
- Total queries: 3

## Investigation Metadata
- Investigation ID: 75
- Run ID: b478f2e8-d422-4ddf-84eb-a50fea595b16
- Catalog: eds_it_dev
- Schema: elh_comn
- Status: completed
- Started: 2026-08-21 04:16:01
- Completed: 2026-08-21 04:16:11

## Baseline Score
- Overall: 88.05
- Dimensions:
  - file_size: 68.03
  - scan_efficiency: 83.33
  - delete_overhead: 100.0
  - manifest_organization: 99.15
  - partition_aware: 100.0
  - row_count: 667617969
  - num_data_files: 430
  - total_data_file_bytes: 30588066095
  - partition_count: 430
  - snapshot_count: 1
  - is_empty: False

## Findings
### Finding 0: What are the actual Iceberg table properties configured, and are any misconfigured?
- Verdict: found
- Exact result: commit.retry.min-wait-ms=1000, commit.retry.num-retries=5, current-snapshot-id=1307919922919960643
- Rationale: The three properties are present; retry settings match defaults (min‑wait 1000 ms) and are not harmful. However, key write‑time properties (e.g., write.target-file-size-bytes, format-version, write.delete.mode) are absent, which can lead to sub‑optimal file sizing or compatibility issues.
- Recommendation: Add missing critical Iceberg table properties such as write.target-file-size-bytes (default 536870912), format-version (e.g., 2), and write.delete.mode if deletes are used. The existing retry settings are acceptable.
- Evidence IDs: ['trail:0', 'knowledge:iceberg/table-properties-reference@9e0ad176bc79']
- Validation: valid

### Finding 1: Based on the pre-computed column cardinality data, which columns are good partition candidates (moderate cardinality, low nulls)?
- Verdict: not_found
- Exact result: []
- Rationale: No column has moderate cardinality (100‑10,000 distinct values) with <5% nulls in the pre‑computed stats.
- Recommendation: No suitable partition column based on current stats; consider adding a low‑cardinality categorical column or use time‑based partitioning if applicable.
- Evidence IDs: ['trail:1']
- Validation: valid

### Finding 2: What are the recommended partition columns and transforms based on column cardinality and query patterns?
- Verdict: not_found
- Exact result: No column meets the moderate cardinality (100‑10,000 distinct values) and low null (<5%) criteria for identity partitioning, and no time‑based column is evident in query patterns.
- Rationale: All candidate columns are either too low (56 values), too high (30,990 values) or have high null rates; query workload shows no time‑filtering.
- Recommendation: Do not add an identity partition column. If future queries filter on a categorical column with moderate cardinality, consider identity partitioning then. Otherwise retain the current table without additional partitions.
- Evidence IDs: ['trail:2']
- Validation: valid

## Knowledge References Consulted

- `iceberg/partition-transforms@0a94cba344a6` (fetched 2026-08-21 04:16:04)
- `runbooks/partition-strategy-guidelines@239416aabfea` (fetched 2026-08-21 04:16:04)
- `iceberg/table-properties-reference@9e0ad176bc79` (fetched 2026-08-21 04:16:05)
