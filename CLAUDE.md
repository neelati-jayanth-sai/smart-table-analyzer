# CLAUDE.md

> **Architecture Contract — Smart Table Analyzer**
>
> This document is the single source of truth for Claude Code. Read it before making **any** code changes.

---

# Mission

Smart Table Analyzer is **not** a health score generator.

It is an **adaptive Iceberg investigation system** that helps data engineers diagnose table problems by automatically:

1. Collecting Iceberg metadata
2. Detecting investigation signals
3. Forming hypotheses
4. Running validation SQL
5. Evaluating evidence
6. Producing explainable findings

**The Investigator LLM is the primary intelligence of this application.**

The Legacy Analyzer is a deterministic sensor layer.

---

# Architecture Contract

## Non-negotiable Rules

1. **Investigator owns all reasoning.**
2. **Legacy Analyzer never generates recommendations.**
3. Read Spark metadata **once**.
4. Never introduce vector RAG for Iceberg metadata.
5. Every finding requires evidence.
6. Prefer modifying existing modules over creating new ones.
7. Architecture changes require Opus design before implementation.

---

# Repository Structure

```text
src/
├── analyzer/                 # deterministic sensor layer + pipeline entrypoint
│   ├── metrics.py            # one parallel pass of Iceberg metric queries
│   ├── signals.py            # measurements vs the operating standard
│   ├── legacy_analyzer.py    # LegacyAnalyzer -> InvestigationContext
│   ├── pipeline.py           # SmartTableAnalyzer: the single execution path
│   └── progress.py           # AnalysisProgress callback (CLI + dashboard)
│
├── context/                  # investigation state + prompt rendering
│   ├── investigation_context.py
│   ├── summarizers.py        # findings/results/knowledge -> prompt-sized text
│   ├── engine.py             # PromptProfile -> PromptContext
│   └── helpers.py
│
├── investigator/             # the reasoning engine
│   ├── investigator.py       # lifecycle, delegation, terminal status
│   ├── status.py             # final_status: terminal-state decision
│   ├── planner/              # adaptive hypothesis generation
│   │   ├── hypotheses.py     # signal -> hypothesis catalogue (data)
│   │   └── planner.py        # plan_checks: LLM ranking + fallbacks
│   ├── loop/                 # Hypothesis -> SQL -> Evidence -> Decide -> Repeat
│   │   ├── chain.py          # one hypothesis run to a conclusion
│   │   └── runner.py         # concurrent fan-out over chains
│   ├── executors/            # one mixin per stage of a check
│   │   ├── nodes.py          # InvestigationNodes: the composed unit
│   │   ├── query.py          # generate SQL
│   │   ├── execution.py      # run SQL, record the trail
│   │   ├── analysis.py       # result -> draft finding
│   │   ├── analyst_tools.py  # bounded extra-query tool loop
│   │   ├── compaction.py     # draft -> persisted finding
│   │   ├── finding_compaction.py  # build_finding_state helper
│   │   ├── serialization.py  # to_str/to_str_or_none coercions
│   │   └── _logging.py       # @_logged node decorator
│   ├── critic/               # validation of findings
│   │   ├── critic.py         # adversarial LLM review
│   │   ├── quality_gate.py   # deterministic rejection rules
│   │   └── sanitizers.py     # placeholder SQL, confidence derivation
│   ├── knowledge/            # list-then-fetch tool loop + deterministic fallback
│   │   ├── retriever.py      # deterministic keyword fallback
│   │   ├── tool_runner.py    # LLM-driven fetch loop
│   │   └── tool_definitions.py
│   ├── prompts/              # prompt builders, response validation, templates/
│   │   ├── builders.py
│   │   └── response_validator.py
│   └── state/                # invariants (validator) and budget
│       ├── validator.py
│       └── budget.py         # StepBudget
│
├── metadata/                 # ALL Spark structure reads, exactly once
│   ├── loader.py             # load_table_metadata
│   ├── collection_profile.py # MetadataCollectionProfile: fast/deep
│   ├── columns.py            # cardinality / null analysis
│   ├── partitions.py
│   ├── properties.py
│   ├── query_patterns.py     # IOMETE query-log workload adapter
│   ├── workload.py
│   └── catalog/              # Alation catalog context
│       ├── alation_adapter.py
│       ├── api_key_adapter.py
│       ├── api_helpers.py
│       └── mock_adapter.py
│
├── models/                   # domain models shared across layers
│   ├── finding.py            # Finding, Investigation, lifecycle states
│   ├── state.py              # InvestigationState and friends
│   ├── report.py             # InvestigationReport
│   └── assessment.py         # deterministic report assessment
│
├── reporting/                 # consumes validated findings only
│   ├── assembler.py           # DB -> InvestigationReport (+ claim validation)
│   ├── assessment_policy.py   # assess(): status/evidence -> assessment
│   ├── sections.py            # one builder per report section
│   ├── closing_sections.py    # recommendations + metadata appendix
│   ├── markdown.py
│   └── writer.py
│
├── query/                     # SQL execution and safety hooks
│   ├── query_workbench.py     # QueryWorkbench: validate, pin, execute, timeout
│   ├── query_hooks.py         # hook interface + validation results
│   ├── hook_factory.py        # create_investigation_hooks
│   ├── snapshot_pinning.py    # rewrite queries onto a pinned snapshot
│   ├── schema_grounding.py    # SqlGroundingHook: reject hallucinated columns
│   └── _schema_grounding_core.py
│
├── calculators/                # pure deterministic scoring
│   ├── baseline_scorer.py      # score() + explain_score()
│   └── health_score_calculator.py
│
├── database/                   # SQLite persistence
│   ├── schema.py                # create_schema + migrations (DDL in schema/investigation.sql)
│   ├── investigation_db.py      # InvestigationDb facade
│   ├── investigation_reads.py
│   ├── investigation_writes.py
│   ├── knowledge_store.py
│   └── paths.py                 # investigation_db_path
│
├── dashboard/                   # Streamlit dashboard building blocks
│   ├── analysis_runner.py       # DashboardAnalysisRunner: run the pipeline from the UI
│   ├── report_store.py          # InvestigationReportStore: list/get historic reports
│   ├── view_models.py
│   ├── overview.py              # one renderer per dashboard page
│   ├── findings.py
│   ├── evidence.py
│   ├── history.py
│   ├── audit.py
│   └── artifact_reports.py
│
├── connectors/                  # Spark and LLM adapters
│   ├── llm_adapter.py            # LLMAdapter interface + MockLLMAdapter
│   └── dell_aia_adapter.py       # DellAIAAdapter: real LLM connector
│
├── validation/                   # evidence-ID claim validation
│   └── claim_validator.py
│
└── utils/                        # tokens, JSON parsing, error guidance
    ├── tokens.py
    ├── json_parsing.py
    └── errors.py
```

