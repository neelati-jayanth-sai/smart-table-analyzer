# Context

## Knowledge trees

- `knowledge/iceberg` is curated Apache Iceberg knowledge.
- `knowledge/iomete` is curated IOMETE platform knowledge.
- `knowledge/runbooks` is curated team operating knowledge.
- `knowledge/runbooks/validated-workload-profiles.md` is the authority for the
  team-verified 2026-08-24 ingestion and consumption profiles. File size,
  row-group size, distribution mode, partitioning, and compaction are
  conditional rules selected from measured table/workload evidence, not global
  defaults. The runbooks supersede generic vendor guidance where they apply.

## SQLite-backed knowledge retrieval seam

- `scripts/retrieve_knowledge.py` is the small interface (CLI).
- `scripts/knowledge_retrieval.py` exposes deterministic `list_knowledge_paths` and `fetch_knowledge_path` over SQLite index.
- `data/investigation.db` is the authoritative knowledge index (topic path → current version) per Architecture.md §5; an explicit database path is supported only as a test or CLI override.
- `scripts/init_knowledge_db.py` scans authored entries and populates knowledge_index table.
- Authored knowledge lives in `knowledge/<source>/*.md` - one file per topic, 50-200 lines each. README inventories are documentation only and are excluded from seeding and deterministic fallback retrieval.
- List returns topic paths + descriptions; Fetch returns full markdown text.
- Clean structure: only production .md files, no intermediate artifacts.

## Investigator metadata seam

- `src/metadata/loader.py` is the small interface for loading Iceberg/IOMETE table metadata.
- `load_table_metadata(spark, table_name)` returns columns, `.files`, `.partitions`, `.history`, and `.snapshots` summaries plus sample rows.
- Metadata is JSON-safe (numpy scalars, Decimals, datetime, and binary values are normalized) before being passed into the investigator state.
- `src/models/state.py` carries `table_metadata` on `InvestigationState`.
- `InvestigationState` also tracks `asked_questions` across checks so selection can avoid duplicate questions.
- Registered deterministic skill templates use metadata table names only through safe rendering.

## Query serialization

- `src/query/query_workbench.py` normalizes all Spark row values to plain JSON/msgpack serializable primitives before returning `QueryResult`.
- This ensures `InvestigationState` checkpoint writes to SQLite and `investigation_trail` JSON storage succeed for Decimal, datetime, binary, and numpy-backed values.
- `QueryWorkbench` supports optional `table_name` and `snapshot_id` for Iceberg `VERSION AS OF` pinning and avoids double execution by default (use `full_count=True` for an accurate total).
- It accepts `table_metadata` and appends `SqlGroundingHook` before execution as defence in depth.

## Schema grounding seam

- `src/query/schema_grounding.py` exposes `SchemaResolver` and `SqlGroundingHook`.
- `SqlGroundingHook` is an adapter behind the `QueryHook` seam; it rejects queries that reference columns absent from the base table or Iceberg metadata tables (`.files`, `.partitions`, `.history`, `.snapshots`).
- It kills hallucinations such as `partition` on `.files` while tolerating unknown aliases, missing metadata, and subqueries.
- `SchemaResolver` resolves columns per table from the metadata produced by `src/metadata/loader.py`.

## Manifest layer seam

- `knowledge/<source>/manifest/` holds hand-curated semantic indexes over the tree layer.
- Each manifest is a reviewable YAML file with semantic name, description, tree path list, and version.
- `scripts/knowledge_manifest.py` exposes `list_manifests` and `fetch_manifest` for loading and concatenating manifest content.
- `retrieve_knowledge.py --manifest <source>` lists available manifests; `fetch --manifest <source> --path <name>` concatenates all tree entries referenced by that manifest.
- Manifests let humans curate coherent topic bundles (e.g., "partitioning", "snapshots") without rebuilding the tree layer.

## Claim validation seam

- `src/evidence/collection_adapter.py` persists five deterministic collection records (identity/schema, layout, properties, column profile, workload) and matching coverage before LLM investigation; the profile mode determines whether column evidence is complete, partial, failed, or skipped. `src/investigator/critic/final_review.py` critiques the completed run through the final-review seam and records a safe fallback when its structured response is unavailable.
- `src/validation/claim_validator.py` scopes `trail:`, `knowledge:`, and `evidence:{id}` references to their investigation; a completed deterministic record may support a finding when no successful LLM query is used.
- `src/reporting/assembler.py` embeds a `ClaimValidator` result for each finding in the final report.
- A claim must cite a successful query from its own check; knowledge is supporting context, never standalone table proof.
- `src/dashboard/current_result_trust.py` is the current-run projection seam. It shows a verified finding or recommendation only when persisted validation, authoritative claim validation, and successful execution agree.

