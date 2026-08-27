# TASK_TRACKER.md

Tracker for `Smart_Table_Analyzer_Architecture_Review.md` (phase 1) and the
mock-Investigator test suite plus modular refactor (phase 2).

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked

**Historical tracker:** current implementation status and verification results are maintained in
`IMPLEMENTATION_PROGRESS.md`.

---

# Phase 2 — Investigator testing and modular architecture

## 1. Investigator testing

- [x] **1.1** Realistic mock Iceberg metadata and table scenarios
  - [x] `tests/mocks/iceberg.py` — real `.files` / `.partitions` / `.snapshots` /
        `.history` column sets, table properties, partition specs, sample rows
  - [x] Seven scenarios: `healthy`, `partition_skew`, `small_files`,
        `missing_sort_order`, `delete_overhead`, `table_property_naming`, `empty`
  - [x] Every scenario is internally consistent — row counts, file counts, and byte
        totals agree across `.files` and `.partitions` (asserted, parametrized)
  - [x] Each raises **exactly one** signal, so tests assert detection *and* the
        absence of false positives
- [x] **1.2** `tests/mocks/sql.py` — read-only SQL evaluator so mock evidence is
      derived from the scenario's data instead of hardcoded per test
- [x] **1.3** `tests/mocks/spark.py` — Spark Connect stand-in; records every query and
      table read, and injects failures via `fail_on`
- [x] **1.4** `tests/mocks/llm.py` — scripted LLM that answers by *prompt kind* (not
      round-robin, which breaks under concurrency) and echoes the real query numbers
- [x] **1.5** Scenario coverage in `tests/test_investigator_scenarios.py`

| Required scenario | Tests |
|---|---|
| partition skew | signal severity + measured ratio, plan → `skew`, finding quotes the 40,000,000-row partition |
| small files | signal + measured average, plan → `file_size`, finding quotes the 3,000 file count |
| missing sort order | signal fires only when no sort order *and* no sort property, plan → `sort` |
| healthy table | no signals at all, generic coverage plan, **no root causes** in the report |
| hook failures | `ReadOnlyHook`, `SchemaWhitelistHook`, `SqlGroundingHook`; recorded, retried, run continues, report warns |
| SQL execution failures | retried with the error in the next prompt, other checks still conclude, report warns |
| adaptive multi-step loop | follow-up creates a second check with its own evidence ID, bounded by `MAX_FOLLOWUPS_PER_CHAIN`, follow-up question reaches the query prompt |

- [x] **1.6** Investigator chooses different checks per mock metadata
  - [x] Parametrized signal → first-hypothesis mapping across six scenarios
  - [x] `test_different_tables_get_different_plans` asserts the first hypothesis is
        distinct for every problem scenario
  - [x] Severity ordering: HIGH before MEDIUM before LOW
  - [x] Investigator selection honoured when available; selection outage degrades to
        signal-derived deterministic checks rather than failing
- [x] **1.7** Every finding carries confidence, rationale, and evidence
  - [x] Asserted for every scenario: evidence IDs non-empty, resolve through
        `ClaimValidator`, confidence in [0, 1], rationale ≥ 20 chars
  - [x] Confidence derived when the LLM omits it; clamped when out of range
  - [x] A finding with no evidence is recorded `inconclusive` and the run is `failed`
- [x] **1.8** `tests/test_mock_iceberg.py` — 32 tests on the fixtures themselves, so
      fixture drift cannot silently hollow out the suite

### Defects found by the new tests, and fixed

1. **An unreachable table was reported as an empty table.** `collect_raw_metrics`
   swallowed every query error and returned zeros, so a total Spark outage produced
   `is_empty=True` and a clean bill of health. Now raises `MetadataUnavailable` when
   every metric query fails, tracks `failed_metrics` on partial failure, and only calls
   a table empty when the counts actually answered.
2. **`ORDER BY` on a non-selected column was a no-op** in the mock SQL evaluator
   (it sorted after projection). Fixed to sort source rows before projecting, as SQL
   does — this is the shape of the snapshot-pinning query.
3. **Markdown tables broke the executive summary.** `exact_result` is often a table,
   which cannot be inlined in a bullet. Now flattened and truncated for the headline;
   the full value still renders under Root Causes.

## 2. Modular architecture

- [x] **2.1** New package layout (see `CLAUDE.md` for the annotated tree)

