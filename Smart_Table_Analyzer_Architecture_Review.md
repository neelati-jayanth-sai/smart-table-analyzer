
# Smart Table Analyzer — Brutal Architecture Review & Fix Plan

**Date:** 2026-08-24

> Goal: Build an MVP that genuinely saves Data Engineers investigation time while keeping the Legacy Analyzer and LLM-powered Investigator as the core architecture.

---

# Executive Verdict

**Current score:** 6.5/10

The project has a strong idea but weak integration. The Legacy Analyzer is excellent, the Investigator concept is valuable, but the execution flow prevents the LLM from behaving like an actual investigator.

**Do not rewrite the project.** Fix the architecture and data flow.

---

# Core Design Principle

## Responsibilities

| Component | Responsibility |
|-----------|----------------|
| Legacy Analyzer | Collect metadata once & generate deterministic signals |
| Context Manager | Hold investigation state & build compact LLM context |
| Investigator | Generate hypotheses, choose tests, reason over evidence |
| Spark | Execute only requested SQL/evidence queries |
| Critic | Validate findings & confidence |
| Report Generator | Produce engineer-focused report |

---

# Current Problems

## P0 — Smart Table Analyzer bypasses the Investigator

### Problem

The analyzer performs metadata collection and scoring, but the Investigator is not consistently the primary execution path.

### Impact

- LLM reasoning is skipped.
- Reports become metadata summaries.
- Intelligence appears fake.

### Fix

Pipeline must always be:

```text
User
 ↓
Legacy Analyzer
 ↓
Context Manager
 ↓
Investigator
 ↓
Evidence
 ↓
Report
```

---

## P0 — Legacy Analyzer produces reports instead of context

### Problem

The strongest logic already exists:

- file statistics
- partitions
- snapshots
- sort order
- health metrics

But it outputs reports instead of reusable investigation state.

### Fix

Return:

```text
InvestigationContext
├── metadata
├── signals
├── baseline
└── runtime
```

Never generate recommendations inside the Legacy Analyzer.

---

## P0 — Investigation status is misleading

### Current

```text
Status: Completed

Finding:
hook_failed
```

This is incorrect.

### Fix

Use separate states:

- Metadata collected
- Planning complete
- Checks running
- Evidence validated
- Investigation completed
- Investigation failed

Never mark completed unless evidence exists.

---

# P1 Issues

## Hook failure is a single point of failure

### Problem

One failed hook kills the investigation.

### Fix

```text
Hook fails
 ↓
Log error
 ↓
Fallback execution
 ↓
Continue investigation
```

The report should contain a warning—not an empty finding.

---

## Fixed checks are not intelligent

### Current

Every table gets similar checks.

### Desired

The Investigator should decide.

Example:

Input:

```text
430 files
68 MB average
Small-file ratio low
Partition skew high
```

LLM decides:

- Skip small files
- Investigate partition skew
- Generate SQL
- Validate result

No deterministic branching.

---

## No investigation loop

### Current

```text
Metadata
 ↓
LLM
 ↓
Report
```

### Required

```text
Metadata
 ↓
Hypothesis
 ↓
SQL Test
 ↓
Evidence
 ↓
Need another test?
 ├── Yes → repeat
 └── No → conclude
```

This is the biggest intelligence improvement.

---

# P2 Issues

## Missing Context Manager

A lightweight Context Manager is required.

### Responsibilities

- Cache metadata once
- Track completed checks
- Store evidence IDs
- Build compact prompt

### It should NOT

- Use RAG
- Use embeddings
- Use vector databases
- Be another agent

Keep it simple.

---

## Repeated Spark metadata reads

### Problem

Multiple components read Iceberg metadata independently.

### Fix

Read once.

Cache forever during investigation.

Everything uses cached metadata.

---

## Context becomes too large

### Problem

Raw SQL results remain in memory.

### Fix

Keep only:

```text
Completed:
✓ Partition skew confirmed
✓ Small files dismissed
```

Persist full results to SQLite.

---

# P3 Issues

## Findings lack evidence

Every finding should contain:

- Evidence ID
- SQL used
- Confidence
- Metadata source

Example:

```text
Finding:
Partition skew

Evidence:
E-003

Confidence:
0.94
```

---

## Health score has no explanation

Replace:

```text
Health: 53
```

With:

| Evidence | Impact |
|----------|-------|
| Partition skew | -22 |
| Missing sort | -15 |
| Healthy files | +8 |

Final Score: 71

Engineers trust evidence, not numbers.

---

## Report structure is wrong

### Current

- Rows
- Files
- Partitions
- Health

### Better

1. Executive Summary
2. Root Cause
3. Evidence
4. SQL Validation
5. Recommendations
6. Metadata Appendix

The first page should answer:

> What is wrong?

Not:

> How many rows exist?

---

# Recommended Architecture

```text
                User
                  │
                  ▼
      Legacy Analyzer (Spark)
  Metadata + Signals (ONE READ)
                  │
                  ▼
         Context Manager
      Cache + State + Prompt
                  │
                  ▼
      Investigator (GPT-OSS)
   Hypothesis → Test → Reason
                  │
                  ▼
          Spark SQL Runner
      Only when evidence needed
                  │
                  ▼
              Critic
      Validate confidence
                  │
                  ▼
        Engineer Report + DB
```

---

# Investigation Context

```text
InvestigationContext
│
├── metadata
│   ├── schema
│   ├── files
│   ├── partitions
│   ├── snapshots
│   └── properties
│
├── signals
│   ├── partition_skew
│   ├── small_files
│   ├── sort_order
│   └── manifest_health
│
├── completed_checks
│
├── evidence
│
└── findings
```

This is the single source of truth.

---

# MVP Roadmap

## Phase 1 (Must Have)

- [ ] Legacy Analyzer returns InvestigationContext
- [ ] Add lightweight Context Manager
- [ ] Investigator becomes mandatory execution path
- [ ] Remove misleading completed status
- [ ] Cache all metadata once

## Phase 2

- [ ] Adaptive hypothesis generation
- [ ] Investigation loop
- [ ] Evidence registry
- [ ] Confidence scoring

## Phase 3

- [ ] Better report UX
- [ ] SQL explanation
- [ ] Trend analysis across snapshots

---

# What Will Impress a Manager?

## Valuable

- Finds the actual root cause
- Generates validation SQL
- Explains why performance is bad
- Produces evidence-backed recommendations
- Saves 30–60 minutes of investigation

## Not Valuable

- Generic health scores
- AI summaries without evidence
- Repeated metadata
- Static recommendations
- RAG or vector databases

---

# Final Verdict

| Area | Score |
|------|------:|
| Problem Selection | 10/10 |
| Legacy Analyzer | 9/10 |
| Investigator Concept | 8/10 |
| Current Integration | 5/10 |
| Report Quality | 4/10 |
| MVP Readiness | **6.5/10** |

**Target after fixes:** **8.5–9/10**

The architecture does **not** need more agents. It needs a clean execution flow where the Legacy Analyzer provides facts, the Context Manager manages state, and the Investigator performs adaptive reasoning over evidence.