## Reporting seam

- `src/reporting/assembler.py` assembles an `InvestigationReport` from the database, baseline score, findings, and knowledge references.
- `src/reporting/writer.py` writes the report as Markdown with a JSON sidecar under `reports/`.
- Default filename: `reports/investigation_{run_id}_{table}_{timestamp}.md`.
- Section order is fixed and engineer-first: Executive Summary, Root Causes, Evidence, SQL Validation, Recommendations, Metadata Appendix.
- `src/calculators/baseline_scorer.py::explain_score` breaks the health score into per-dimension evidence and impact rows; the report renders that table instead of a bare number.

## Finalized assessment and dashboard seam

- `src/reporting/assessment_policy.py::assess` is the assessment seam. It produces `clean`, `needs_review`, `action_required`, or `incomplete` independently of the investigation lifecycle. A lifecycle of `completed` only means execution finished.
- A report stores both `lifecycle_state` and `assessment`; every consumer must project the report assessment rather than infer a health state from SQLite findings. High-severity deterministic signals prevent `clean`, and records without `assessment_version=deterministic-v1` are `incomplete` so legacy runs cannot become false green.
- A finding's `verdict` records whether its investigation question was answered; `issue_state` separately records `issue_found`, `no_issue_found`, or `needs_review`. Only a validated `issue_found` may create a root cause, action-required assessment, or remediation action.
- `src/dashboard/report_store.py::InvestigationReportStore` is the dashboard interface: `list_runs()` returns newest-first history and `get_report(investigation_id)` returns the one assembled report used by all screens. Its fingerprint identifies the exact report projection being displayed.
- `src/dashboard/` renders progressive navigation in the fixed order Overview, Findings, Evidence, History, Audit. The view-model module only projects report state and measured signal thresholds; it does not derive a table assessment.

## Analysis pipeline seam

- `src/runtime/` is the analysis-runtime seam. `AnalysisRuntime` returns canonical Iceberg analysis models; `SparkIometeRuntime` owns production Spark normalization and `LocalIcebergRuntime` owns PyIceberg metadata plus DuckDB compute. The analyzer must not branch by environment or consume Spark/Arrow/DuckDB values directly.
- The proven runtime interface is intentionally limited to table description, bounded samples, primitive-column profiling, latest snapshot lookup, optional workload patterns, and validated read-only evidence queries. The latter is an audited Investigator requirement, not a generic Spark SQL interface.
- `src/analyzer/legacy_analyzer.py` is the deterministic sensor layer: `collect_core(table)` returns enough metadata, signals, and baseline for investigation; `complete_profile(context)` appends the mandatory full primitive-column profile. It never calls an LLM and never recommends.
- `collect_raw_metrics` retains partition-storage facts (partition byte and file-count distribution) alongside row skew without scanning the base table: it batches `.files`, `.partitions`, and `.snapshots` aggregates. Its `row_count` is the current data-file `record_count` estimate, with explicit provenance, rather than an exact delete-aware `COUNT(*)`.
- `src/metadata/collection_profile.py::MetadataCollectionProfile` is the collection Interface. The dashboard always resolves to `deep` and ten Thorough checks; compatibility callers may still carry legacy profile values while migration completes. Deep profiles every primitive column in bounded aggregate batches and records skipped/failed columns.
- `detect_signals` turns measured facts into `{name, severity, detail, metrics}` signals (small_files, undersized_partitions, partition_skew, unpartitioned, missing_sort_order, delete_overhead, manifest_health, snapshot_retention, table_property_naming, custom_property_naming, poor_pruning, measurement_unavailable, empty_table). `undersized_partitions` means average partition capacity is below the 128 MB file target; it warrants testing a coarser partition transform, but does not by itself prove that daily pruning is inappropriate. Unavailable measurements always require review rather than silently becoming zero-valued facts.
- `src/metadata/properties.py` is the table-property casing seam. It preserves exact catalog keys in `raw_properties` and exposes only exact lowercase keys as effective `properties`; it never turns a mixed-case lookalike into an active setting. Known Iceberg/team configuration keys with noncanonical casing produce a high-severity `table_property_naming` signal, while unknown custom names remain a low-severity caution. Canonical-plus-variant pairs are recorded as collisions for report evidence.
- High-severity deterministic signals are assessment evidence, not LLM instructions: they lower the baseline score, persist with it, and require a review warning even when an LLM check returns `not_found`. A lifecycle status of `completed` means checks finished; it never means the table is healthy.
- `src/analyzer/pipeline.py` starts the Investigator from core evidence while the required full profile runs beside it; it persists the completed profile before final review and reporting.
- `SmartTableAnalyzer` receives and reuses an already-established Spark session; the CLI only stops sessions it created. Evidence queries use Spark Connect tag-scoped interruption when the connector supports it, and otherwise report timeout cancellation as unconfirmed rather than claiming the action stopped.
- The Analyzer captures a snapshot when callers have not supplied one. Deterministic metrics are read `VERSION AS OF` that snapshot; DDL, schema, and properties remain explicitly live observations.
- Deep column profiling is capped at eight columns and one worker by default. Its timeout returns promptly and records unconfirmed server-side cancellation rather than pretending Spark work stopped.
- `src/context/summarizers.py::InvestigationContext` caches metadata, signals, baseline, completed checks, evidence IDs, and findings for one run; `to_state()` projects it into `InvestigationState`.
- `scripts/run_investigation.py` is the thin CLI wrapper: environment, SSL, Spark session, then `SmartTableAnalyzer.analyze`.
- `scripts/_investigation_cli.py` holds environment/Spark/report plumbing plus `setup_logging`, which stamps every log record with its investigation id.

