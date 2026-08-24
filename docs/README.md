# Adaptive Table Health Score Calculator

An implementation of the usage-conditioned health scoring system for analytical tables (e.g., Apache Iceberg) as described in the specification.

## Overview

This system computes table-level health scores by combining structural health indicators with workload-derived usage signals. Unlike static scoring systems, this approach:

- **Separates quality from operational relevance** - Metric quality and relevance are computed independently
- **Adapts to workload behavior** - Metric weights are modulated based on observed execution cost
- **Preserves explainability** - Deterministic subscores with clear attribution
- **Uses engine-reported metadata** - All inputs come from execution engine telemetry

## Key Innovation

The central insight is that **metric quality and metric relevance are orthogonal concerns**:

- **Quality**: How well does the table conform to design expectations?
- **Relevance**: How much does deviation from those expectations affect observed workload cost?

## Installation

No external dependencies required - uses only Python standard library.

```bash
# Clone or copy the files to your workspace
# No pip install needed
```

## Usage

### Basic Example

```python
from health_score_calculator import HealthScoreCalculator, UsageSignals
from usage_signal_calculators import UsageSignalCalculator, DeleteOverheadMetrics

# Calculate usage signal for delete overhead
calculator = UsageSignalCalculator()
delete_metrics = DeleteOverheadMetrics(
    delete_file_bytes=23_529_021,
    data_file_bytes=4_621_100_465,
    queries_touching_deletes=100,
    total_queries=100
)
u_delete = calculator.compute_delete_overhead_usage(delete_metrics)

# Create usage signals
usage_signals = UsageSignals(
    file_size=0.0,
    scan_efficiency=0.0,
    delete_overhead=u_delete,
    manifest_organization=0.0,
    partition_aware=0.0
)

# Compute health score
health_calc = HealthScoreCalculator()
result = health_calc.compute_health_score(usage_signals)

print(f"Overall Health: {result.overall_health:.2f}")
```

### Run Examples

```bash
python example_usage.py
```

This will run three examples:
1. **Baseline delete overhead** (from spec Section 7.6) - Expected: ≈99.5
2. **Degraded delete overhead** (from spec Section 7.7) - Expected: ≈95.6
3. **Comprehensive example** with all metrics active

## Components

### 1. Health Score Calculator (`health_score_calculator.py`)

Core computation engine that:
- Computes subscores from usage signals: `s_i = 1 / (1 + u_i)`
- Adjusts baseline weights based on usage: `w_i^adj = w_i^base * (1 + u_i)`
- Normalizes weights to sum to 1
- Computes final health score: `Health = 100 * sum(w_i^final * s_i)`

### 2. Usage Signal Calculators (`usage_signal_calculators.py`)

Implements usage signal computation for each metric:

#### File Size Optimization
- **Failure Mode**: Excessive task scheduling overhead due to suboptimal file granularity
- **Formula**: `u_file = observed_total_task_time / ideal_total_task_time`

#### Scan Efficiency
- **Failure Mode**: Read amplification from ineffective pruning
- **Formula**: `u_scan = files_scanned / files_required`

#### Delete Overhead
- **Failure Mode**: Additional scan cost from merge-on-read delete processing
- **Formula**: `u_delete = delete_exposure × delete_cost_ratio`
  - `delete_cost_ratio = delete_file_bytes / (delete_file_bytes + data_file_bytes)`
  - `delete_exposure = queries_touching_deletes / total_queries`

#### Manifest Organization
- **Failure Mode**: Excessive metadata traversal during query planning
- **Formula**: `u_manifest = table_hotness × planning_cost_ratio`
  - `table_hotness = query_executions / max_observed`
  - `planning_cost_ratio = planning_time / expected_planning_time`

#### Partition-Aware Metrics
- **Failure Mode**: Excessive scanning from ineffective partition pruning
- **Formula**: `u_partition = partition_exposure × partition_cost_ratio`
  - `partition_cost_ratio = partitions_scanned / total_partitions`
  - `partition_exposure = partition_sensitive_queries / total_queries`

## Mathematical Framework

For each health category `i`:

1. **Baseline Weight** (`w_i^base`): Encodes inherent structural severity
2. **Usage Signal** (`u_i ∈ [0,1]`): Derived from workload behavior
3. **Subscore** (`s_i = 1/(1+u_i)`): Remaining structural health
4. **Adjusted Weight** (`w_i^adj = w_i^base * (1+u_i)`): Usage-conditioned importance
5. **Final Weight** (`w_i^final = w_i^adj / sum(w_j^adj)`): Normalized
6. **Health Score** (`Health = 100 * sum(w_i^final * s_i)`): Final score

## Advantages Over Prior Art

- **Dynamic relevance** without redefining metric semantics
- **Cost-based scoring**, not symptom-based
- **Engine-observable** and explainable
- **Extensible** to additional metrics without changing core logic

## File Structure

```
smart_table_analyzer/
├── health_score_calculator.py      # Core scoring engine
├── usage_signal_calculators.py     # Metric-specific calculators
├── example_usage.py                # Example demonstrations
├── requirements.txt               # Dependencies (none required)
├── README.md                       # This file
└── spec/
    └── health_score.md             # Original specification
```

## Extending the System

To add a new metric:

1. Add a new dataclass in `usage_signal_calculators.py` for the metric's inputs
2. Implement a static method `compute_<metric>_usage()` following the pattern:
   - Identify the failure mode
   - Define exposure and cost intensity components
   - Apply formula: `Usage Relevance = Exposure × Cost Intensity`
3. Add the metric to `UsageSignals` dataclass
4. Add baseline weight to `HealthScoreCalculator.BASELINE_WEIGHTS`

## License

This implementation is based on the specification provided and is intended for internal use.