| Package | Responsibility |
|---|---|
| `src/analyzer/` | `metrics.py` (collection) · `signals.py` (measurement vs standard) · `legacy_analyzer.py` · `pipeline.py` (entrypoint) |
| `src/context/` | `investigation_context.py` · `summarizers.py` · `engine.py` · `helpers.py` |
| `src/investigator/skills/` | Registered deterministic checks, templates, rendering, and execution seam |
| `src/investigator/loop/` | `chain.py` (one hypothesis to conclusion) · `runner.py` (fan-out) |
| `src/investigator/executors/` | `nodes.py` · `query.py` · `execution.py` · `analysis.py` · `compaction.py` · `analyst_tools.py` |
| `src/investigator/critic/` | `critic.py` · `quality_gate.py` · `sanitizers.py` |
| `src/investigator/prompts/` | `builders.py` · `response_validator.py` · `templates/` |
| `src/investigator/state/` | `validator.py` · `budget.py` (schema lives in `src/models/state.py`) |
| `src/investigator/knowledge/` | `retriever.py` · `tool_runner.py` · `tool_definitions.py` |
| `src/metadata/` | `loader.py` · `columns.py` · `partitions.py` · `properties.py` · `query_patterns.py` · `workload.py` · `catalog/` |
| `src/models/` | `finding.py` · `state.py` · `report.py` |
| `src/reporting/` | `assembler.py` → `sections.py` → `markdown.py` → `writer.py` |
| `src/database/` | `schema.py` (DDL + migrations) · `investigation_db.py` · `knowledge_store.py` |
| `src/utils/` | `tokens.py` · `json_parsing.py` · `errors.py` |

- [x] **2.2** `ExecutorNodes` split into one mixin per stage, composed in
      `executors/nodes.py`, so each stage is separately readable and testable
- [x] **2.3** No file over 500 lines — largest is `database/investigation_db.py` at 354
      (one repository class); next is `investigator/investigator.py` at 201
- [x] **2.4** Dead code and duplicate implementations removed (~2,000 lines)

| Removed | Why |
|---|---|
| `src/examples/` (6 files) | Demos of the connectors below; four could not import |
| `src/connectors/iomete_connector.py` (500 lines) | Imports `iceberg_metadata_extractor`, which does not exist in this repo — unimportable, unreferenced |
| `src/connectors/real_iceberg_connector.py` (178) | Same missing import |
| `src/calculators/iceberg_health_calculator.py` (155) | A second health-score implementation; its own `compute_from_metrics_dict` raises `NotImplementedError("Use baseline_scorer.score() instead")` |
| `src/calculators/usage_signal_calculators.py` (210) | Fed only the duplicate above |
| `tests/test_pipeline_integration.py` (424) | Duplicated the mock Spark and LLM that `tests/mocks/` now provides; assertions folded into the scenario suite, response-validation, and scorer tests |
| `tmp_kwtypes.py` | Scratch file |

- [x] **2.5** Public APIs preserved — every package `__init__` still exports what it
      exported before (verified by an explicit API check across 18 packages).
      Deep module paths moved; they are internal, and all in-repo callers were updated.

### Import-path changes (deep paths only)

`investigator.state` → `models.state` · `investigator.metadata_loader` →
`metadata.loader` · `investigator.context_manager` → `context.summarizers` +
`context.investigation_context` · `investigator.context_engine` → `context.engine` ·
`investigator.check_planner` → `investigator.selection` + `investigator.skills` · `investigator.parallel_runner` →
`investigator.loop` · `investigator.graph_nodes` / `graph_node_executors` →
`investigator.executors` · `investigator.finding_quality` → `investigator.critic` ·
`investigator.token_counter` / `response_parser` / `error_guidance` → `utils.*` ·
`reporting.report_writer` → `reporting.{sections,markdown,writer}` ·
`analyzers.*` → `analyzer.*`

### Structural problems the refactor exposed, and fixed

1. **An import cycle**: `context` needed `InvestigationState`, which lived under
   `investigator`, which imports `context`. The state schema is a shared data model,
   so it moved to `src/models/state.py`; `investigator/state/` keeps the *rules*
   (validator, budget) and re-exports the schema.
2. **A name collision**: two modules named `query_patterns` (the model/protocol and the
   IOMETE adapter). The model is now `metadata/workload.py`.
3. `Finding` and `Investigation` were defined inside the SQLite module. They are domain
   models, so they moved to `src/models/finding.py`; the database now stores them.

## 3. Validation

- [x] Full suite green after every phase (A→D), fixed before moving on
- [x] Final: **194 passed**
- [x] Script smoke tests: `scripts/test_budget.py` and the local Iceberg E2E runner pass
- [x] Import sweep: every module under `src/` imports cleanly (0 failures)
- [x] Byte-compile: all of `scripts/`, `app.py`, `ui_*.py`
- [x] Public-API check across 18 packages: 0 failures
- [x] End-to-end smoke: full pipeline over the `small_files` scenario renders a
      complete six-section report
- [x] `CLAUDE.md` repository map and module-ownership sections updated to the new
      layout; `CONTEXT.md` seam paths repointed and the mock harness documented

---

# Phase 1 — Architecture review fixes

## P0-0 Audit

- [x] Trace `run_investigation.py` → Legacy Analyzer → Investigator → Report
- [x] Inventory missing/dead modules
- [x] Baseline test run

**A1 — The project did not import.** `src/investigator/__init__.py` eagerly imported a dead
`investigation_graph.py`, which imported `langgraph.checkpoint.sqlite` (not installed, not in
`requirements.txt`). 8/8 test modules failed at collection; 0 tests ran. That module and
`routers.py` were dead — nothing but themselves referenced `create_investigation_graph`.

