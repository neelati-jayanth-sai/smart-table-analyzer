# BUILD_SPEC.md
## Smart Table Analyzer Local Iceberg Test Runtime

**Status:** Architecture candidate — implementation gated by STA surface audit  
**Primary consumer:** Smart Table Analyzer (STA)  
**Primary objective:** Make STA realistically testable locally without running Spark  
**Explicit non-objective:** Build a lightweight Spark replacement

---

# 1. Executive Decision

Build a **local analysis runtime for Smart Table Analyzer**.

Do **not** initially build:

- a Spark clone;
- a generic Spark/Iceberg compatibility engine;
- a SQL dialect compatibility system;
- a custom DataFrame engine;
- a transparent replacement for arbitrary PySpark applications.

The system should allow the **same STA analysis logic** to operate against two infrastructure implementations:

```text
                       Smart Table Analyzer
                                │
                       canonical contracts
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
             Production Runtime       Local Runtime
                    │                       │
                    ▼                       ▼
              Spark / Iomete        PyIceberg + DuckDB
                    │                       │
                    └───────────┬───────────┘
                                │
                         Apache Iceberg
```

The goal is behavioral parity of STA.

Not implementation parity between engines.

---

# 2. Problem Being Solved

STA currently operates in an environment where Spark and Iceberg are tightly integrated.

Production code can perform operations conceptually like:

```python
spark.table("catalog.namespace.table")
```

and:

```sql
SELECT *
FROM catalog.namespace.table.files
```

along with table scans, metadata inspection, partition analysis and aggregation.

Running Spark locally is expensive enough to make STA development and iteration painful.

Replacing Spark directly with DuckDB or PyIceberg creates a different problem:

```text
Production:
Spark syntax + Spark objects + Iceberg integration

Local:
DuckDB syntax + PyIceberg objects + different behavior
```

If analysis logic itself must change between these environments, local testing loses value.

Therefore the requirement is:

> STA business logic must be shared between local and production environments while infrastructure-specific behavior is isolated behind a small, explicit boundary.

---

# 3. Most Important Scope Correction

The project is **not**:

```text
Spark API
     ↓
our fake Spark
     ↓
DuckDB
```

The preferred architecture is:

```text
STA
 │
 ▼
Analysis Runtime Contract
 │
 ├───────────────┐
 ▼               ▼
Spark Runtime    Local Runtime
 │               │
Spark            PyIceberg + DuckDB
```

Transparent PySpark compatibility may be added selectively later.

It is not the fundamental architecture.

---

# 4. Why This Architecture

STA is not a general ETL framework.

Its primary job is to understand a table.

It cares about:

- schema;
- Iceberg field IDs;
- partition specification;
- partition evolution;
- files;
- file sizes;
- record counts;
- column statistics;
- snapshots;
- history;
- manifests;
- delete files;
- table properties;
- partition distribution;
- sample data;
- aggregations;
- compaction signals;
- maintenance signals.

These concepts belong to the analysis domain.

They should not be represented internally as:

- Spark Row;
- Spark DataFrame;
- DuckDB relation;
- PyArrow Table.

Those are infrastructure representations.

---

# 5. Canonical Domain Model

Introduce canonical internal types.

Potential models:

```text
TableMetadata
TableSchema
ColumnMetadata

PartitionSpec
PartitionField
PartitionStats

DataFileMetadata
DeleteFileMetadata
ColumnMetrics

SnapshotMetadata
SnapshotSummary
HistoryEntry

ManifestMetadata

TableProperties

TableProfile
```

These become the common language of STA.

Illustrative example only:

```python
@dataclass(frozen=True)
class DataFileMetadata:
    path: str
    content_type: str
    file_format: str
    spec_id: int
    record_count: int
    size_bytes: int
    partition: dict[str, object]
    column_sizes: dict[int, int]
    value_counts: dict[int, int]
    null_counts: dict[int, int]
    nan_counts: dict[int, int]
    lower_bounds: dict[int, object]
    upper_bounds: dict[int, object]
    sort_order_id: int | None
```

Important:

Do not simplify away Iceberg semantics.