Entry points live outside `src/`: `app.py` is the Streamlit dashboard,
`scripts/_investigation_cli.py` is the CLI — both call
`SmartTableAnalyzer.analyze()`. `tests/` mirrors the modules above;
`schema/investigation.sql` is the canonical DDL for `src/database/schema.py`.

Every folder has **one responsibility**. Files stay small and focused; split a
module rather than letting it accumulate a second job.

Do not mix business logic across modules.

---

# Module Ownership

## src/analyzer/

### Purpose

Deterministic metadata collection only.

### Responsibilities

- Connect to Spark
- Read Iceberg metadata
- Read schema
- Read `$files`
- Read `$partitions`
- Read snapshots
- Read manifests
- Read table properties
- Compute deterministic metrics
- Generate investigation signals

### Must NEVER

- Call the LLM
- Generate recommendations
- Explain root causes
- Decide investigation priority
- Produce the final report

### Output

```python
TableMetadata
LegacySignals
```

Think of this module as a **medical scanner**.

It observes.

It never diagnoses.

---

## src/investigator/

This is the **brain** of the system.

Everything involving reasoning belongs here.

### investigator/investigator.py

Owns:

- Investigation lifecycle
- Hypothesis generation
- Delegation
- Confidence tracking
- Final conclusions

### investigator/planner/