**A2 — Six referenced modules did not exist in this working copy:** `src/database/`,
`src/reporting/report_{models,assembler,writer}.py`, `src/connectors/dell_aia_adapter.py`,
`src/investigator/metadata_loader.py`, five prompt templates, `ui_metadata.py`. Contracts were
recovered from call sites, `schema/investigation.sql`, `CONTEXT.md`, and the committed reports.

**A3 — No Legacy Analyzer.** Collection was scattered across a CLI helper. `src/analyzers/`
held two dead scripts that hardcoded a production IOMETE API token, printed a report, and never
invoked the Investigator — the exact bypass the review names.

**A4 — Status was misleading.** `status="completed"` was hardcoded regardless of evidence.
`reports/investigation_real_1.json` is the review's own evidence: `"completed"` alongside
findings of `"exact_result": "hook_failed"` and `"evidence_ids": []`.

**A5 — Hook failure was fatal.** One try/except marked the whole investigation `failed`;
`_fill_with_llm` broke the entire planning loop on the first LLM exception.

**A6 — Checks were hardcoded** in two places (`_COVERAGE_SEQUENCE` and a duplicated ladder in
`decide_next_check`). Signals never influenced what was investigated.

**A7 — No investigation loop.** N independent one-shot checks; a finding could never trigger a
follow-up.

**A8 — Metadata was read repeatedly.** The Investigator re-loaded it whenever `table_metadata`
was `None`, and three loaders each hit Spark again.

**A9 — No confidence** on `Finding` / `FindingState` / `AnalysisState`.

**A10 — Report was metadata-first**, with no Root Cause or SQL Validation section and no
score explanation.

**A11 — `QueryWorkbench` ignored `table_metadata`.** `CONTEXT.md` documented that it appends
`SqlGroundingHook`; the code never did, so hallucinated-column SQL failed in Spark instead of
being rejected with the real column list.

**A12 — Validators used bare `json.loads`**, so a model fencing its JSON in ```json lost the
whole finding.

## P0 Foundations

- [x] **P0-1** Restored every missing module; deleted the dead LangGraph modules
- [x] **P0-2** `analyzer/legacy_analyzer.py` emits `InvestigationContext`; signals are
      `{name, severity, detail, metrics}` measurements with no recommendation vocabulary
      (asserted); dead bypass scripts deleted
- [x] **P0-3** `InvestigationContext` — metadata, signals, baseline, runtime, completed
      checks, evidence refs, findings. No RAG, no embeddings, no vector store
- [x] **P0-4** `analyzer/pipeline.py` is the single path; no branch reaches a report
      without the Investigator
- [x] **P0-5** Lifecycle `metadata_collected → planning → checks_running →
      evidence_validated → completed | failed`; the database downgrades `completed` to
      `failed` when no finding cites evidence; schema widened with an additive migration

## P1 Intelligence

- [x] **P1-1** Signal-driven, LLM-ranked planning; the duplicated hardcoded ladder is gone
- [x] **P1-2** Chains: Hypothesis → SQL → Evidence → Decide → Repeat, bounded
- [x] **P1-3** No hook single point of failure; degraded checks warn in the report;
      `SqlGroundingHook` wired into `QueryWorkbench` (A11)
- [x] **P1-4** Evidence IDs and confidence on every finding, derived when omitted

## P2 Presentation

- [x] **P2-1** Engineer-first report and dashboard, fixed six-section order
- [x] **P2-2** `explain_score` recovers the adaptive weights from the stored subscores;
      contributions reconstruct the overall score (asserted)
- [x] **P2-3** `setup_logging` stamps every record with its investigation id; structured
      logs at each stage

## Cross-cutting

- [x] Iceberg metadata read exactly once (asserted against the recording mock Spark)
- [x] No repeated Spark metadata queries — everything reads `InvestigationContext.metadata`
- [x] Large results stay out of prompts; raw rows persist to `investigation_trail`

---

# Blockers / notes

- **Security — action required:** the deleted `analyze_iomete_table.py` and
  `analyze_any_table.py` contained a hardcoded live IOMETE API token for
  `ashwin_ramesh_kumar`. The files are gone; **the token must be rotated.**
- **This repo is not under version control.** The modules removed in 2.4 were copied to
  the session scratchpad first (`removed_modules/`), but that is temporary. Say so this
  session if you want any of them restored.
- **Not verifiable in this environment:** anything needing a live IOMETE Spark Connect
  session or Dell AIA Gateway credentials — `scripts/test_end_to_end.py`,
  the local E2E runner and `OllamaCloudAdapter` against the configured gateway. The
  adapter's HTTP contract was reconstructed from `scripts/test_llm_oauth.py` and should be
  smoke-tested against the gateway before release. Everything else runs on the mock harness.
- `requirements.txt`: `langgraph` and `langchain-core` removed (no runtime path imports
  them); `streamlit` and `pandas` added, which `app.py` always needed.
- `tests/mocks/sql.py` supports no joins, subqueries, or `HAVING`. Extend the evaluator
  when a test needs one rather than hardcoding a canned result — the point is that mock
  evidence stays consistent with mock metadata.
- `explain_score` recovers weights from the stored subscores, exact for the current
  `s = 1/(1+u)` formula. If `HealthScoreCalculator` changes that formula, the explanation
  must change with it.