Preserve identifiers such as:

```text
field_id
spec_id
snapshot_id
sequence_number
sort_order_id
```

These are important for analyzing evolved tables correctly.

---

# 6. Runtime Contract

Start with a narrow interface derived from the actual STA audit.

Illustrative shape:

```python
class AnalysisRuntime(Protocol):

    def get_table_metadata(
        self,
        table: TableIdentifier,
    ) -> TableMetadata:
        ...

    def get_schema(
        self,
        table: TableIdentifier,
    ) -> TableSchema:
        ...

    def get_files(
        self,
        table: TableIdentifier,
    ) -> list[DataFileMetadata]:
        ...

    def get_partitions(
        self,
        table: TableIdentifier,
    ) -> list[PartitionStats]:
        ...

    def get_snapshots(
        self,
        table: TableIdentifier,
    ) -> list[SnapshotMetadata]:
        ...

    def get_history(
        self,
        table: TableIdentifier,
    ) -> list[HistoryEntry]:
        ...

    def get_manifests(
        self,
        table: TableIdentifier,
    ) -> list[ManifestMetadata]:
        ...

    def sample(
        self,
        table: TableIdentifier,
        request: SampleRequest,
    ) -> TableSample:
        ...

    def aggregate(
        self,
        table: TableIdentifier,
        request: AggregateRequest,
    ) -> AggregateResult:
        ...
```

This interface is **not final**.

The actual methods MUST come from the STA audit.

Do not implement speculative methods.

---

# 7. Production Adapter

Implement:

```text
SparkIometeRuntime
```

The production implementation wraps behavior STA already uses.

For example:

```python
class SparkIometeRuntime:

    def get_files(self, table):
        return normalize_files(
            self.spark.sql(
                f"SELECT * FROM {table}.files"
            )
        )
```

Production continues using:

- Spark;
- Iceberg Spark integration;
- Iomete catalogs.

The adapter does not change how Spark works.

It converts Spark results into canonical STA models.

---

# 8. Local Adapter

Implement:

```text
LocalIcebergRuntime
```

Preferred implementation split:

```text
Metadata operations
        │
        ▼
    PyIceberg


Data scans / compute
        │
        ▼
      DuckDB
```

PyIceberg is the preferred local implementation for Iceberg metadata inspection.

DuckDB is the preferred local analytical compute engine.

Neither is treated as automatically equivalent to Spark.

---

# 9. Behavioral Authority

There are three levels of authority.

## 9.1 Iceberg specification

Defines intended table-format semantics.

## 9.2 Production Spark/Iomete

Defines behavior STA must remain compatible with in deployment.

## 9.3 Local implementations

PyIceberg and DuckDB provide local behavior.

They are implementations.

They are **not** assumed to be perfect compatibility references.

Therefore:

```text
production Spark/Iomete
          │
          │ differential tests
          ▼
canonical expected behavior
          ▲
          │
PyIceberg / DuckDB
```

---

# 10. Metadata Normalization

Do not expose raw PyIceberg results directly to STA.

Local path:

```text
PyIceberg
    │
    ▼
Local Normalizer
    │
    ▼
Canonical STA Model
```

Production path:

```text
Spark Iceberg metadata table
    │
    ▼
Spark Normalizer
    │
    ▼
Canonical STA Model
```

Analyzer logic sees only the canonical middle layer.

---

# 11. Why PyIceberg Is Useful

Iceberg exposes metadata concepts such as:

- history;
- snapshots;
- files;
- manifests;
- partitions;
- entries;
- refs;
- metadata log entries;
- delete files.

PyIceberg exposes corresponding inspection APIs.

Examples:

```python
table.inspect.files()
table.inspect.partitions()
table.inspect.snapshots()
table.inspect.manifests()
table.inspect.entries()
```

This means much of STA's metadata work can likely be implemented without Spark, DuckDB SQL translation, or SQLFrame.

---

# 12. Differential Conformance Testing

This is a first-class system component.

Create fixture scenarios including:

```text
basic_unpartitioned
basic_partitioned
many_small_files
large_files
skewed_partition
many_partitions
schema_evolution
partition_evolution
multiple_partition_specs
many_snapshots
snapshot_rollback
many_manifests
position_deletes
equality_deletes
sort_order
null_heavy_columns
wide_schema
nested_schema
```

The same logical fixture must be evaluated using:

```text
Spark/Iomete Runtime
```

and:

```text
Local Runtime
```

---

# 13. Compare Canonical Outputs

Do not compare Spark objects directly to PyArrow objects.

Compare canonical models.

Example:

```python
expected = spark_runtime.get_files(TABLE)
actual = local_runtime.get_files(TABLE)

assert_semantically_equal(
    expected,
    actual,
)
```

Conformance must cover:

- schemas;
- identifiers;
- data types;
- snapshot IDs;
- spec IDs;
- field IDs;
- partition values;
- file metrics;
- null semantics;
- error behavior where relevant.

---

# 14. Analyzer-Level Conformance

This is more important than adapter-level conformance.

Example fixture:

```text
47 files

42 files:
1–3 MB

5 files:
250 MB

target size:
256 MB
```

Both runtimes should eventually cause STA to conclude something materially equivalent to:

```text
small file problem detected
severity: high
compaction recommended
```

The ultimate test is:

```text
STA + Spark
      │
      ▼
Finding Set A


STA + Local Runtime
      │
      ▼
Finding Set B


A ≈ B
```

---

# 15. Exact Equality Is Not Always Required

Distinguish:

```text
engine parity
```

from:

```text
analysis parity
```

Different engines may represent timestamps, decimals, or nested values differently.

If normalization produces equivalent canonical values and STA reaches the same analysis conclusion, the system may be correct.

Do not reproduce irrelevant formatting differences.

---

# 16. SQLFrame's Role

SQLFrame is useful but optional.

Use it only when STA contains meaningful existing PySpark DataFrame transformation logic such as:

```python
df.filter(...)
  .groupBy(...)
  .agg(...)
  .withColumn(...)
  .select(...)
```

and moving that transformation behind runtime methods would provide little value.

Optional path:

```text
STA transformation
       │
       ▼
   PySpark-shaped API
       │
       ▼
     SQLFrame
       │
       ▼
      DuckDB
```

SQLFrame must **not** become a dependency of every metadata operation.

---

# 17. DuckDB's Role

DuckDB is primarily:

```text
local analytical compute
```

Use it for:

- scanning;
- aggregation;
- sampling;
- grouping;
- filtering;
- joining;
- profiling.

Do not initially rely on DuckDB for:

- Iceberg metadata correctness;
- Spark compatibility;
- maintenance semantics;
- write conflict semantics;
- transaction parity.

unless conformance tests prove the exact required behavior.

---

# 18. Avoid a Generic SQL Router

Do not build:

```text
spark.sql()
     │
SQL classifier
     │
Spark SQL parser
     │
Iceberg dispatch
     │
DuckDB translation
```

This can become a Spark SQL compatibility project.

Prefer semantic runtime operations.

Bad inside analyzer business logic:

```python
spark.sql(
    f"""
    SELECT *
    FROM {table}.files
    """
)
```

Better:

```python
runtime.get_files(table)
```

Production may implement that using Spark SQL.

Local may implement it using PyIceberg.

---

# 19. Escape Hatch for SQL

Only add unrestricted SQL if the repository audit proves it is needed.

Possible controlled API:

```python
runtime.execute_query(
    QueryRequest(...)
)
```

Avoid a generic:

```python
runtime.sql(str)
```

until there is demonstrated need.

Otherwise the runtime abstraction collapses into an engine abstraction.

---

# 20. Compute API

STA may need a smaller set of compute primitives:

- sample rows;
- count rows;
- count distinct;
- null counts;
- min/max;
- approximate cardinality;
- group-by partition;
- histogram;
- column profiling;
- correlation;
- targeted custom aggregation.

Represent recurring operations explicitly.

Illustrative example:

```python
runtime.aggregate(
    table,
    AggregateRequest(
        metrics=[
            Count("*"),
            NullCount("customer_id"),
            Min("created_at"),
            Max("created_at"),
        ]
    )
)
```