## Investigation lifecycle

- States: `metadata_collected` -> `planning` -> `checks_running` -> `evidence_validated` -> `completed` | `failed`.
- `InvestigationDb.complete_investigation` downgrades `completed` to `failed` when no finding cites evidence, so a report can never claim success over an empty evidence set.
- `src/investigator/selection.py` selects one registered check adaptively from measured signals, with deterministic fallback when the LLM is unavailable.
- `src/investigator/skills/` is the deterministic execution seam: registered templates are safely rendered and recorded; the LLM cannot supply SQL.
- `src/investigator/loop/` runs each hypothesis as a chain (skill -> evidence -> decide -> follow-up, up to `MAX_FOLLOWUPS_PER_CHAIN`); a chain that fails is logged and skipped rather than ending the run.
- Every finding carries `evidence_ids` and a `confidence`; `graph_node_executors._confidence` derives one deterministically when the LLM omits it.
## Knowledge retrieval seam

- `src/investigator/knowledge/retriever.py` provides deterministic `KnowledgeRetriever` fallback when the LLM tool loop yields no references.
- `src/investigator/knowledge/tool_runner.py` runs the list-then-fetch LLM tool loop and records fetched references.
- `src/context/summarizers.py` summarizes findings, query results, and knowledge consulted to stay within the context budget.
- `src/database/knowledge_store.py` accepts an optional explicit `repo_root`; callers pass it when available instead of deriving it from `db_path`.
- `knowledge retriever`, `context budget`, and `prompt summarization` are first-class domain terms.

## Context engine seam

- `src/context/engine.py` exposes `ContextEngine` (ABC), `InvestigationContextEngine`, `PromptProfile`, and `PromptContext`.
- `InvestigationContextEngine` builds profile-specific `PromptContext` objects for `DECIDE`, `KNOWLEDGE`, `QUERY`, and `ANALYSIS` prompts.
- `src/context/summarizers.py` provides summarization helpers used by the context engine: `summarize_findings`, `summarize_query_result`, `prepare_knowledge_context`, and `summarize_metadata`.
- `summarize_metadata` enforces per-section column budgets so wide tables do not collapse metadata sections.

## Token counter seam

- `src/utils/tokens.py` exposes `TokenCounter` (ABC) plus `Char4TokenCounter` and `TiktokenTokenCounter` adapters.
- `get_token_counter(model_name=None)` returns a tiktoken-based counter when the model family is known, otherwise the character/4 fallback.
- `LLMAdapter` exposes a `token_count(messages)` seam; `DellAIAAdapter` uses the counter and records `last_usage` statistics.
- `MAX_PROMPT_TOKENS` defaults from `PROMPT_MAX_TOKENS` (or 8000) and is enforced consistently by `prompts.py`.

## Context budget

- Prompts receive summarized table metadata (column names grouped by table: main, .files, .partitions, .history, .snapshots), query results (row_count + up to 3 key rows), and truncated knowledge excerpts (<=500 chars each, <=2000 total).
- The default prompt token budget is read from `PROMPT_MAX_TOKENS` (default 8000) and applied through `MAX_PROMPT_TOKENS` (exported from `src/context`).
- `investigator/prompts/builders.py` checks each built prompt against `MAX_PROMPT_TOKENS` with `TokenCounter` and raises if it exceeds the budget.
- Prompts include partition metadata (`partition_count`, `partition_queryable`) so `decide_next_check` avoids `partitioning` checks on unpartitioned or non-queryable tables.
- Retry prompts include the previous failed query and its error so the LLM can correct itself instead of repeating the same invalid SQL.

## Budget router

