# Sort Order Optimization in Apache Iceberg

## Overview

Sort order defines how rows are physically ordered within data files. While optional, specifying a sort order can dramatically improve query performance through better data clustering and more effective min/max filtering.

## What Sort Order Controls

Sort order affects:
- **Physical row ordering** within each data file
- **Min/max statistics effectiveness** for filtering
- **Data clustering** for range queries
- **Compression ratios** (similar values compress better)

Sort order does NOT affect:
- Partition layout (controlled by partition spec)
- Row ordering across files (each file is independent)
- Query result ordering (queries still need ORDER BY)

## Defining Sort Order

Sort orders are specified at table creation or via ALTER TABLE:

```sql
CREATE TABLE events (
    event_id BIGINT,
    user_id BIGINT,
    event_timestamp TIMESTAMP,
    event_type STRING
)
PARTITIONED BY (days(event_timestamp))
SORTED BY (event_type, event_timestamp);
```

### Sort Fields
Each sort field specifies:
- **Source column** or **transform**
- **Sort direction:** ASC (ascending) or DESC (descending)
- **Null ordering:** NULLS FIRST or NULLS LAST

### Multi-Column Sort
Sort order is applied lexicographically:
1. Sort by first field
2. Within ties, sort by second field
3. Continue for remaining fields

**Example:** `SORTED BY (region, user_id)` groups all rows for each region together, then sorts by user_id within each region.

## When Sort Order Helps

### Use Case: Range Queries
**Scenario:** Queries filter on a high-cardinality column

```sql
SELECT * FROM events WHERE event_id BETWEEN 1000 AND 2000;
```

**Benefit:** Sorted data has tight min/max bounds per file, enabling file-level pruning

### Use Case: Join Optimization
**Scenario:** Tables joined on sorted column

```sql
SELECT * FROM orders o JOIN items i ON o.order_id = i.order_id;
```

**Benefit:** If both tables sorted by join key, readers can use sorted merge join

### Use Case: Frequent GROUP BY
**Scenario:** Aggregation queries on specific columns

```sql
SELECT user_id, COUNT(*) FROM events GROUP BY user_id;
```

**Benefit:** Sorted data allows streaming aggregation without buffering all groups

### Use Case: Time-Series Access Patterns
**Scenario:** Recent data queried more frequently

```sql
SELECT * FROM logs WHERE log_timestamp > NOW() - INTERVAL '1 hour';
```

**Benefit:** `SORTED BY (log_timestamp DESC)` puts recent data first, improving cache hits

## When Sort Order Doesn't Help

### Random Point Lookups
If queries filter on random keys with no range patterns, sort order provides minimal benefit.

### Full Table Scans  
Queries without filters or with low selectivity scan entire table regardless of sort order.

### Extremely High Cardinality
Sorting on UUID or random hash provides little clustering benefit.

## Sort Order Transforms

You can sort by partition transforms, not just raw column values:

```sql
SORTED BY (bucket(16, user_id), event_timestamp)
```

**Benefit:** Groups data by bucketed partition value first, then sorts within bucket.

## Write-Time Cost

Applying sort order has costs:
- **CPU:** Sorting rows before writing
- **Memory:** Buffering rows to sort (configured by `write.sort.memory-limit`)
- **Write latency:** Sorting delays file writes

**Tradeoff:** Write-time cost vs. read-time benefit. Worth it if queries benefit from filtering/clustering.

## Sort Order Evolution

Tables can change sort order via ALTER TABLE:

```sql
ALTER TABLE events SET SORT ORDER (user_id, event_timestamp);
```

**Behavior:**
- New files written with new sort order
- Old files keep original sort order (never rewritten automatically)
- Sort order ID tracked in file metadata

**Implication:** Table can have files with different sort orders. This is normal and expected.

## Common Pitfalls

### Pitfall: Sorting on Partition Column
**Problem:** Sorting by column already used for partitioning
**Impact:** Redundant (partition already clusters data by that column)
**Fix:** Sort by other high-value columns within partitions

### Pitfall: Too Many Sort Fields
**Problem:** Sorting by 5+ columns
**Impact:** Diminishing returns; later fields barely affect clustering
**Fix:** Limit to 2-3 most selective columns

### Pitfall: Wrong Sort Direction
**Problem:** Using ASC when queries filter for recent data
**Impact:** Recent data scattered across files instead of clustered
**Fix:** Use DESC for timestamp columns when queries favor recent data

### Pitfall: Ignoring Write Cost
**Problem:** Sorting on every write for streaming table with low query selectivity
**Impact:** High write latency, wasted CPU
**Fix:** Skip sort order for tables with full-scan access patterns

## Monitoring Sort Effectiveness

```sql
-- Check sort order configuration
SELECT * FROM table.metadata.sort_orders;

-- Check if files use sort order (via sort_order_id in file metadata)
SELECT 
    sort_order_id,
    COUNT(*) as file_count,
    SUM(record_count) as total_rows
FROM table.metadata.files
GROUP BY sort_order_id;
```

### Effectiveness Signals
- **Pruning improvement:** Queries filter more files after adding sort order
- **Compression improvement:** File sizes decrease due to better compression
- **Scan reduction:** Queries read fewer rows per file (tighter min/max bounds)

## Best Practices

### Identify High-Value Sort Columns
1. Analyze query WHERE clauses (most filtered columns)
2. Check join predicates (join key columns)
3. Review GROUP BY fields (aggregation columns)
4. Prioritize columns with range queries over point lookups

### Start Simple
- Begin with 1-2 sort fields
- Measure query improvement
- Add more fields only if measurable benefit exists

### Coordinate with Partitioning
- Partition by time, sort by next-most-selective column
- Avoid sorting by partition column

### Consider Access Patterns
- **OLTP-style:** Sort by primary key or frequent lookup column
- **OLAP-style:** Sort by common filter/group-by columns
- **Time-series:** Sort by timestamp DESC if recent data queried most

---

## Provenance

**Based on:**
- `format/spec.md` (Apache Iceberg) - Appendix C > Sort Orders
- Iceberg repository commit: `c62a8fc3ee808e95d5493e4ffd19642ac22ea82f`

**Source extracts:**
- `knowledge/iceberg/tree/format/spec-md/iceberg-table-spec/appendix--ee218b8e/sort-orders/README.md`
