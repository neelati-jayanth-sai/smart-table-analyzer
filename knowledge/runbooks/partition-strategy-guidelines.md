# Tested Partition Strategy Guidelines

## Decision rule

Choose partitioning from access pattern and expected capacity per partition,
not total table size alone. The target is useful partition pruning while still
forming files appropriate to the selected workload profile.

Required evidence:

- current `SHOW CREATE TABLE` partition transform and sort order;
- partition byte/file-count distribution and active partition-spec IDs;
- frequently filtered driver columns from workload evidence;
- table width, row density, and COW/MOR ingestion mode.

## Tested patterns

| Evidence | Tested direction |
| --- | --- |
| Large traffic/event table with time predicates | `days(time_column)`; use range distribution when sorted for consumption |
| Low daily volume where daily partitions create small files | Test `months(time_column)` before recommending it |
| Narrow, high-row-density CUST-style table | Monthly partitioning was tested to produce a balanced approach |
| No reliable partition predicate | Keep unpartitioned and use hash distribution; do not invent a partition key |
| Frequent high-cardinality equality lookups | Test a bucket only when workload evidence proves its value |

Month partitioning is conditional: it must preserve workload pruning. A small
average partition alone is not proof that it is appropriate.

## Guardrails

- Use at most two partition fields. Add a second only for a demonstrated
  secondary access pattern.
- Do not identity-partition a high-cardinality identifier.
- Do not recommend a transform change from total table size alone.
- Treat partition-spec evolution as a migration: old files can retain an old
  layout. Report active spec IDs and rewrite requirement.
- Test the proposed spec on representative data and queries before production.

## Sorting relationship

For a partitioned, sorted table, place tested driver columns in the sort order
and use range distribution for writes. For an unsorted partitioned table, use
hash distribution. Do not sort by a partition column without an additional
consumption reason.

## Review checklist

- [ ] Driver predicates and sort keys have workload evidence.
- [ ] Proposed capacity supports the selected file-size profile.
- [ ] The proposed spec has no more than two fields.
- [ ] COW/MOR mode and compaction cadence are stated.
- [ ] Existing and proposed layouts were tested before a production rewrite.

## Provenance

Team-verified ingestion and consumption test matrix supplied 2026-08-24.
