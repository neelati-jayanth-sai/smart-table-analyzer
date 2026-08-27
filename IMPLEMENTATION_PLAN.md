# IMPLEMENTATION_PLAN.md
## Mandatory Build and Test Sequence

This document is the execution contract for implementing the architecture in `BUILD_SPEC.md`.

The order below is mandatory unless repository evidence proves a step impossible or unnecessary.

Do not skip directly to building `LocalIcebergRuntime`.

---

# 1. Repository Audit First

Audit the entire Smart Table Analyzer repository.

Find every direct and indirect use of:

```text
SparkSession
spark.sql
spark.table
spark.read
spark.catalog
DataFrame
pyspark.sql.functions
Window
collect
toPandas
Spark Row
Spark SQL types
Iceberg metadata tables
Iceberg procedures
Spark configuration
catalog configuration
Spark-specific helper utilities
Spark-specific exceptions
```

Also inspect tests, mocks, fixtures, adapters, and legacy code.

Do not refactor yet.

Deliver:

```text
STA_SPARK_SURFACE.md
```

The audit must include every usage location and classify why it exists.

---

# 2. Classify Every Spark Dependency

Each Spark dependency must be classified into one of:

```text
A — metadata access
B — ordinary analytical compute
C — existing DataFrame transformation
D — Spark-specific semantics
E — write or mutation
F — maintenance/procedure
G — dead or unnecessary
H — unknown / needs investigation
```

For every entry record:

- file;
- symbol or SQL;
- purpose;
- frequency;
- current input/output shape;
- whether STA business logic depends on Spark-specific representation;
- candidate local implementation;
- compatibility risk.

Do not infer support from documentation alone.

Use small executable probes when needed.

---

# 3. Produce the Minimum Runtime Contract

From the audit, generate:

```text
STA_RUNTIME_CONTRACT.md
```

Rules:

- no speculative methods;
- every method must map to at least one real STA operation;
- methods should represent domain actions, not engine syntax;
- do not add generic `.sql()` unless audit evidence requires it;
- do not expose Spark DataFrame or PyArrow Table in the public contract unless unavoidable.

Example good methods:

```text
get_schema
get_files
get_partitions
get_snapshots
sample_rows
profile_columns
```

Example bad methods without evidence:

```text
sql
execute_anything
spark_session
duckdb_connection
```

---

# 4. Define Canonical Models

Create only models needed by the runtime contract.

Preserve important Iceberg identities:

```text
field_id
spec_id
snapshot_id
sequence_number
sort_order_id
```

Normalize infrastructure-specific types.

Do not create a huge domain model hierarchy.

Prefer small immutable dataclasses or Pydantic models.

Add focused unit tests for canonicalization.

---

# 5. Implement Production Adapter First

Implement:

```text
SparkIometeRuntime
```

using existing production Spark/Iomete behavior.

Do not alter analyzer algorithms yet.

Move one capability at a time behind the runtime.

Suggested migration order:

```text
schema
table properties
files
partitions
snapshots
history
manifests
sample/read
profile/aggregate
other audited capabilities
```

After each migration:

- run existing tests;
- run production-path tests;
- confirm canonical output;
- ensure no analyzer behavior changed unintentionally.

---

# 6. Use a Strangler Migration

Do not rewrite STA in one pass.

For each capability:

```text
existing Spark path
        │
        ▼
wrap behind runtime
        │
        ▼
canonical model
        │
        ▼
same analyzer logic
```

Keep the application runnable after each step.

Commit or checkpoint logically complete migrations.

---

# 7. Eliminate Engine Objects from Analyzer Logic

Gradually remove direct dependencies from analysis code on:

- Spark Row;
- Spark DataFrame;
- Arrow Table;
- DuckDB relation.

These objects may exist inside adapters.

They should not leak into:

- deterministic analyzers;
- Investigator context;
- recommendation logic;
- scoring logic;
- report generation.

---