Production can use Spark.

Local can use DuckDB.

However, do not create an elaborate query DSL.

If an existing transformation already works cleanly under SQLFrame, use SQLFrame selectively.

---

# 21. Catalog Strategy

Do not make a REST server mandatory for every test.

Use two tiers.

## Fast tests

```text
PyIceberg
local warehouse
temporary data
in-process runtime
```

## Integration/conformance tests

```text
Iceberg REST-compatible catalog
+
object storage / MinIO if required
+
Local runtime
```

These verify:

- catalog.namespace.table resolution;
- REST catalog behavior;
- catalog operations;
- relevant configuration mapping.

REST equivalence does not imply full Iomete equivalence.

---

# 22. Identifier Model

Use an explicit type:

```python
@dataclass(frozen=True)
class TableIdentifier:
    catalog: str
    namespace: tuple[str, ...]
    table: str
```

Avoid passing raw `"catalog.db.table"` strings through core STA logic after parsing.

This reduces problems around:

- nested namespaces;
- quoting;
- case behavior;
- catalog selection;
- metadata-table suffixes.

---

# 23. Metadata Tables Are Not Ordinary Tables

Do not model:

```text
catalog.db.table.files
```

as a normal table identifier internally.

Prefer:

```python
MetadataTableRequest(
    table=TableIdentifier(...),
    kind=MetadataTable.FILES,
)
```

Production adapter renders Spark syntax.

Local adapter calls PyIceberg inspection APIs.

---

# 24. Canonical Type Normalization

Explicitly normalize:

```text
decimal
date
timestamp
timestamp with timezone
binary
UUID
fixed
list
map
struct
NaN
infinity
null
nested values
Iceberg encoded lower/upper bounds
```

Do not normalize complex values using `str(value)`.

---

# 25. Metrics Normalization

Iceberg file metrics use Iceberg field IDs.

STA must preserve those IDs.

Canonical metadata should retain:

```text
field_id
spec_id
snapshot_id
sequence_number
sort_order_id
```

Optionally resolve current column names, but never discard underlying IDs.

This is essential after schema evolution and column renames.

---

# 26. Partition Evolution

Partition evolution is a mandatory conformance scenario.

Example:

```text
spec 0:
days(timestamp)

spec 1:
days(timestamp), region
```

Canonical file metadata must retain `spec_id`.

STA must not flatten multiple historical partition specs into a single assumed layout.

---

# 27. Schema Evolution

Mandatory scenarios:

```text
column add
column rename
column delete
compatible type promotion
nested field evolution
```

STA should rely on Iceberg field IDs rather than:

```text
column position == column identity
```

---

# 28. Delete Files

Mandatory scenarios:

```text
position deletes
equality deletes
```

Be careful:

```text
record_count in data files
```

does not necessarily equal:

```text
visible table row count
```

STA recommendations must understand that distinction.

---

# 29. Snapshot Semantics

Preserve where relevant:

```text
snapshot_id
parent_id
sequence_number
operation
commit timestamp
summary
manifest list
```

Do not derive snapshot behavior from file modification times.

---

# 30. Caching

Metadata caching should live above engine-specific runtime implementations where possible.

Preferred:

```text
Investigator
       │
       ▼
Analysis Context / Metadata Cache
       │
       ▼
AnalysisRuntime
```

This allows local and production to exercise the same caching behavior.

Minimum cache key should contain conceptually:

```text
catalog
namespace
table
snapshot_id
metadata_kind
```

Avoid stale reuse after snapshot changes.

---

# 31. Legacy Analyzer Integration

Legacy Analyzer should consume canonical models.

Preferred flow:

```text
AnalysisRuntime
       │
       ▼
Canonical Table Context
       │
       ├──► Legacy Analyzer
       │
       └──► Investigator
```

Legacy Analyzer can calculate deterministic signals such as:

- small-file ratio;
- average file size;
- partition skew;
- snapshot accumulation;
- manifest count;
- partition cardinality.

It should not know which engine produced the metadata.

