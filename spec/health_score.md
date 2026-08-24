Impact-Based Derivation of Composite Health Scores for Lakehouse Tables
Revision History

















VersionDateDescriptionAuthor/Editor1.0YYYY-MM-DDInitial draftFirst Last
Invention Disclosure
The Pan-Dell Patent Committee (PDPC) reviews disclosures originating from Boomi, Dell Digital, Dell Technologies Services, and P&O CTO teams, as well as disclosures outside the scope of other P&O product-based patent committees.
The invention disclosure described in this document falls into one of these categories and aligns with the Strategic Themes pursued annually by the Chief Technology Officer of Dell Technologies.
<add text introducing other organizations of other inventors>









































NameRole

Dell Confidential
The information contained in this document is Dell Confidential and intended only for the recipient. Do not copy, forward, or distribute this document to anyone other than the original recipient.
Contents

Technical Field
Problem Statement
Key Insight (Inventive Concept)
System Overview
Usage Signal Design Principle
Metric-Specific Usage Signals (Current Implementation)

6.1 File Size Optimization
6.2 Scan Efficiency
6.3 Delete File Overhead
6.4 Manifest Organization
6.5 Partition-Aware Metrics


Structural Health Score Computation under Delete Overhead
Non-Overlapping Cost Attribution
Advantages Over Prior Art
Status


Abstract
This disclosure presents a system for computing a table-level health score for versioned analytical tables, such as Apache Iceberg tables, in which structural health indicators are combined with workload-derived usage signals to dynamically adjust metric relevance.
Unlike static scoring systems, the proposed approach separates quality from operational relevance and modulates category influence based on empirically observed execution cost attributable to distinct failure modes.
The system preserves deterministic, explainable subscores while adapting to workload behavior using engine-reported execution metadata.
1. Technical Field
The invention relates to operational health assessment of analytical data tables, and more specifically to adaptive scoring of metadata-driven health metrics based on observed workload behavior.
2. Problem Statement
Existing table health scoring systems compute weighted sums of normalized metrics reflecting structural properties such as file size, delete files, manifests, and snapshots.
These systems suffer from three limitations:

Static importance assumptions – metric weights do not adapt to workload differences.
Symptom-based scoring – metrics reflect theoretical risk rather than observed cost.
Poor actionability – high scores may not correspond to operational pain.

As a result, identical health scores may represent vastly different operational realities.
3. Key Insight (Inventive Concept)
The central insight of this invention is:

Metric quality and metric relevance are orthogonal concerns and must be computed separately.


Quality answers: How well does the table conform to design expectations?
Relevance answers: How much does deviation from those expectations affect observed workload cost?

The invention introduces usage-conditioned weight modulation, in which metric relevance is derived from execution-engine-reported workload behavior corresponding to each metric's failure mode.
4. System Overview
For each health category i, the system maintains:
Fixed Baseline Weight
wibasew_{i}^{base}wibase​
Encodes the inherent structural severity of the category.
Usage Signal
ui∈[0,1]u_i \in [0,1]ui​∈[0,1]
Derived from workload behavior and table structure (e.g., exposure × cost ratio), representing structural pressure exerted by this category.
Deterministic Subscore
si=11+uis_i = \frac{1}{1+u_i}si​=1+ui​1​
The subscore represents remaining structural health along dimension i. Higher usage implies lower health.
Weight Adjustment
wiadj=wibase(1+ui)w_{i}^{adj}=w_{i}^{base}(1+u_i)wiadj​=wibase​(1+ui​)
Weight Normalization
wifinal=wiadj∑jwjadjw_{i}^{final}=\frac{w_{i}^{adj}}{\sum_j w_{j}^{adj}}wifinal​=∑j​wjadj​wiadj​​
Final Health Score
Health=100×∑i(wifinal⋅si)Health = 100 \times \sum_i (w_{i}^{final} \cdot s_i)Health=100×i∑​(wifinal​⋅si​)
5. Usage Signal Design Principle
Each usage signal quantifies:

Observed operational cost attributable to the failure mode of a specific health category.

