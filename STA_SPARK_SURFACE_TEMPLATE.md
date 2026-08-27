# STA_SPARK_SURFACE.md
## Smart Table Analyzer Spark/Iceberg Dependency Audit

> This file must be generated from the real repository before major refactoring.
> Do not fill it with assumptions.

---

# 1. Summary

Record:

```text
Total Spark-related call sites:
Distinct Spark APIs:
Distinct Spark SQL patterns:
Distinct Iceberg metadata tables:
Distinct Spark configuration keys:
Distinct write/mutation paths:
Distinct maintenance/procedure calls:
```

Provide an overall conclusion:

```text
Metadata-centric / Compute-centric / Spark-coupled / Mixed
```

---

# 2. Dependency Inventory

| ID | File | Line/Function | Operation | Category | Purpose | Frequency | Input | Output | Local Candidate | Risk | Notes |
|---|---|---|---|---|---|---:|---|---|---|---|---|
| S001 | | | | | | | | | | | |

Categories:

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

---

# 3. SparkSession Usage

Document every use of:

```text
SparkSession
builder
getOrCreate
config
session-scoped configuration
```

For each, answer:

- Does STA business logic depend on this?
- Is it only bootstrap?
- Can it remain production-only?
- Does local testing need an equivalent?

---

# 4. spark.sql Usage

For every SQL string/template:

- include the query or normalized pattern;
- classify:
  - ordinary SQL;
  - Iceberg metadata query;
  - Spark-specific command;
  - maintenance procedure;
  - DDL;
  - DML;
- record result schema expectations;
- record whether analyzer logic depends on Spark-specific field names/types.

Do not merely count `spark.sql`.

Understand each query.

---

# 5. spark.table / spark.read Usage

Document:

```text
spark.table
spark.read
spark.read.format
load
table
option/options
```

For each call:

- source type;
- table identifier format;
- operations performed afterward;
- whether direct DataFrame compatibility is actually required.

---

# 6. DataFrame API Surface

List every DataFrame method used.

| Method | Count | Files | Complexity | SQLFrame Candidate? | Runtime Method Candidate? |
|---|---:|---|---|---|---|
| select | | | | | |
| filter | | | | | |
| groupBy | | | | | |
| agg | | | | | |
| join | | | | | |
| withColumn | | | | | |

Also list:

- actions (`collect`, `count`, `show`, etc.);
- conversion methods;
- persistence/cache operations;
- repartition/coalesce if any.

---

# 7. pyspark.sql.functions Surface

Inventory every function.

Examples:

```text
col
lit
count
countDistinct
avg
min
max
when
explode
struct
array
date_trunc
to_date
percentile_approx
```

For each:

- location;
- use case;
- whether it can be represented as a runtime-level operation;
- whether SQLFrame supports it;
- whether DuckDB has a semantic equivalent.

---

# 8. Window Functions

Document every use of:

```text
Window
row_number
rank
dense_rank
lag
lead
partitionBy
orderBy
```

Assess whether these are core analyzer logic or implementation detail.

---

# 9. Iceberg Metadata Surface

Inventory use of:

```text
.files
.partitions
.snapshots
.history
.manifests
.entries
.refs
.metadata_log_entries
.delete_files
.all_files
.all_entries
```

For each:

- Spark query;
- fields consumed by STA;
- PyIceberg inspection equivalent;
- known representation differences;
- compatibility risk.

---

# 10. Iceberg Procedures

Inventory any use of:

```text
rewrite_data_files
rewrite_manifests
expire_snapshots
remove_orphan_files
rollback_to_snapshot
set_current_snapshot
```

Classify each as:

```text
analysis-only need
actual execution need
unused/dead
```

Do not implement local execution unless STA genuinely requires it.

---

# 11. Catalog Configuration

Inventory:

```text
spark.sql.catalog.*
warehouse
uri
catalog implementation
authentication
case sensitivity
namespace handling
```

Determine what is:

- production bootstrap only;
- relevant to local integration tests;
- irrelevant to analyzer logic.

---

# 12. Spark-Specific Types

Document any dependence on:

```text
Row
StructType
StructField
ArrayType
MapType
DecimalType
TimestampType
```

Determine whether these leak into analyzer or Investigator layers.

---

# 13. Error Handling

Document Spark/Iceberg exceptions that alter analyzer behavior.

Examples:

```text
table not found
namespace not found
permission denied
unsupported operation
analysis exception
query failure
```

Determine whether local runtime needs equivalent canonical errors.

---

# 14. Writes and Mutations

Document:

```text
write
writeTo
saveAsTable
append
overwrite
merge
update
delete
alter
create
drop
```

For each:

- production purpose;
- whether STA requires it;
- whether only fixture generation needs it.

---

# 15. Test Dependencies

Document current tests that:

- mock Spark;
- require a SparkSession;
- depend on static metadata;
- depend on real Iceberg state;
- test Investigator;
- test Legacy Analyzer.

Identify which tests should become:

```text
unit
local integration
conformance
```

---

# 16. Hotspots

Identify files with the highest Spark coupling.

| File | Spark Call Sites | Severity | Refactor Priority |
|---|---:|---|---|
| | | | |

---

# 17. Candidate Runtime Operations

Only after completing the audit, propose runtime methods.

| Runtime Method | Existing Call Sites | Why Needed | Production Implementation | Local Implementation |
|---|---|---|---|---|
| | | | | |

If a method has no existing call site, do not add it without explicit justification.

---

# 18. SQLFrame Candidates

List only DataFrame-heavy areas that would benefit from preserving PySpark syntax.

For each:

- exact transformation;
- Spark expected result;
- SQLFrame/DuckDB result;
- parity status;
- type differences;
- recommendation:
  - adopt;
  - rewrite behind runtime;
  - Spark-only.

---

# 19. Architectural Conclusion

Answer directly:

1. Is STA primarily metadata-centric?
2. How much of STA actually needs Spark DataFrames?
3. How much can PyIceberg cover?
4. How much compute can DuckDB cover?
5. Is SQLFrame necessary?
6. Are any Spark semantics impossible to abstract safely?
7. Is the runtime project still justified?
8. Estimated compatibility surface: small / medium / large / unacceptable.

---

# 20. Go / No-Go

Conclude one of:

```text
GO
GO WITH REDUCED SCOPE
REFACTOR STA FIRST
NO-GO
```

Explain why using evidence from the audit.
