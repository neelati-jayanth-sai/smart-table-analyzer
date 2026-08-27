# CODEX_GOAL.md
## Goal: Make Smart Table Analyzer Realistically Testable Locally Without Spark

Read these files first:

```text
BUILD_SPEC.md
IMPLEMENTATION_PLAN.md
STA_SPARK_SURFACE.md   # generate this if it does not yet exist
```

Then inspect the full repository.

Your job is **not** to build a lightweight Spark clone.

Your job is to make the same Smart Table Analyzer business logic run against:

```text
Production:
Spark / Iomete / Iceberg
```

and:

```text
Local:
PyIceberg + DuckDB
```

through a small explicit runtime boundary and canonical domain models.

---

# Non-Negotiable Rules

1. **Audit before refactoring.**

   Generate `STA_SPARK_SURFACE.md` from the real repository.

2. **Do not invent a large runtime interface.**

   Derive `STA_RUNTIME_CONTRACT.md` only from actual STA usage.

3. **Implement the production adapter first.**

   Extract existing Spark/Iomete behavior behind the runtime without changing analyzer behavior.

4. **Use canonical models.**

   Analyzer and Investigator logic must not depend directly on Spark Row, Spark DataFrame, Arrow Table, or DuckDB relation objects.

5. **Use PyIceberg for local Iceberg metadata.**

6. **Use DuckDB for local analytical compute.**

7. **Evaluate SQLFrame only where existing PySpark DataFrame code makes it genuinely useful.**

   Do not make SQLFrame foundational by default.

8. **Do not build:**

```text
fake SparkSession
Spark SQL compatibility engine
generic SQL transpiler
custom DataFrame engine
custom query planner
Catalyst-like system
RDD support
Spark Connect
custom Iceberg metadata parser
custom Parquet reader
custom REST catalog
```

9. **Do not scatter `if local:` branches through business logic.**

   Environment differences belong in adapters.

10. **Do not silently normalize unsafe semantic differences.**

    Unknown local-vs-Spark divergence must fail strict conformance.

---

# Mandatory Execution Order

## Phase 1 — Audit

Search the repository for:

```text
SparkSession
spark.sql
spark.table
spark.read
spark.catalog
DataFrame methods
pyspark.sql.functions
Window
collect
toPandas
Spark Row/types
Iceberg metadata tables
Iceberg procedures
Spark config
catalog config
```

Generate:

```text
STA_SPARK_SURFACE.md
```

Do not refactor before this is complete.

---

## Phase 2 — Runtime Contract

Generate:

```text
STA_RUNTIME_CONTRACT.md
```

Every method must map to real audited STA use.

No speculative generic `.sql()` or `.execute()` methods unless required.

---

## Phase 3 — Canonical Models

Introduce the smallest canonical model set needed for:

```text
schema
files
partitions
snapshots
history
manifests
table properties
sampling/profiling
```

Preserve Iceberg identifiers:

```text
field_id
spec_id
snapshot_id
sequence_number
sort_order_id
```

Add unit tests.

---

## Phase 4 — SparkIometeRuntime

Wrap existing production behavior.

Migrate one capability at a time.

After each migration:

```text
run relevant tests
run production-path tests
verify analyzer output
```

Do not change analysis algorithms to make abstraction easier.

---

## Phase 5 — Real Iceberg Fixtures

Create real fixture scenarios.

Minimum:

```text
healthy_table
many_small_files
partition_skew
schema_evolution
partition_evolution
snapshot_buildup
```

Prefer declarative fixture definitions.

Do not mock final metadata results.

---

## Phase 6 — LocalIcebergRuntime

Implement one runtime method at a time.

Preferred:

```text
PyIceberg → metadata
DuckDB → compute
```

For each method:

```text
Spark expected canonical result
vs
Local canonical result
```

Add differential tests immediately.

---

## Phase 7 — SQLFrame Evaluation

Only for real existing DataFrame-heavy transformations.

Test actual transformations under SQLFrame/DuckDB.

Adopt selectively if parity is good and it reduces duplication.

Otherwise keep the transformation behind runtime methods or production-only if genuinely Spark-specific.

---

## Phase 8 — Analyzer Conformance

Run the same fixtures through STA with both runtimes.

Compare structured findings:

```text
issue type
severity
evidence
recommendation
important metrics
```

Do not compare LLM prose word-for-word.

Compare deterministic and structured outputs.

---

## Phase 9 — Known Differences

Create:

```text
KNOWN_DIFFERENCES.yaml
```

Every accepted difference needs:

```text
production behavior
local behavior
normalization rule
why safe
covering test
```

Do not add entries just to make tests green.

---

# Testing Requirements

Maintain three layers:

```text
1. Unit
2. Local integration
3. Differential conformance
```

Important edge cases must include:

```text
schema evolution
partition evolution
multiple spec IDs
position deletes
equality deletes
nested types
decimals
timestamps
null/NaN behavior
snapshot history
file metrics
```

---

# Self-Critique Requirement

At major milestones, ask:

1. Are we solving STA's testing problem or building a generic engine?
2. Is this abstraction proven necessary by current code?
3. Could an existing library own this layer?
4. Are we preserving behavior or merely syntax?
5. Can local passing tests create false confidence in production?
6. Is this new code more expensive to maintain than simply running Spark?
7. Are we adding compatibility behavior STA never uses?
8. Did a repository fact disprove an assumption from the spec?

If the answer indicates scope drift, reduce scope.

---

# Stop Conditions

Stop and document rather than expanding scope if:

```text
the runtime requires rewriting most STA business logic

a generic Spark SQL compatibility layer becomes necessary

Spark-specific distributed semantics dominate the application

local and Spark semantics diverge frequently and cannot be normalized safely

runtime maintenance becomes the majority of the project
```

If this happens, recommend the smallest corrective architecture rather than forcing the original plan.

---

# Definition of Done

Do not consider the task complete until:

- `STA_SPARK_SURFACE.md` is based on the real repository;
- `STA_RUNTIME_CONTRACT.md` exists and contains only proven necessary methods;
- production Spark/Iomete path still works;
- supported local tests run without Spark/JVM;
- at least six real Iceberg pathology fixtures exist;
- same analyzer business logic runs with both runtimes;
- supported runtime methods have differential conformance tests;
- structured analyzer findings are materially equivalent on supported fixtures;
- known differences are documented;
- analyzer business logic contains no environment-specific branching;
- no unnecessary general Spark compatibility subsystem was introduced;
- full relevant test suite passes.

---

# Working Style

Be empirical.

Read the repository deeply.

Run tests frequently.

Use small vertical migrations rather than a large rewrite.

Prefer deleting unnecessary abstraction over adding another layer.

When the repository contradicts the spec, treat the repository and observed behavior as evidence and update the plan.

The architectural goal remains:

> Shared analyzer logic, explicit runtime boundary, canonical Iceberg analysis models, real local Iceberg fixtures, and differential verification against production Spark/Iomete behavior.
