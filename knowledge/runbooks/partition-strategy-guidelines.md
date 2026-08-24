# Partition Strategy Guidelines

## Overview

This runbook documents team conventions for choosing partition strategies for Iceberg tables on the IOMETE platform. Following these guidelines ensures consistent table design and reduces operational issues.

## Decision Tree

### Step 1: Identify Primary Access Pattern

- **Time-based queries:** Use time-based partitioning (day, month). This is the default and preferred approach.
- **Categorical queries:** Use identity partitioning for low-cardinality dimensions.
- **High-Cardinality Point Lookups:** Use bucket partitioning ONLY if time-based partitioning is insufficient or if queries frequently filter on a specific ID.
- **Full scans:** Consider unpartitioned

### Step 2: Estimate Cardinality

- **Low (< 100 values):** Identity transform safe
- **Medium (100-1,000 values):** Identity safe, or bucket if explicitly needed for uniform distribution
- **High (> 1,000 values):** Do NOT partition by this column unless absolutely necessary. If partitioning is strictly required (e.g., for frequent point lookups), use a Bucket transform.

### Step 3: Consider Data Volume

- **Small (< 100 GB):** Coarser partitioning acceptable
- **Medium (100 GB - 1 TB):** Standard partitioning (e.g., daily)
- **Large (> 1 TB):** Fine partitioning (e.g., hourly) or multi-column

## Standard Patterns by Table Type

### Event/Log Tables

**Characteristics:** Time-series data, frequent recent access, append-only

**Standard partition spec:**

```sql
PARTITIONED BY (days(event_timestamp))
```

**Alternative for high-volume:**

```sql
PARTITIONED BY (hours(event_timestamp))
```

**Sort order:**

```sql
SORTED BY (event_timestamp DESC, user_id)
```

### Fact Tables (OLAP)

**Characteristics:** Large volume, analytical queries, time and dimension filters

**Standard partition spec:**

```sql
PARTITIONED BY (
    days(transaction_date),
    bucket(16, customer_id)
)
```

**Sort order:**

```sql
SORTED BY (transaction_date DESC, product_id)
```

### Dimension Tables

**Characteristics:** Small to medium, lookup queries, slowly changing

**Standard partition spec:**

```sql
-- Usually unpartitioned due to small size
-- If partitioned:
PARTITIONED BY (region)  -- Low cardinality category
```

### User Activity Tables

**Characteristics:** High cardinality user dimension, time-based queries

**Standard partition spec:**

```sql
PARTITIONED BY (
    days(activity_date),
    bucket(32, user_id)
)
```

## Partition Granularity Standards

### Time-Based Granularity

| Data Volume/Day | Query Pattern | Recommended Granularity |
|-----------------|---------------|-------------------------|
| < 1 GB | Daily/weekly queries | Monthly |
| 1-10 GB | Daily queries | Daily |
| 10-100 GB | Hourly queries | Daily (or hourly if selective) |
| > 100 GB | Real-time/streaming | Hourly |

### Bucketing Standards

| Cardinality | Typical Use Case | Bucket Count |
|-------------|------------------|--------------|
| < 1,000 | Small user base | 8 |
| 1,000-100,000 | Medium user base | 16 |
| 100,000-1M | Large user base | 32 |
| > 1M | Very large user base | 64 |

**Rule:** Bucket count should be power of 2 for even distribution

## Multi-Column Partitioning Order

**General rule:** Order by query selectivity (most selective first)

**Exception:** Always put time dimension first for time-series tables

**Example (correct):**

```sql
PARTITIONED BY (
    days(event_date),      -- Queries always filter by date
    bucket(16, user_id),   -- Secondary distribution
    region                 -- Tertiary filter (if used)
)
```

**Example (incorrect):**

```sql
PARTITIONED BY (
    region,                -- Low selectivity
    days(event_date)       -- High selectivity but second
)
```

## Anti-Patterns

### Anti-Pattern 1: High-Cardinality Identity

**Bad:**