Creates dynamic investigations.

Never hardcode investigation order.

Bad:

```python
if skew > 0.8:
    run_partition_check()
```

Good:

- Read metadata
- Read signals
- Ask LLM what deserves investigation
- Produce ordered hypotheses

### investigator/prompts/

Only prompt construction.

No SQL execution.

No parsing.

### investigator/prompts/response_validator.py

Validate structured LLM responses.

Never invent fallback findings.

Return explicit validation errors.

### investigator/executors/compaction.py

Compress completed investigations into concise summaries.

Purpose:

Reduce prompt size without losing conclusions.

### investigator/loop/

Runs the adaptive loop: Hypothesis -> SQL -> Evidence -> Decide -> Repeat.

One chain per hypothesis, bounded by `MAX_FOLLOWUPS_PER_CHAIN`. A chain that
fails is logged and skipped; it never ends the investigation.

### investigator/critic/

Rejects any claim that outruns its evidence, then the deterministic quality
gate rejects what the Critic let through.

---

## src/context/

A lightweight state manager (`investigation_context.py`) plus the
prompt-rendering engine (`engine.py`).

Responsibilities:

- Cache metadata read once by the Legacy Analyzer
- Build compact prompts
- Track completed checks
- Maintain evidence references

Never put business logic here.

Never add RAG, embeddings, or a vector store.

---

## src/metadata/

The only place that reads table structure from Spark, and it reads it once per
investigation. Everything downstream consumes `InvestigationContext.metadata`.

---

## src/models/

Domain models shared across layers: `Finding`, `Investigation`,
`InvestigationState`, `InvestigationReport`.

No behaviour beyond the data itself.

---

## src/query/

Owns SQL only.

Responsibilities:

- Generate executable SQL
- Schema grounding
- Query execution
- Spark interaction

Never generate recommendations.

Never interpret business meaning.

---

## src/calculators/

Pure deterministic calculations.

Examples:

- Health score
- File statistics
- Distribution metrics

No LLM logic.

---

## src/reporting/

Consumes validated findings only.

The reporting layer must never invent conclusions.

Section order is fixed: Executive Summary, Root Causes, Evidence, SQL
Validation, Recommendations, Metadata Appendix.

---

## src/connectors/

Infrastructure only.

Responsibilities:

- Spark adapters
- LLM adapters
- Authentication
- Connection handling

No investigation logic.

---

# Execution Flow

```text
User selects table
        │
        ▼
Legacy Analyzer
(metadata + signals)
        │
        ▼
Context Manager
(compact investigation state)
        │
        ▼
Investigator (LLM)
        │
        ├── Form hypothesis
        ├── Choose next test
        ├── Generate SQL
        ├── Evaluate evidence
        └── Repeat if needed
        │
        ▼
Spark SQL
(evidence only)
        │
        ▼
Critic
(validate claims)
        │
        ▼
Final Report
```

The loop continues until confidence is sufficient.

---

# Investigation Context

The Context Manager owns one shared object.

```python
InvestigationContext(
    table_name,
    metadata,
    signals,
    completed_checks,
    evidence_refs,
    findings
)
```

## Keep

- schema summary
- partition summary
- file summary
- health signals
- previous conclusions

## Never Keep

- full DataFrames
- complete `$files` output
- manifest rows
- repeated SQL history
- verbose JSON blobs

Raw data stays in Spark or SQLite.

Only concise evidence enters prompts.

---

# Adaptive Investigation Loop

The Investigator must behave like an engineer.

## Step 1

Read metadata & signals.

Example:

```text
Rows: 667M
Files: 430 (68 MB avg)
Partition skew: HIGH
Sort order: Missing
```