---

# 32. Investigator Integration

Investigator should not receive raw:

- Spark Rows;
- DuckDB result sets;
- Arrow schemas.

It should receive:

```text
Canonical Table Context
+
deterministic findings
+
targeted query results
```

This improves deterministic testing and context control.

---

# 33. Fixture Philosophy

Avoid mock-only tests for infrastructure semantics.

Create actual Iceberg tables.

Pathology fixtures should include:

```text
HEALTHY_TABLE
SMALL_FILES
PARTITION_SKEW
PARTITION_EXPLOSION
SNAPSHOT_BLOAT
MANIFEST_BLOAT
SCHEMA_EVOLUTION
PARTITION_EVOLUTION
DELETE_HEAVY
SORTED_TABLE
UNPARTITIONED_LARGE_TABLE
```

---

# 34. Declarative Fixtures

Prefer declarative scenario descriptions.

Example:

```yaml
name: small_files

schema:
  id: long
  timestamp: timestamp
  region: string

partition:
  - days(timestamp)

files:
  count: 100
  approximate_size: 2MB

expected_findings:
  - SMALL_FILE_PROBLEM
  - COMPACTION_CANDIDATE
```

Fixture builders create real Iceberg state from those descriptions.

---

# 35. Three Test Layers

## Layer 1 — Unit

Test:

- normalizers;
- deterministic analyzers;
- canonical models;
- cache;
- Investigator input construction.

No external engine required.

## Layer 2 — Local integration

Use:

```text
PyIceberg
DuckDB
real Iceberg files
```

## Layer 3 — Conformance

Compare:

```text
Spark/Iomete
vs
Local runtime
```

Run selectively or in CI where practical.

---

# 36. Version Pinning

Pin actual versions.

Conceptually:

```yaml
production_profile:
  spark: "<actual Iomete Spark version>"
  iceberg: "<actual production Iceberg version>"

local_profile:
  pyiceberg: "<pinned>"
  duckdb: "<pinned>"
  sqlframe: "<pinned if used>"
```

Do not infer production versions.

Do not use unpinned “latest” versions in conformance tests.

---

# 37. Known Difference Registry

Maintain a machine-readable registry.

Example:

```yaml
differences:
  - id: D001
    area: timestamp_precision
    local: ...
    production: ...
    normalization: ...
    safe: true

  - id: D002
    area: ...
    safe: false
```

Unknown differences should fail strict conformance.

---

# 38. Strict Test Mode

Conformance tests run in strict mode.

Unknown semantic divergence:

```text
FAIL
```

not:

```text
WARN
```

False confidence is more dangerous than unsupported functionality.

---

# 39. Spark API Compatibility

Transparent Spark compatibility is not an initial requirement.

After extracting runtime boundaries, classify remaining Spark-specific code:

```text
A — easily moved behind runtime
B — SQLFrame can execute unchanged
C — genuinely requires Spark
D — dead / unnecessary
```

Only category B justifies SQLFrame integration.

---

# 40. SQLFrame Evaluation Gate

Before making SQLFrame a core dependency:

Take real STA transformations and evaluate:

```text
API compatibility
result parity
type parity
function coverage
performance
failure behavior
```

Adopt it only if it materially reduces duplication.

---

# 41. Write Support

STA is primarily an analyzer.

Local writes are secondary.

Initial write support only needs to construct and evolve fixture tables.

STA itself should normally be read-only.

This reduces compatibility risk.

---

# 42. Maintenance Actions

Separate:

```text
maintenance detection
```

from:

```text
maintenance execution
```

STA should initially answer:

- Does this table need compaction?
- Why?
- Which files or partitions are causing it?
- What is the likely benefit?

It does not need to reproduce every Spark maintenance procedure locally.

Optional future simulation must be clearly labelled simulation.

---

# 43. Explicitly Rejected Work

Do not implement:

```text
SparkSession clone
Spark scheduler
Catalyst clone
generic DataFrame engine
Spark SQL parser
Spark SQL transpiler
RDD
Spark Connect
streaming
MLlib
custom Iceberg metadata parser
custom Parquet reader
custom REST catalog
```