```sql
PARTITIONED BY (user_id)  -- Millions of partitions
```

**Good:**

```sql
PARTITIONED BY (bucket(32, user_id))
```

### Anti-Pattern 2: No Partitioning on Large Tables

**Bad:**

```sql
CREATE TABLE events (...);  -- 500 GB table, no partitions
```

**Good:**

```sql
CREATE TABLE events (...) PARTITIONED BY (days(event_date));
```

### Anti-Pattern 3: Over-Partitioning

**CRITICAL RULE:** NEVER recommend more than 2 partition columns. 3+ is a severe anti-pattern that multiplies into millions of micro-partitions and destroys query performance.
- Pick the SINGLE best time-based column for the primary partition.
- Only add a secondary partition if absolutely necessary for a secondary access pattern.
- Do NOT just list every valid candidate you found.

**Bad:**

```sql
PARTITIONED BY (
    hours(event_timestamp),
    region,
    product_category,
    user_tier
)  -- 4 dimensions = explosion of partitions
```

**Good:**

```sql
PARTITIONED BY (
    days(event_timestamp),
    bucket(16, CONCAT(region, product_category))
)
```

### Anti-Pattern 4: Unnecessary Bucketing
**CRITICAL RULE:** Do NOT blindly suggest bucket partitioning just because a high-cardinality column exists.
- If a table already has a good time-based or low-cardinality categorical partition column, bucketing is usually unnecessary and adds overhead.
- Only suggest bucketing if: (A) there is no other viable partition column, or (B) the table is massive and requires compound partitioning (e.g., `day(time_col)` + `bucket(id_col)`), or (C) query logs prove frequent point-lookups on the ID column.

**Bad:**

```sql
-- Adding a bucket partition just because user_id exists in the schema
PARTITIONED BY (days(event_timestamp), bucket(16, user_id)) 
```

**Good:**

```sql
-- Keeping it simple when data volume per day is manageable
PARTITIONED BY (days(event_timestamp))
```

## Change Management

### When to Evolve Partition Spec

- Data volume increased 10x since table creation
- Query patterns changed significantly
- Partition count > 10,000 (too many) or < 10 (too few)

### Process for Partition Evolution

1. **Analyze current state:** File count, partition count, query patterns
2. **Propose new spec:** Document in team wiki with rationale
3. **Test on subset:** Create test table with new spec, validate performance
4. **Plan migration:** Schedule rewrite during low-traffic window
5. **Execute:** Use migration pattern from `partition-evolution-limitations.md`
6. **Monitor:** Compare query performance before/after

## Platform-Specific Considerations (IOMETE)

### Respect Planner Limits

- Keep total partition count < 10,000 (planner uses approximate pruning above this)
- Keep partition spec count < 3 (multiple specs slow planning)

### Coordinate with Compaction

- IOMETE compaction jobs work best with homogeneous partition specs
- Avoid partition evolution shortly before scheduled compaction

### Metadata Cache Warm-up

- First query after partition evolution may be slow (cache miss)
- Pre-warm cache with lightweight query after DDL changes

## Documentation Requirements

When creating a new table, document partition strategy in table comment:

```sql
COMMENT ON TABLE db.table IS 'Event log table.
Partition strategy: Daily time + 16-bucket user distribution.
Rationale: 10 GB/day ingest, queries filter by date + user.
Reviewed: 2024-01-15';
```

## Review Checklist

Before finalizing partition strategy:
- [ ] Estimated partition count within acceptable range (10-1,000)
- [ ] Primary query filter columns included in partition spec
- [ ] Partition order aligns with query selectivity
- [ ] Table comment documents strategy and rationale
- [ ] Tested on sample data or similar table
- [ ] Platform-specific constraints considered

---

## Provenance

**Based on:**
- Team operational experience with Iceberg tables on IOMETE
- Lessons learned from production table performance issues
- Apache Iceberg partitioning best practices adapted to team context

**Source:** Team runbook, maintained by data platform team