All usage signals follow:
Usage Relevance=Exposure×Cost IntensityUsage\ Relevance = Exposure \times Cost\ IntensityUsage Relevance=Exposure×Cost Intensity
This avoids double-counting and preserves orthogonality.
6. Metric-Specific Usage Signals (Current Implementation)
6.1 File Size Optimization
Failure Mode
Excessive task scheduling and execution overhead due to suboptimal file granularity.
Usage Signal
ufile=observed_total_task_timeideal_total_task_timeu_{file}=
\frac{observed\_total\_task\_time}
{ideal\_total\_task\_time}ufile​=ideal_total_task_timeobserved_total_task_time​
Where:
ideal_total_task_time=target_file_sizeeffective_scan_throughput_per_coreideal\_total\_task\_time=
\frac{target\_file\_size}
{effective\_scan\_throughput\_per\_core}ideal_total_task_time=effective_scan_throughput_per_coretarget_file_size​
The baseline throughput is empirically derived from well-optimized executions and represents a conservative lower bound.

6.2 Scan Efficiency
Failure Mode
Read amplification caused by ineffective pruning or data layout.
Usage Signal
uscan=files_scannedfiles_requiredu_{scan}=
\frac{files\_scanned}
{files\_required}uscan​=files_requiredfiles_scanned​
This isolates unnecessary data access and is orthogonal to file granularity.

6.3 Delete File Overhead
Failure Mode
Additional scan cost introduced by merge-on-read delete processing.
Delete Cost Ratio
delete_cost_ratio=delete_file_bytesdelete_file_bytes+data_file_bytesdelete\_cost\_ratio=
\frac{delete\_file\_bytes}
{delete\_file\_bytes+data\_file\_bytes}delete_cost_ratio=delete_file_bytes+data_file_bytesdelete_file_bytes​
Exposure
delete_exposure=queries_touching_deletestotal_queriesdelete\_exposure=
\frac{queries\_touching\_deletes}
{total\_queries}delete_exposure=total_queriesqueries_touching_deletes​
Usage Signal
udelete=delete_exposure×delete_cost_ratiou_{delete}=
delete\_exposure \times delete\_cost\_ratioudelete​=delete_exposure×delete_cost_ratio
All inputs are directly reported by the execution engine.

6.4 Manifest Organization
Failure Mode
Excessive metadata traversal during query planning.
Table Hotness
table_hotness=query_executionsmax_observedtable\_hotness=
\frac{query\_executions}
{max\_observed}table_hotness=max_observedquery_executions​
Planning Cost Ratio
planning_cost_ratio=planning_timeexpected_planning_timeplanning\_cost\_ratio=
\frac{planning\_time}
{expected\_planning\_time}planning_cost_ratio=expected_planning_timeplanning_time​
Usage Signal
umanifest=table_hotness×planning_cost_ratiou_{manifest}=
table\_hotness \times planning\_cost\_ratioumanifest​=table_hotness×planning_cost_ratio
This captures metadata overhead only when slow planning occurs frequently.

6.5 Partition-Aware Metrics
Failure Mode
Excessive data scanning caused by ineffective partition pruning or skewed partition layouts.
Partition Cost Ratio
partition_cost_ratio=partitions_scannedtotal_partitionspartition\_cost\_ratio=
\frac{partitions\_scanned}
{total\_partitions}partition_cost_ratio=total_partitionspartitions_scanned​
Interpretation:

Close to 0 → effective pruning
Close to 1 → near full-partition scan

Exposure
partition_exposure=partition-sensitive queriestotal queriespartition\_exposure=
\frac{partition\text{-}sensitive\ queries}
{total\ queries}partition_exposure=total queriespartition-sensitive queries​
Usage Signal
upartition=partition_exposure×partition_cost_ratiou_{partition}=
partition\_exposure \times partition\_cost\_ratioupartition​=partition_exposure×partition_cost_ratio
This represents the effective structural pressure caused by partition inefficiency.
7. Structural Health Score Computation Under Delete Overhead
This analysis derives the structural table health score using only:

Table metadata
Workload exposure

No execution-time-calibrated subscores are used.
7.1 Dataset and Table Configuration
Experiments were conducted on a production-scale Iceberg table:
sales_base

Approximately 2 billion rows
Merge-on-read (MOR) layout
Row-level deletes materialized as delete files

The workload consists of delete-aware analytical queries.

7.2 Delete Usage Signal Definition
Delete Cost Ratio
delete_cost_ratio=delete_file_bytesdelete_file_bytes+data_file_bytesdelete\_cost\_ratio=
\frac{delete\_file\_bytes}
{delete\_file\_bytes+data\_file\_bytes}delete_cost_ratio=delete_file_bytes+data_file_bytesdelete_file_bytes​
Delete Exposure
delete_exposure=queries touching delete filestotal queriesdelete\_exposure=
\frac{queries\ touching\ delete\ files}
{total\ queries}delete_exposure=total queriesqueries touching delete files​
Delete Usage Signal
udelete=delete_exposure×delete_cost_ratiou_{delete}=
delete\_exposure \times delete\_cost\_ratioudelete​=delete_exposure×delete_cost_ratio