## Step 2

Form a hypothesis.

Example:

> Partition pruning may be ineffective because a few partitions dominate table size.

## Step 3

Generate SQL.

## Step 4

Execute SQL.

## Step 5

Evaluate evidence.

## Step 6

Choose one:

- Conclude
- Investigate deeper

Never execute a fixed checklist.

The investigation order is dynamic.

---

# Prompt Rules

Prompts must be compact.

Preferred format:

```text
TABLE: sales

Rows: 667M
Files: 430
Avg File: 68 MB

Signals
- Partition skew: HIGH
- Missing sort order: HIGH

Completed
- Small file analysis: PASS
```

Avoid giant JSON.

Avoid Markdown reports.

Avoid duplicated metadata.

---

# Evidence Rules

Every finding MUST contain:

- Question
- Verdict
- Exact result
- Rationale
- Evidence ID
- Confidence
- Recommendation

Example:

```yaml
Question:
Is partition pruning ineffective?

Verdict:
Confirmed

Evidence:
E-004

Confidence:
0.94

Recommendation:
Repartition using day(region)
```

No evidence = no finding.

---

# Reporting Rules

The report order is fixed.

1. Executive Summary
2. Root Causes
3. Evidence
4. SQL Validation
5. Recommendations
6. Metadata Appendix

Never start with row count.

Engineers care about conclusions first.

---

# Model Delegation Policy

Claude Code must delegate based on task complexity.

## Sonnet (Default Implementation Model)

Use Sonnet for:

- Bug fixes
- Feature implementation
- SQL tools
- Refactoring
- Unit tests
- Parser fixes
- UI changes
- Documentation
- Integration work

Expected workload: **90%**

Constraint:

Do not redesign architecture.

---

## Opus (Architecture Model)

Use Opus only for high-level design.

Delegate when changing:

- Investigation workflow
- State model
- Context management
- Prompt strategy
- Multi-module architecture
- Performance architecture
- Cross-cutting refactors

Opus outputs:

1. Design
2. Trade-offs
3. File modification plan
4. Migration strategy

**Opus does not implement production code.**

Implementation returns to Sonnet.

---

# Decision Matrix

| Task | Delegate |
|------|----------|
| Bug fix | Sonnet |
| New investigator | Sonnet |
| SQL generation | Sonnet |
| Tests | Sonnet |
| UI | Sonnet |
| Refactor within module | Sonnet |
| Context redesign | Opus |
| State redesign | Opus |
| Investigator workflow | Opus |
| Architecture review | Opus |
| Implement approved design | Sonnet |

---

# Before Writing Code

Claude must answer these questions internally.

### 1. Which module owns this responsibility?

If unsure, stop.

### 2. Does this add reasoning to Legacy Analyzer?

If yes, reject the approach.

### 3. Can metadata be reused instead of reading Spark again?

Always prefer cached metadata.

### 4. Is this architectural?

If yes:

Design with Opus.

Implement with Sonnet.

---

# Forbidden Changes

Never do the following.

- Remove Investigator
- Bypass Investigator
- Replace reasoning with if/else rules
- Move recommendations into Legacy Analyzer
- Add vector RAG for metadata
- Re-read Iceberg metadata repeatedly
- Generate findings without evidence
- Hardcode investigation order
- Store large SQL results in prompt context

---

# Success Criteria

A completed investigation must answer five questions.

### 1. What is wrong?

Clear root cause.

### 2. Why is it happening?

Evidence-based explanation.

### 3. What proves it?

SQL + metadata evidence.

### 4. How confident is the conclusion?

Explicit confidence score.

### 5. What should the engineer do next?

Actionable recommendation backed by evidence.

If any of these five answers are missing, the implementation is considered incomplete.

---

# One Sentence That Must Never Be Violated

> **The Legacy Analyzer measures facts. The Investigator reasons over those facts. Any interpretation, prioritization, recommendation, or diagnosis belongs exclusively to `src/investigator/`.**