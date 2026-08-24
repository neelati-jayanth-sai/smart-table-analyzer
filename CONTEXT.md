# Context

## Knowledge trees

- `knowledge/iceberg` is curated Apache Iceberg knowledge.
- `knowledge/iomete` is curated IOMETE platform knowledge.
- `knowledge/runbooks` is curated team operating knowledge.

## SQLite-backed knowledge retrieval seam

- `scripts/retrieve_knowledge.py` is the small interface (CLI).
- `scripts/knowledge_retrieval.py` exposes deterministic `list_knowledge_paths` and `fetch_knowledge_path` over SQLite index.
- `investigation.db` holds knowledge index (topic path → current version) per Architecture.md §5.
- `scripts/init_knowledge_db.py` scans authored entries and populates knowledge_index table.
- Authored knowledge lives in `knowledge/<source>/*.md` - one file per topic, 50-200 lines each.
- List returns topic paths + descriptions; Fetch returns full markdown text.
- Clean structure: only production .md files, no intermediate artifacts.

## Investigator metadata seam

- `src/metadata/loader.py` is the small interface for loading Iceberg/IOMETE table metadata.
- `load_table_metadata(spark, table_name)` returns columns, `.files`, `.partitions`, `.history`, and `.snapshots` summaries plus sample rows.
- Metadata is JSON-safe (numpy scalars, Decimals, datetime, and binary values are normalized) before being passed into the investigator state.
- `src/models/state.py` carries `table_metadata` on `InvestigationState`.
- `InvestigationState` also tracks `asked_questions` across checks so the planner can avoid duplicate questions.
- `build_query_prompt` uses metadata to ground generated SQL in real table and Iceberg/IOMETE conventions.

## Query serialization

- `src/query/query_workbench.py` normalizes all Spark row values to plain JSON/msgpack serializable primitives before returning `QueryResult`.
- This ensures `InvestigationState` checkpoint writes to SQLite and `investigation_trail` JSON storage succeed for Decimal, datetime, binary, and numpy-backed values.
- `QueryWorkbench` supports optional `table_name` and `snapshot_id` for Iceberg `VERSION AS OF` pinning and avoids double execution by default (use `full_count=True` for an accurate total).
- It accepts `table_metadata` and appends `SqlGroundingHook` to the hook pipeline so generated SQL is validated against real column metadata before execution.

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

- `src/validation/claim_validator.py` checks every finding's `evidence_ids` against `investigation_trail` and `knowledge_references`.
- Evidence IDs use the forms `trail:{check_num}` and `knowledge:{source}/{topic_path}@{version}`.
- `src/reporting/assembler.py` embeds a `ClaimValidator` result for each finding in the final report.

## Reporting seam

- `src/reporting/assembler.py` assembles an `InvestigationReport` from the database, baseline score, findings, and knowledge references.
- `src/reporting/writer.py` writes the report as Markdown with a JSON sidecar under `reports/`.
- Default filename: `reports/investigation_{run_id}_{table}_{timestamp}.md`.
- Section order is fixed and engineer-first: Executive Summary, Root Causes, Evidence, SQL Validation, Recommendations, Metadata Appendix.
- `src/calculators/baseline_scorer.py::explain_score` breaks the health score into per-dimension evidence and impact rows; the report renders that table instead of a bare number.

## Analysis pipeline seam

- `src/analyzer/legacy_analyzer.py` is the deterministic sensor layer: `LegacyAnalyzer.collect(table)` reads Iceberg metadata once and returns an `InvestigationContext` of metadata, signals, and baseline. It never calls an LLM and never recommends.
- `detect_signals` turns measured facts into `{name, severity, detail, metrics}` signals (small_files, partition_skew, unpartitioned, missing_sort_order, delete_overhead, manifest_health, snapshot_retention, table_property_naming, poor_pruning, empty_table).
- `src/analyzer/pipeline.py` is the single execution path: Legacy Analyzer -> Context Manager -> Investigator -> Evidence -> Report. There is no branch that skips the Investigator.
- `src/context/summarizers.py::InvestigationContext` caches metadata, signals, baseline, completed checks, evidence IDs, and findings for one run; `to_state()` projects it into `InvestigationState`.
- `scripts/run_investigation.py` is the thin CLI wrapper: environment, SSL, Spark session, then `SmartTableAnalyzer.analyze`.
- `scripts/_investigation_cli.py` holds environment/Spark/report plumbing plus `setup_logging`, which stamps every log record with its investigation id.

## Investigation lifecycle

- States: `metadata_collected` -> `planning` -> `checks_running` -> `evidence_validated` -> `completed` | `failed`.
- `InvestigationDb.complete_investigation` downgrades `completed` to `failed` when no finding cites evidence, so a report can never claim success over an empty evidence set.
- `src/investigator/planner/` plans hypotheses adaptively: the LLM ranks them against the measured signals, with signal-derived hypotheses and then a generic coverage sequence as fallbacks for when the LLM is unavailable.
- `src/investigator/loop/` runs each hypothesis as a chain (SQL -> evidence -> decide -> follow-up, up to `MAX_FOLLOWUPS_PER_CHAIN`); a chain that fails is logged and skipped rather than ending the run.
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
- `src/investigator/` reasoning, split into `planner/`, `loop/`, `executors/`,
  `critic/`, `knowledge/`, `prompts/`, and `state/`.
- `src/metadata/` every Spark structure read, performed once per investigation.
- `src/models/` domain models: `Finding`, `Investigation`, `InvestigationState`,
  `InvestigationReport`.
- `src/reporting/` `assembler.py` -> `sections.py` -> `markdown.py` -> `writer.py`.
- `src/utils/` token counting, JSON extraction, and retry error guidance.
- Package `__init__` exports are the public API; deep module paths are internal
  and may move.

## Mock Iceberg test harness

- `tests/mocks/iceberg.py` builds realistic Iceberg metadata per scenario:
  `healthy`, `partition_skew`, `small_files`, `missing_sort_order`,
  `delete_overhead`, `table_property_naming`, `empty`.
- Each scenario is internally consistent — row counts, file counts, and byte
  totals agree across `.files` and `.partitions` — and raises exactly one signal,
  so a test can assert both detection and the absence of false positives.
- `tests/mocks/sql.py` is a small read-only SQL evaluator; mock evidence is
  derived from the scenario's data rather than hardcoded per test.
- `tests/mocks/spark.py` serves those tables through the evaluator and records
  every query and table read, which is how "read metadata once" is asserted.
  `fail_on` injects Spark-side failures.
- `tests/mocks/llm.py` answers by prompt kind rather than round-robin, so
  concurrent checks stay deterministic; `sql=` injects hook-violating SQL and
  `analysis=` controls verdicts, confidence, and follow-ups.
