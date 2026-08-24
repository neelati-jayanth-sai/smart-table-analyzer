# Scan Efficiency and Sort Order: What's Needed to Fix

## Current State
Both `scan_efficiency` and `sort_order` are hardcoded to `50.0` in the baseline scoring. This is a placeholder because these dimensions require data that isn't currently collected.

## What's Needed Conceptually

### Scan Efficiency Requirements

**Data Sources Needed:**

1. **Historical Query Data**
   - What queries have been run against this table recently
   - Which columns are actually being accessed in queries
   - What predicates/filters are commonly used
   - Query execution plans showing actual vs. expected data scanned

2. **Current Table Configuration**
   - File format being used (Parquet, ORC, etc.)
   - Compression settings
   - Row group size configuration
   - Z-ordering configuration (if any)
   - Bloom filter configuration (if any)

3. **Runtime Statistics**
   - Column pruning ratios (columns read vs. columns needed)
   - Row group hit rates (how effectively predicates filter data)
   - File scan ratios (files scanned vs. files needed)
   - Compression ratios (actual vs. theoretical)

**Metrics to Calculate:**

```
Column Pruning Score = (Columns Needed / Columns Actually Read) × 100
Row Group Filter Score = (Rows After Filter / Rows Scanned) × 100  
File Scan Score = (Files Needed / Files Scanned) × 100
Compression Score = (Uncompressed Size / Compressed Size) × 100
Overall Scan Efficiency = Weighted Average of above scores
```

**Key Insight:** Scan efficiency cannot be determined from table metadata alone. It requires **query execution data** to understand how the table is actually being used.

### Sort Order Requirements

**Data Sources Needed:**

1. **Current Table Configuration**
   - What columns is the table currently sorted by (if any)
   - Z-ordering configuration (which columns, in what order)
   - Local sorting within partitions
   - Sort order versioning (has it changed over time)

2. **Query Pattern Analysis**
   - What columns are commonly used in:
     - Range predicates (BETWEEN, >, <, >=, <=)
     - Join conditions
     - GROUP BY operations
     - ORDER BY operations
   - Cardinality of columns used in predicates
   - Selectivity of predicates

3. **Performance Correlation**
   - Query execution times vs. sort order alignment
   - Whether sorted columns reduce file scans
   - Impact of sort order on join performance

**Metrics to Calculate:**

```
Sort Alignment Score = (Queries Using Sorted Columns / Total Queries) × 100
Range Predicate Score = (Range Predicates on Sorted Columns / Total Range Predicates) × 100
Join Optimization Score = (Joins on Sorted Columns / Total Joins) × 100
Overall Sort Order Score = Weighted Average of above scores
```

**Key Insight:** Sort order effectiveness requires understanding **how the table is queried** to determine if the current sort order is optimal.

## Implementation Requirements (No Code Changes)

### Infrastructure Requirements

1. **Query Logging System**
   - Capture all queries run against the table
   - Log query execution plans
   - Track columns accessed, predicates used, execution time
   - Store historical query patterns

2. **Configuration Discovery**
   - Parse table DDL to extract sort order configuration
   - Discover Z-ordering and Bloom filter settings
   - Track configuration changes over time

3. **Statistics Collection**
   - Collect runtime statistics from query execution
   - Measure column pruning effectiveness
   - Track row group filter rates
   - Monitor file scan patterns

4. **Pattern Analysis**
   - Analyze historical query patterns
   - Identify common predicates and join patterns
   - Correlate query patterns with table configuration
   - Generate recommendations based on usage patterns

### Data Requirements

**Query Execution Data:**
```
For each query:
- Query text
- Execution plan
- Columns accessed
- Predicates used
- Rows scanned vs. rows returned
- Files scanned vs. files needed
- Execution time
- Timestamp
```

**Table Configuration Data:**
```
Current table state:
- Sort order columns
- Z-ordering columns
- Bloom filter columns
- Row group size
- Compression settings
- File format
```

**Historical Configuration Data:**
```
Configuration changes over time:
- When sort order changed
- When Z-ordering was added/modified
- When compression settings changed
```

### Integration Points

**With Alation (if available):**
- Query popularity and frequency
- Common join patterns
- Popular columns
- Downstream table dependencies

**With IOMETE Platform:**
- Query execution logs
- Table access patterns
- Performance metrics
- Configuration history

**With Iceberg Metadata:**
- Current snapshot configuration
- Partition evolution history
- Schema evolution history

## Scoring Logic (Conceptual)

### Scan Efficiency Scoring

```
IF historical query data exists:
    column_pruning_score = calculate_column_pruning_efficiency()
    row_group_score = calculate_row_group_filter_efficiency()
    file_scan_score = calculate_file_scan_efficiency()
    compression_score = calculate_compression_efficiency()
    
    scan_efficiency = weighted_average([
        (column_pruning_score, 0.3),
        (row_group_score, 0.3),
        (file_scan_score, 0.2),
        (compression_score, 0.2)
    ])
ELSE:
    scan_efficiency = 50.0  # Cannot determine without query data
```

### Sort Order Scoring

```
IF table has sort order AND historical query data exists:
    alignment_score = calculate_sort_alignment_with_queries()
    range_predicate_score = calculate_range_predicate_benefit()
    join_optimization_score = calculate_join_optimization_benefit()
    
    sort_order_score = weighted_average([
        (alignment_score, 0.4),
        (range_predicate_score, 0.3),
        (join_optimization_score, 0.3)
    ])
ELSE IF table has no sort order:
    sort_order_score = 50.0  # Neutral - neither good nor bad
ELSE:
    sort_order_score = 50.0  # Cannot determine without query data
```

## What This Means

### Short Term (Current System)
- Keep placeholder scores of 50.0
- Acknowledge these dimensions cannot be properly scored without additional data
- Focus investigation on dimensions that can be measured from table metadata alone

### Medium Term (With Query Logging)
- Implement query logging to capture execution data
- Calculate real scan efficiency scores
- Calculate real sort order scores based on query patterns
- Provide actionable recommendations based on actual usage

### Long Term (Full Integration)
- Integrate with Alation for query pattern analysis
- Integrate with IOMETE platform for execution metrics
- Provide continuous monitoring and optimization suggestions
- Track score improvements over time

## Conclusion

The fundamental issue is that **scan efficiency and sort order are usage-dependent metrics**. They cannot be determined from table metadata alone - they require understanding how the table is actually queried.

To fix these properly, the system needs:
1. **Query execution data** (what queries are run, how they perform)
2. **Configuration discovery** (what sorting/z-ordering exists)
3. **Pattern analysis** (how usage patterns align with configuration)

Without these data sources, the 50.0 placeholder is appropriate - it indicates "we cannot determine this score" rather than providing a misleading number.