Existing projects own these concerns.

---

# 44. Primary Acceptance Criterion

The project succeeds when:

> For supported STA scenarios, local execution and production Spark/Iomete execution generate semantically equivalent canonical inputs and materially equivalent analyzer findings.

Not:

- “95% PySpark compatibility”;
- “same SQL runs”;
- “DuckDB looks like Spark”.

---

# 45. Secondary Acceptance Criteria

The local runtime should provide:

- fast startup;
- low memory overhead;
- deterministic fixtures;
- no JVM requirement;
- easy pytest integration;
- real Iceberg metadata.

Measure performance instead of inventing targets.

---

# 46. Kill Criteria

Stop expanding the runtime if any of the following are true.

## K1

Extracting Spark behind the runtime requires rewriting most STA business logic.

## K2

PyIceberg/DuckDB disagree with Spark frequently on common STA scenarios and differences cannot be normalized safely.

## K3

A generic SQL compatibility layer becomes necessary.

## K4

The project starts implementing query-engine internals.

## K5

Local testing becomes nearly as complex or expensive as running Spark.

## K6

Most failures become runtime-compatibility bugs rather than STA bugs.

---

# 47. Go Criteria

Continue if the STA surface audit shows the majority of work is:

```text
Iceberg metadata inspection
+
ordinary analytics
+
limited Spark DataFrame transformations
```

Be cautious if it reveals heavy reliance on:

```text
Spark execution plans
Spark-specific UDFs
complex Spark SQL extensions
RDD APIs
distributed semantics
custom Spark listeners
Spark write behavior
transaction/conflict behavior
arbitrary SQL
```

---

# 48. Future Generalization

Only after STA works reliably should this be considered for extraction into a broader:

```text
Portable Iceberg Analysis Runtime
```

Only after that should Spark-compatible syntax be considered.

Generalization is an outcome.

It is not an initial requirement.

---

# 49. Final Technology Decisions

## PyIceberg

**Use.**

Role:

- Iceberg metadata inspection;
- catalog access;
- fixture operations where appropriate.

Confidence:

High, but conformance tested.

## DuckDB

**Use.**

Role:

- local compute;
- scans;
- aggregations;
- profiling.

Confidence:

High for analytical compute, lower for Spark/Iceberg semantic parity.

## SQLFrame

**Evaluate, then selectively use.**

Role:

- preserve existing PySpark DataFrame transformations where beneficial.

Do not make it foundational until real STA code proves the need.

## DuckDB experimental Spark API

**Do not use as foundation.**

## Iceberg REST catalog

**Use in integration/conformance tests where catalog parity matters.**

Do not require it for every unit test.

---

# 50. Final Architecture

```text
                         ┌─────────────────────┐
                         │ Smart Table Analyzer│
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Canonical STA Model │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  AnalysisRuntime    │
                         └──────┬───────┬──────┘
                                │       │
                  production    │       │ local
                                │       │
                                ▼       ▼
                           Spark       PyIceberg
                           Iomete        │
                              │          ├── Metadata
                              │          │
                              │        DuckDB
                              │          │
                              │          └── Compute
                              │
                              └──────────┬───────────┘
                                         │
                                         ▼
                                   Apache Iceberg
```

Optional implementation detail:

```text
existing PySpark transformation
              │
              ▼
          SQLFrame
              │
              ▼
           DuckDB
```

---

# 51. Final Engineering Principle

The goal is **not**:

> Make DuckDB behave like Spark.

The goal is:

> Make Smart Table Analyzer independent of which correct Iceberg-capable engine supplies its analysis inputs.

That is the smaller and more defensible problem.

---

# 52. Implementation Gate

Do not begin substantial runtime implementation until these artifacts exist:

1. `STA_SPARK_SURFACE.md`
2. `STA_RUNTIME_CONTRACT.md`
3. a minimal conformance fixture plan
4. proof that `SparkIometeRuntime` can wrap current production behavior without changing analyzer semantics

If the repository contradicts assumptions in this document, update the implementation plan.

Do not force the repository to fit the document.