# 8. Build Real Iceberg Fixtures

Do not rely only on mocked metadata.

Create real Iceberg fixtures for at least:

```text
healthy_table
many_small_files
partition_skew
schema_evolution
partition_evolution
snapshot_buildup
```

Then expand to:

```text
many_manifests
delete_heavy
multiple_partition_specs
wide_schema
nested_schema
sorted_table
unpartitioned_large_table
```

Each fixture should declare expected semantic properties.

---

# 9. Fixture Builder Requirements

Prefer declarative fixtures.

Example:

```yaml
name: small_files
rows: 100000
files: 100
approx_file_size_mb: 2

expected:
  small_file_problem: true
  compaction_candidate: true
```

Do not mock the final metadata result.

The builder should create real Iceberg state producing those characteristics.

---

# 10. Implement LocalIcebergRuntime

Only after the production adapter and canonical models are working.

Preferred ownership:

```text
PyIceberg:
metadata inspection
catalog access
Iceberg-aware operations

DuckDB:
scans
aggregation
profiling
sampling
general local compute
```

Do not route metadata through DuckDB merely because DuckDB can read it.

Do not route compute through PyIceberg if DuckDB is more appropriate.

---

# 11. Add SQLFrame Only Through a Gate

Inspect existing STA DataFrame-heavy logic.

If a transformation is costly to rewrite and SQLFrame can execute it correctly:

- create a focused compatibility test;
- compare results with Spark;
- document supported functions;
- use SQLFrame only for that path.

Do not globally replace PySpark imports unless there is strong evidence this is needed.

Do not make SQLFrame the center of the runtime.

---

# 12. Differential Testing Per Runtime Method

For every supported runtime operation:

```text
SparkIometeRuntime
        │
        ▼
canonical expected result

LocalIcebergRuntime
        │
        ▼
canonical actual result
```

Compare semantic equality.

Normalize safe representation differences explicitly.

Unknown differences must fail strict tests.

---

# 13. Analyzer-Level Differential Testing

Run the same fixture through STA with both runtimes.

Compare:

```text
detected issue type
severity
evidence
recommendation type
important metrics
```

Do not require exact prose equality from an LLM.

Compare structured findings before natural-language report generation.

---

# 14. Investigator Testing

Investigator tests should use deterministic canonical context.

Where LLM outputs are involved:

- test prompt/input construction separately;
- test deterministic pre-analysis separately;
- use schema validation;
- avoid making local-vs-production parity depend on free-form wording.

If Investigator findings are structured, compare normalized structured output.

---

# 15. Legacy Analyzer Testing

Legacy Analyzer must operate on canonical inputs.

Add deterministic tests for:

```text
small-file ratio
average file size
partition skew
partition cardinality
snapshot count/growth
manifest count
compaction signals
```

These tests should not require Spark.

---

# 16. Cache Testing

Cache semantics should be shared across runtimes.

Test:

- cache hit;
- cache miss;
- snapshot change invalidation;
- metadata-kind isolation;
- table identifier isolation.

Cache keys should include the snapshot identity when relevant.

---

# 17. Type Conformance Tests

Add explicit tests for:

```text
decimal
date
timestamp
timestamp with timezone
binary
UUID
nested structs
arrays
maps
null
NaN
Iceberg lower/upper bounds
```

Do not rely on string comparison.

---

# 18. Evolution Conformance Tests

Mandatory:

```text
column add
column rename
column delete
compatible type promotion
partition spec evolution
multiple spec IDs across files
```

Ensure field IDs and spec IDs survive normalization.

---

# 19. Delete Semantics Tests

Create fixtures with:

```text
position deletes
equality deletes
```

Verify STA does not confuse:

```text
physical data-file record counts
```

with:

```text
visible table row count
```

---

# 20. Known Difference Registry

Create:

```text
KNOWN_DIFFERENCES.yaml
```

Each accepted difference must contain:

```text
id
area
production behavior
local behavior
normalization rule
why it is safe
test covering it
```

Do not add differences simply to make tests pass.

Every accepted difference requires justification.

---

# 21. Strict Conformance Mode

Conformance tests must have strict mode.

Unknown semantic difference:

```text
FAIL
```

Supported and documented harmless difference:

```text
NORMALIZE
```

Unsupported semantic behavior:

```text
EXPLICITLY UNSUPPORTED
```

Never silently continue.

---

# 22. No Generic Spark Compatibility Work

Do not implement any of these unless the current repository forces it and the implementation note explains why:

```text
fake SparkSession
generic Spark SQL parser
generic SQL transpiler
DataFrame engine
Catalyst-like planner
Spark scheduler
RDD API
Spark Connect
UDF system
streaming
MLlib
```

If implementation starts moving in these directions, stop and reassess.

---

# 23. No Local Branches in Business Logic

Do not introduce:

```python
if local:
    ...
else:
    ...
```

inside analyzer business logic.

Environment-specific behavior belongs in runtime adapters.

Bootstrap-level environment selection is acceptable.

---

# 24. Production Compatibility Must Remain Intact

The existing Spark/Iomete path must remain functional throughout the migration.

Do not optimize for local testing by weakening production behavior.

Every refactor should preserve production-path tests.

---

# 25. Measure Rather Than Assume

For important decisions, gather evidence:

```text
actual Spark surface size
actual SQLFrame coverage
actual PyIceberg metadata parity
actual DuckDB compute parity
actual startup time
actual memory use
actual fixture-generation cost
```

Do not use guessed percentages.

---

# 26. Required Artifacts

By the end of implementation, the repository should include:

```text
BUILD_SPEC.md
IMPLEMENTATION_PLAN.md
STA_SPARK_SURFACE.md
STA_RUNTIME_CONTRACT.md
KNOWN_DIFFERENCES.yaml
```

Optionally:

```text
CONFORMANCE_MATRIX.md
FIXTURE_CATALOG.md
```

if they provide real value.

---

# 27. Required Test Layers

The implementation is incomplete unless all three exist.

## Unit

No engine required.

## Local integration

Real Iceberg + PyIceberg/DuckDB.

## Differential conformance

Spark/Iomete vs local for supported capabilities.

---

# 28. Definition of Done

The work is complete only when:

- `STA_SPARK_SURFACE.md` reflects the real codebase;
- `STA_RUNTIME_CONTRACT.md` contains only proven necessary operations;
- analyzer business logic does not directly depend on engine-specific metadata representations;
- production Spark execution still works;
- local execution works without requiring Spark/JVM for supported tests;
- at least six real Iceberg pathology fixtures work;
- same analyzer logic runs against both runtimes;
- supported runtime operations have differential tests;
- analyzer-level structured findings are materially equivalent for supported fixtures;
- known differences are documented;
- no generic Spark compatibility subsystem was introduced without explicit necessity;
- test suite passes.

---

# 29. Stop Conditions

Stop and document findings rather than expanding scope if:

## S1

The runtime abstraction requires rewriting most of STA.

## S2

STA heavily depends on distributed Spark semantics.

## S3

A general Spark SQL compatibility layer becomes necessary.

## S4

Local and Spark semantics diverge frequently in ways that cannot be normalized safely.

## S5

The local harness becomes almost as expensive or complicated as Spark.

## S6

Most engineering effort shifts from STA to maintaining a pseudo-engine.

---

# 30. Final Instruction to the Implementer

Do not follow this document mechanically when the repository disproves an assumption.

Treat:

```text
existing code
tests
production behavior
measured results
```

as evidence.

When an assumption is disproven:

1. document it;
2. update the plan;
3. preserve the architectural goal:
   - shared analyzer logic;
   - explicit runtime boundary;
   - canonical models;
   - differential testing;
   - minimal compatibility surface.

Do not broaden scope merely to make the original design look correct.