7.3 Subscore Mapping
sdelete=11+udeletes_{delete}=
\frac{1}{1+u_{delete}}sdelete​=1+udelete​1​
Properties:

Bounded in (0,1]
Monotonic degradation
Stable under small fluctuations


7.4 Metric Weight Derivation
Baseline Anchor
Representative group-by aggregation query:
Tbaseline≈79sT_{baseline} \approx 79sTbaseline​≈79s
Observed Runtime Amplification
Delete-aware query runtime:
Tdelete≈87sT_{delete} \approx 87sTdelete​≈87s
Δdelete≈8s\Delta_{delete} \approx 8sΔdelete​≈8s
Weight Assignment
wdelete=8w_{delete}=8wdelete​=8
Only the delete metric contributes in these experiments.

7.5 Structural Health Definition
Health=100×∑i(wifinal×si)Health=
100 \times \sum_i (w_i^{final}\times s_i)Health=100×i∑​(wifinal​×si​)
Where:
wifinal=wiadj∑jwjadjw_i^{final}=
\frac{w_i^{adj}}
{\sum_j w_j^{adj}}wifinal​=∑j​wjadj​wiadj​​
and
wiadj=wibase(1+ui)w_i^{adj}=w_i^{base}(1+u_i)wiadj​=wibase​(1+ui​)
For a single metric:
wdeletefinal=1w_{delete}^{final}=1wdeletefinal​=1

7.6 Baseline Structural Health (Experiment A)
Baseline Scan Statistics

Data file bytes: 4,621,100,465
Delete file bytes: 23,529,021

Baseline Delete Cost Ratio
0.005060.005060.00506
Baseline Delete Exposure
1.01.01.0
Baseline Delete Usage
udelete=0.00506u_{delete}=0.00506udelete​=0.00506
Baseline Delete Subscore
sdelete≈0.995s_{delete}\approx0.995sdelete​≈0.995
Baseline Weight Adjustment
wdeletebase=8w_{delete}^{base}=8wdeletebase​=8
wdeleteadj=8.0405w_{delete}^{adj}=8.0405wdeleteadj​=8.0405
wdeletefinal=1w_{delete}^{final}=1wdeletefinal​=1
Baseline Health Score
Healthbaseline≈99.5Health_{baseline}\approx99.5Healthbaseline​≈99.5
This indicates very low latent delete risk.

7.7 Delete-Degraded Structural Health (Experiment B)
Degraded Scan Statistics

Data file bytes: 4,621,100,465
Delete file bytes: 221,224,399

Degraded Delete Cost Ratio
0.04570.04570.0457
Degraded Delete Exposure
1.01.01.0
Degraded Delete Usage
udelete=0.0457u_{delete}=0.0457udelete​=0.0457
Degraded Delete Subscore
sdelete≈0.956s_{delete}\approx0.956sdelete​≈0.956
Degraded Weight Adjustment
wdeleteadj=8.3656w_{delete}^{adj}=8.3656wdeleteadj​=8.3656
wdeletefinal=1w_{delete}^{final}=1wdeletefinal​=1
Degraded Structural Health Score
Healthdegraded≈95.6Health_{degraded}\approx95.6Healthdegraded​≈95.6

7.8 Results Summary























ScenarioDelete File RatioDelete Usage (u_delete)Health ScoreBaseline (Exp A)0.51%0.005199.5Delete-Degraded (Exp B)4.57%0.045795.6
Figure 1. Structural health scores before and after delete degradation. Health is computed exclusively from structural delete usage, without runtime calibration.
Figure 2. Impact of deleted file ratio on structural health. The bounded mapping ensures gradual degradation even as delete metadata increases.
8. Non-Overlapping Cost Attribution

























MetricIsolatesFile Size OptimizationTask execution overheadScan EfficiencyData read amplificationDelete OverheadMOR delete processingManifest OrganizationPlanning-phase metadata cost
Improving one dimension does not inherently improve others.
9. Advantages Over Prior Art

Dynamic relevance without redefining metric semantics
Cost-based, not symptom-based scoring
Engine-observable and explainable
Extensible to additional metrics without changing core logic

10. Status
This disclosure defines the scoring framework and four fully specified usage-conditioned metrics.
Additional metrics may be incorporated using the same:
Exposure×CostExposure \times CostExposure×Cost
pattern without altering the inventive concept.