- `src/investigator/state/budget.py` exposes `StepBudget` and `BudgetRouter`.
- `StepBudget` derives `max_steps` from `max_checks` and `max_retries_per_check`: `max_checks * (6 + 2 * max_retries_per_check) + padding`.
- `Investigator` sets `max_steps` on the initial state from `StepBudget`, with headroom for follow-up checks.
- `BudgetRouter` routes between `success`, `retry`, and `failed` after query execution, but refuses `retry` when the global step budget cannot afford another `generate`+`execute` cycle.
- `InvestigationState` carries `step_count` (incremented by each graph node) and `max_steps`; `state_validator.py` enforces non-negative invariants.

## Empty table handling

- `scripts/_investigation_cli.py::compute_baseline` sets `is_empty` in `baseline_score.dimensions` when `row_count == 0` and `num_data_files == 0`.
- `InvestigationContextEngine` exposes `is_empty`, `row_count`, and `num_data_files` in the `baseline_summary`.
- `build_decide_prompt` instructs the LLM to ask exactly one confirmation question when the table is empty, instead of inventing file-size or partitioning questions.
- `Investigator.run_investigation` caps `max_checks` to 1 for empty tables so the investigation completes after the single confirmation check.

## Alation catalog context seam

- `src/metadata/catalog/` exposes `AlationContextAdapter` (ABC), `TablePatterns`, `AlationAPIKeyAdapter`, and `MockAlationAdapter`.
- `AlationContextAdapter` is an adapter behind a catalog context seam; it retrieves usage patterns (common_joins, common_filters, lineage, stewards, popular_columns) from Alation.
- `AlationAPIKeyAdapter` uses the standard Alation REST API v2 with API key authentication (refresh token + access token).
  - Retrieves table metadata via `/integration/v2/table/`
  - Retrieves column metadata via `/integration/v2/column/` with `table_id` filter
  - Returns `popular_columns` list with name, title, data_type, and custom_fields for up to 50 columns per table
  - Attempts to retrieve joins via `/integration/v2/join_predicates/table/{id}/` (may return 404 if not enabled)
  - `common_filters` and lineage counts require the Alation AI Agent SDK (admin setup) and are not available via standard API
- `MockAlationAdapter` provides static patterns for testing without Alation credentials.
- `scripts/_investigation_cli.py::compute_baseline` accepts an optional `alation_adapter` and adds `catalog_score`, `downstream_count`, `upstream_count`, and `has_catalog_context` to baseline dimensions when Alation is available.
- `scripts/run_investigation.py` initializes `AlationAPIKeyAdapter` if `ALATION_BASE_URL` and `ALATION_ACCESS_TOKEN` are configured in `.env`, and passes it to baseline collection.
- Environment variables: `ALATION_BASE_URL`, `ALATION_ACCESS_TOKEN`, `ALATION_REFRESH_TOKEN`, `ALATION_USER_ID`, `ALATION_VERIFY_SSL`.

## Package layout

- `src/analyzer/` deterministic collection (`metrics.py`, `signals.py`) plus the
  pipeline entrypoint (`pipeline.py`).
- `src/context/` the investigation context and the prompt-rendering engine.
- `src/investigator/` reasoning, split into `selection.py`, `loop/`, `executors/`,
  `critic/`, `knowledge/`, `prompts/`, and `state/`.
- `src/metadata/` every Spark structure read, performed once per investigation.
- `src/models/` domain models: `Finding`, `Investigation`, `InvestigationState`,
  `InvestigationReport`.
- `src/reporting/` assembles validated findings and deterministic warnings, then renders sections and closing sections through `markdown.py` -> `writer.py`.
- `src/database/` keeps connection/lifecycle ownership in `investigation_db.py`; read and write adapters isolate query ordering and persistence operations behind that interface.
- `src/utils/` token counting, JSON extraction, and retry error guidance.
- Package `__init__` exports are the public API; deep module paths are internal
  and may move.

## Dashboard current-run UI

- The Streamlit UI has one job: validate and run one fully qualified table,
  then render only that session's fresh outcome. It does not browse report
  history or artifacts.
- Historic report persistence remains a backend capability, not dashboard UI.

## Mock Iceberg test harness

- `tests/mocks/iceberg.py` builds realistic Iceberg metadata per scenario:
  `healthy`, `partition_skew`, `small_files`, `missing_sort_order`,
  `delete_overhead`, `table_property_naming`, `empty`.
- Scenarios are internally consistent; `sql.py`, `spark.py`, and `llm.py` derive
  evidence, record reads, and provide deterministic prompt-kind responses.

## Local Iceberg E2E

- `LocalIcebergRuntime` and `LocalIcebergSession` are the local adapter: PyIceberg
  normalizes metadata and DuckDB executes the existing read-only query path.
- Local fixtures use a documented 20 KB scale; production retains the 128 MB standard.
