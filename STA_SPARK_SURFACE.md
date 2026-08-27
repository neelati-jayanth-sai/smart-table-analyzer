# Smart Table Analyzer Spark/Iceberg Dependency Audit

## 1. Summary

The production analysis path is **mixed, with a metadata-centric core**.  The
Legacy Analyzer reads Iceberg metadata tables plus bounded aggregate scans. The
Investigator additionally executes validated, read-only SQL produced at run
time; this is an audited escape hatch, not a reason to emulate Spark SQL.

| Measure | Observed result |
|---|---|
| Core production Spark call sites | 18 in `src/` |
| Distinct core APIs | `sql`, `table`, schema, `limit`, `first`, `collect`, `count` |
| Iceberg metadata relations consumed | `.files`, `.partitions`, `.snapshots`, `.history` |
| Spark configuration in core analyzer | none; connection bootstrap only |
| Production writes/procedures | none in analyzer; recommendations are text only |

## 2. Dependency Inventory

| ID | File | Operation | Category | Purpose | Local candidate | Risk |
|---|---|---|---|---|---|---|
| S001 | `src/analyzer/metrics.py` | aggregates over `.files`, `.partitions`, `.snapshots` | A | deterministic baseline | metadata models | medium |
| S002 | `src/metadata/loader.py` | `table().schema`, bounded sample | A/B | schema and evidence sample | runtime schema/sample | low |
| S003 | `src/metadata/columns.py` | bounded aggregate profile query | B | cardinality/null/min/max | DuckDB aggregate | medium |
| S004 | `src/metadata/partitions.py` | `DESCRIBE`, `SHOW CREATE TABLE` | A | current partition spec | canonical partition spec | medium |
| S005 | `src/metadata/properties.py` | `SHOW TBLPROPERTIES` | A | property-casing evidence | canonical properties | low |
| S006 | `src/query/snapshot_pinning.py` | latest `.snapshots` row | A | reproducible observation | latest snapshot | low |
| S007 | `src/metadata/query_patterns.py` | IOMETE activity-log SQL | D | optional workload signal | production-only unavailable result | medium |
| S008 | `src/query/query_workbench.py` | validated arbitrary read-only SQL | B/D | Investigator evidence checks | restricted runtime query | high |
| S009 | `src/dashboard/analysis_runner.py` | `SparkSession.getActiveSession` | D | production connection bootstrap | production-only | none |
| S010 | `scripts/_investigation_cli.py` | Spark Connect session bootstrap | D | CLI bootstrap | production-only | none |

## 3. SparkSession and configuration

Only the dashboard and operational scripts construct `SparkSession`; the
analyzer modules receive an already-created session. No analyzer decision
depends on session configuration. Spark Connect, certificate, catalog, and
IOMETE URL configuration remain production bootstrap concerns. A local runtime
must not provide a session replacement.

## 4. SQL and DataFrame surface

Core SQL patterns are: metadata aggregates, `SHOW TBLPROPERTIES`, `DESCRIBE
EXTENDED`, `SHOW CREATE TABLE`, column aggregate profiling, the optional IOMETE
activity-log query, and validated Investigator SELECT/WITH statements. Core
DataFrame use is limited to `schema.fields`, `limit`, `first`, `collect`, and
`count`; there are no `pyspark.sql.functions`, `Window`, joins, caching,
repartitioning, or writer APIs in `src/`.

The Investigator query workbench requires a controlled `execute_readonly`
operation because generated evidence SQL is intentionally open-ended after
validation. It must remain bounded to the target table and read-only hooks;
there is no audited need for generic `spark.sql` on the local path.

## 5. Iceberg, errors, and mutations

The core reads only `.files`, `.partitions`, `.snapshots`, and `.history`.
It consumes file content, record and byte counts, `spec_id`, `sort_order_id`,
partition aggregates, snapshot IDs/timestamps, schema names/types, and table
properties. There is no use of manifests, entries, refs, metadata logs, or
delete-file metadata relations directly; delete files are identified by
`files.content != 0`.

No production analyzer writes or calls Iceberg procedures. `rewrite_data_files`
and `ALTER TABLE` occur only in action-safety tests and recommendation handling.
Spark failures are deliberately represented as unavailable measurements or
failed evidence queries; local adapters need equivalent explicit failures.

## 6. Tests and hotspots

Existing tests use `tests/mocks/spark.py` and `tests/mocks/iceberg.py`; these
are useful production-path fakes but are not real local-Iceberg fixtures.
Hotspots are `src/analyzer/metrics.py`, `src/metadata/loader.py`,
`src/metadata/columns.py`, and `src/query/query_workbench.py`.

## 7. Candidate Runtime Operations

| Runtime method | Existing evidence | Adapter behavior |
|---|---|---|
| `table_metadata` | S001, S002, S004, S005 | schema, files, partitions, snapshots, history, properties |
| `sample_rows` | S002 | bounded base-table scan |
| `profile_columns` | S003 | exact bounded aggregates |
| `latest_snapshot_id` | S006 | latest snapshot by commit time |
| `query_patterns` | S007 | production IOMETE adapter; explicit unavailable locally |
| `execute_readonly` | S008 | validated target-table evidence query |

## 8. Architectural conclusion and Go / No-Go

**GO WITH REDUCED SCOPE.** The repository supports a narrow analysis runtime
for deterministic metadata, sampling, profiling, and controlled evidence
queries. PyIceberg can own Iceberg metadata and DuckDB can own local scans and
aggregates. SQLFrame is not justified: there are no DataFrame transformations
to preserve. Arbitrary Investigator SQL is a risk, so local support must be
explicitly bounded and fail closed for unsupported syntax rather than become a
Spark SQL compatibility project. Production-only IOMETE workload logs remain
an unavailable measurement locally.
