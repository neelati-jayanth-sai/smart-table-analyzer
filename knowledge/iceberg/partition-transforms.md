# Partition Transforms in Apache Iceberg

## Overview

Partition transforms in Apache Iceberg define how source column values are converted into partition values. Unlike traditional partitioning systems where you manually specify partition values, Iceberg applies transformation functions to source data, making partitioning more maintainable and less error-prone.

## Supported Transforms

### Identity Transform
- **Usage:** `identity`
- **Behavior:** Uses the source value directly as the partition value
- **Best for:** Low-cardinality categorical data (region, status, type)
- **Example:** `PARTITIONED BY (category)` where category values become partition values as-is

### Bucket Transform
- **Usage:** `bucket[N]` where N is the number of buckets
- **Behavior:** Applies a hash function to the source value and computes modulo N
- **Best for:** High-cardinality columns (IDs, UUIDs) to achieve uniform distribution
- **Example:** `bucket[16]` on user_id distributes data across 16 partitions
- **Note:** Bucket transform is stable across spec evolution

### Truncate Transform
- **Usage:** `truncate[W]` where W is the truncation width
- **Behavior:** Truncates strings to W characters or numbers to W units
- **Best for:** String prefixes or numeric ranges
- **Example:** `truncate[4]` on "2024-01-15" becomes "2024"

### Time-Based Transforms
- **Year:** `year` - Extracts year from timestamp/date
- **Month:** `month` - Extracts year and month from timestamp/date  
- **Day:** `day` - Extracts year, month, and day from timestamp/date
- **Hour:** `hour` - Extracts year, month, day, and hour from timestamp

**Best for:** Time-series data where queries filter by time ranges

## Transform Properties

### Determinism
All partition transforms are deterministic: the same input always produces the same partition value. This is critical for predicate pushdown and partition pruning.

### Hidden Partitioning
Users query using source column values (e.g., `WHERE event_date = '2024-01-15'`), and Iceberg automatically translates this to the appropriate partition filter. Users never need to know the partition scheme.

### Multi-Argument Transforms (V3)
Starting in format V3, transforms can accept multiple source columns using `source-ids` instead of `source-id`. Single-argument transforms continue using `source-id`.

## Common Pitfalls

### Over-Partitioning
- **Problem:** Using identity transform on high-cardinality columns creates too many small partitions
- **Symptom:** Thousands of tiny files, slow metadata operations
- **Fix:** Use bucket[N] or time-based transforms to reduce partition count

### Under-Partitioning  
- **Problem:** Too few partitions mean poor query pruning
- **Symptom:** Queries scan entire table even with selective predicates
- **Fix:** Increase partition granularity (e.g., day instead of month)

### Wrong Transform Choice
- **Problem:** Using bucket transform on time columns loses time-based pruning benefits
- **Symptom:** Cannot prune by time ranges efficiently
- **Fix:** Use time-based transforms (day, hour) for timestamp columns

### Bucket Count Mismatch
- **Problem:** Choosing bucket count that doesn't match data distribution or query patterns
- **Symptom:** Uneven partition sizes, skewed queries
- **Fix:** Choose bucket count based on expected cardinality and parallelism needs (powers of 2 work well: 8, 16, 32)

## Partition Spec Evolution

When you change a table's partition spec, Iceberg doesn't rewrite existing data. Old files stay with their original partition spec, new files use the new spec. Each manifest file tracks which spec it uses.

**Key behavior:**
- Old manifests continue using the old spec
- New writes use the new spec  
- Queries work seamlessly across both by applying appropriate transformations

**Best practice:** Plan your initial partition strategy carefully, as evolution adds complexity to metadata management.

## Field ID Assignment

In V1, partition field IDs started sequentially at 1000 for each spec. In V2 and V3, field IDs are explicitly assigned and tracked in the partition spec JSON.

## Query Planning Implications

Partition transforms enable predicate pushdown at manifest scan time:
1. Query predicate on source column (e.g., `event_date >= '2024-01-01'`)
2. Iceberg transforms predicate to partition space (e.g., `day(event_date) >= 19723`)
3. Manifest scan skips manifests/files that don't match
4. Only relevant files are read

This works because transforms preserve ordering for time-based transforms and bucketing provides uniform distribution.

## Examples

### E-commerce table with multiple transforms

```sql
CREATE TABLE orders (
    order_id BIGINT,
    customer_id BIGINT,
    order_date DATE,
    region STRING,
    total DECIMAL(10,2)
)
PARTITIONED BY (
    days(order_date),  -- Day granularity for time queries
    bucket(16, customer_id),  -- Distribute customers evenly
    region  -- Identity for region filtering
)
```

### Timeseries data with hourly partitions

```sql
CREATE TABLE events (
    event_id STRING,
    event_timestamp TIMESTAMP,
    user_id BIGINT,
    event_type STRING
)
PARTITIONED BY (
    hours(event_timestamp),  -- Hourly granularity
    bucket(32, user_id)  -- User distribution
)
```

## Version Compatibility

- **V1:** All basic transforms supported; partition field IDs auto-assigned starting at 1000
- **V2:** Explicit field ID tracking; all transforms supported
- **V3:** Multi-argument transforms supported via `source-ids`; readers must gracefully handle unknown transforms

Unknown transforms in V3 are ignored by readers (not an error), but writers should not use unknown transforms to maintain compatibility.

---

## Provenance

**Based on:**
- `format/spec.md` (Apache Iceberg) - Specification > Table Metadata > Partition Specs
- `format/spec.md` - Appendix C: JSON serialization > Partition Specs (lines 1697-1737)
- Iceberg repository commit: `c62a8fc3ee808e95d5493e4ffd19642ac22ea82f`

**Source extracts:**
- `knowledge/iceberg/tree/format/spec-md/iceberg-table-spec/appendix--ee218b8e/partition-specs/README.md`
- `knowledge/iceberg/tree/format/spec-md/iceberg-table-spec/specification/table-metadata/partition-4ae0ff7f/partition-97eb5e89/README.md`
