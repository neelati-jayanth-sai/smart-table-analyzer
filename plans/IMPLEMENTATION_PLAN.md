---
agent: devin-local
session: aboard-department
created: 2026-08-13T12:03:12Z
---
# Smart Table Analyzer Investigation Harness - MVP Implementation Plan

Build a **future-proof**, **extensible** adaptive investigation system using LangGraph for workflow orchestration that produces trustworthy, evidence-backed table diagnostics per Architecture.md.

## Executive Summary

**Goal**: Production-ready codebase designed for long-term evolution and feature additions.

**Key Architectural Decisions**:
1. **LangGraph 1.x** - Stable state machine workflow (not ad-hoc loops)
2. **Query Safety Hooks** - 5-layer defense against non-SELECT queries
3. **Plugin Architecture** - Easy to add investigation domains without code changes
4. **Adapter Pattern** - Swap LLM providers, query engines, telemetry without breaking code
5. **Schema Migrations** - Database evolves safely with rollback capability
6. **Feature Flags** - Ship features incrementally, A/B test, easy rollback
7. **Versioned APIs** - Reports, schemas versioned (no breaking changes)
8. **Comprehensive Tests** - Unit, integration, E2E with 80%+ coverage
9. **CI/CD Pipeline** - Auto-enforce quality gates (200-line limit, types, tests)
10. **Living Documentation** - Extension guides, API references, migration paths

## Implementation Status

| Phase | Status | Key Output | Verification |
|---|---|---|---|
| Phase 1: Database schema + migrations | ✅ Complete | `src/database/`, `schema/investigation.sql` | `scripts/test_investigation_db.py` passes |
| Phase 2: Query safety hooks + workbench | ✅ Complete | `src/query/query_hooks.py`, `query_workbench.py` | `scripts/test_query_workbench_smoke.py` passes |
| Phase 3: LangGraph workflow | ✅ Complete | `src/investigator/` graph nodes + state | `scripts/test_graph_flow.py` passes |
| Phase 4: LLM integration + real Spark test | ✅ Complete | `src/connectors/dell_aia_adapter.py` | `scripts/test_graph_flow_real.py` passes |
| Phase 5: Claim validation + reporting | ✅ Complete | `src/validation/`, `src/reporting/` | Report files generated and validated |
| Phase 6: CLI + end-to-end test | ✅ Complete | `scripts/run_investigation.py`, `test_end_to_end.py` | CLI and E2E tests pass |

**First real-table report generated**: `eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev` with 3 validated findings.

## Architectural Decision: LangGraph-Based Orchestration

**LangGraph** will control the entire investigation flow as a state machine, replacing ad-hoc loop management with a proper graph-based workflow framework. This provides:

- **State Management**: Structured investigation state with automatic persistence
- **Graph-based Flow**: Nodes (check steps) and edges (transitions) make logic explicit
- **Built-in Retry**: Native support for retries with backoff
- **Tool Integration**: First-class LLM tool calling support
- **Checkpointing**: Investigation state saved at each step for recovery
- **Debuggability**: Visual graph representation and state inspection

**Skills to Invoke**:

- `/codebase-design` - For designing module interfaces and seams
- `/domain-modeling` - For investigation domain terminology

## Critical Security Feature: Query Safety Hooks

**Defense in Depth** - 5 layers of protection against non-SELECT queries:

1. **Database Credential**: Read-only IOMETE role (cannot write even if SQL bypassed)
2. **Hook Pipeline**: Modular validation before execution
   - `ReadOnlyHook` - Blocks INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.
   - `SingleStatementHook` - Prevents batched queries (`SELECT; DROP TABLE`)
   - `NoFilePathHook` - Blocks file system access (LOAD, COPY, file://)
   - `SchemaWhitelistHook` - Restricts to approved catalogs/schemas
3. **SQL Parsing**: sqlparse validates query structure
4. **Timeout**: 30-second limit (prevents runaway queries)
5. **Snapshot Pinning**: All queries use fixed snapshot (consistency)

**Hook violations are logged** to investigation database for audit trail.

**Query Execution Flow**:

```text
LLM generates SQL
     ↓
SingleStatementHook → [REJECT if multiple statements]
     ↓
ReadOnlyHook → [REJECT if not SELECT/SHOW/DESCRIBE]
     ↓
NoFilePathHook → [REJECT if file:// or LOAD/COPY]
     ↓
SchemaWhitelistHook → [REJECT if unauthorized schema]
     ↓
Apply Snapshot Pinning (rewrite table references)
     ↓
Execute with 30s Timeout
     ↓
Return Result to LLM
```

**Example Hook Rejections**:

- `INSERT INTO table VALUES (1)` → ❌ ReadOnlyHook: "INSERT not allowed"
- `SELECT 1; DROP TABLE users` → ❌ SingleStatementHook: "Multiple statements detected"
- `LOAD DATA FROM 'file://data.csv'` → ❌ NoFilePathHook: "File access blocked"
- `SELECT * FROM other_db.schema.table` → ❌ SchemaWhitelistHook: "Schema not whitelisted"
- `SELECT * FROM eds_it_dev.elh_comn.table` → ✅ All hooks pass

## Current State Assessment

### ✅ Already Complete

**Stage 0a - Model Selection**: Dell AIA Gateway (gpt-oss-120b) is operational

- Authentication working (Basic Auth with server-side token refresh)
- API tested and responding correctly
- 131K token context window confirmed

**Stage 0b - Knowledge Base Content**: 16 production entries validated

- `knowledge/iceberg/` - 9 entries (partition transforms, file sizing, manifests, etc.)
- `knowledge/iomete/` - 1 entry (table maintenance behavior)
- `knowledge/runbooks/` - 3 entries (maintenance schedule, partition strategy, file size standards)
- All entries fact-checked against source docs

**Stage 1 - Foundation Components**:

- `src/calculators/health_score_calculator.py` - 6-dimension health scoring (frozen, working)
- `scripts/knowledge_retrieval.py` - List/fetch operations over SQLite index
- `scripts/init_knowledge_db.py` - Knowledge index population
- IOMETE read-only connection - Tested with Spark Connect, 264 tables accessible

**Stage 3 - Knowledge Retrieval Mechanism**:

- List-then-fetch implemented in `knowledge_retrieval.py`
- SQLite index schema defined
- Version tracking per entry

**Infrastructure**:

- `.env` - All credentials configured and tested
- `authentication_provider.py` - Dell AIA Gateway OAuth
- SSL certificates - Installed and working for both IOMETE and LLM

### ❌ Missing Components (To Build)

**Stage 1**: SQLite investigation schema (trails, findings, baseline score storage)

**Stage 2**: Query Workbench (validation, timeout, snapshot pinning)

**Stage 4**: Investigator loop + trail compaction

**Stage 5**: Claim Validator + Report assembly

**Integration**: Wire all stages together for end-to-end run

---

## Implementation Plan

### Phase 1: Complete Stage 1 (Investigation Database Schema)

**File**: `src/database/investigation_schema.py`

Create SQLite schema for:

- `investigations` - Run metadata (table name, start time, status, baseline score)
- `investigation_trail` - Query execution log (query text, results, timestamp, check number)
- `investigation_findings` - Compacted check records (question, result value, verdict, rationale)
- `knowledge_references` - Knowledge entries consulted (source, topic path, version, timestamp)
- `hook_violations` - **NEW**: Blocked queries (query text, hook name, reason, timestamp) for security audit
- `knowledge_index` - Topic path → current version (already exists, verify schema)

**File**: `src/database/investigation_db.py`

Module providing:

- `create_investigation(table_name: str) -> int` - Start new investigation, return ID
- `record_baseline_score(investigation_id: int, score_result: HealthScoreResult)` - Store 6-dimension breakdown
- `record_query(investigation_id: int, check_num: int, query: str, result: Any)` - Log query execution
- `record_finding(investigation_id: int, check_num: int, finding: Finding)` - Store compacted check
- `record_knowledge_fetch(investigation_id: int, source: str, path: str, version: str)` - Log knowledge access
- `get_investigation(investigation_id: int) -> Investigation` - Retrieve full investigation state

**Script**: `scripts/init_investigation_db.py`

CLI tool to:

- Create `data/investigation.db` if missing
- Initialize both knowledge_index and investigation tables
- Populate knowledge_index from existing markdown files

---

### Phase 2: Build Stage 2 (Query Workbench with Safety Hooks)

**File**: `src/query/query_hooks.py`

Multi-layer query safety hooks (executed in order):

```python
class QueryHook:
    """Base class for query validation hooks."""
    def validate(self, query: str) -> tuple[bool, Optional[str]]:
        """Returns (is_valid, error_message)"""
        raise NotImplementedError

class ReadOnlyHook(QueryHook):
    """Ensure only SELECT/SHOW/DESCRIBE queries."""
    ALLOWED_STATEMENTS = {'SELECT', 'SHOW', 'DESCRIBE', 'EXPLAIN'}
    FORBIDDEN_KEYWORDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE',
        'LOAD', 'COPY', 'EXPORT', 'IMPORT'
    }
    
    def validate(self, query: str) -> tuple[bool, Optional[str]]:
        # Parse SQL and check statement type
        # Reject if not in ALLOWED_STATEMENTS
        # Reject if contains FORBIDDEN_KEYWORDS
        pass

class SingleStatementHook(QueryHook):
    """Ensure only one statement (no semicolon-separated batches)."""
    def validate(self, query: str) -> tuple[bool, Optional[str]]:
        # Count statements, reject if > 1
        pass

class NoFilePathHook(QueryHook):
    """Block file path access (LOAD, external tables)."""
    def validate(self, query: str) -> tuple[bool, Optional[str]]:
        # Regex check for file:// or local paths
        pass

class SchemaWhitelistHook(QueryHook):
    """Ensure queries only access allowed schemas."""
    def __init__(self, allowed_catalogs: list[str], allowed_schemas: list[str]):
        self.allowed_catalogs = allowed_catalogs
        self.allowed_schemas = allowed_schemas
    
    def validate(self, query: str) -> tuple[bool, Optional[str]]:
        # Parse table references, check catalog.schema
        pass
```

**File**: `src/query/query_workbench.py`

Module implementing query execution with hook pipeline:

```python
class QueryWorkbench:
    def __init__(self, 
                 spark_session, 
                 hooks: list[QueryHook],
                 snapshot_id: Optional[str] = None, 
                 timeout_seconds: int = 30):
        self.spark = spark_session
        self.hooks = hooks
        self.snapshot_id = snapshot_id
        self.timeout = timeout_seconds
    
    def validate_query(self, query: str) -> ValidationResult:
        """Run query through all hooks in order."""
        for hook in self.hooks:
            is_valid, error = hook.validate(query)
            if not is_valid:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"{hook.__class__.__name__}: {error}",
                    rewritten_query=None
                )
        
        # All hooks passed - rewrite for snapshot if needed
        rewritten = self._apply_snapshot_pinning(query)
        return ValidationResult(
            is_valid=True,
            error_message=None,
            rewritten_query=rewritten
        )
    
    def execute_query(self, query: str) -> QueryResult:
        """Validate, rewrite, execute with timeout."""
        # 1. Validate through hooks
        validation = self.validate_query(query)
        if not validation.is_valid:
            return QueryResult(
                success=False,
                error=validation.error_message,
                rows=None,
                schema=None
            )
        
        # 2. Execute with timeout
        try:
            df = self.spark.sql(validation.rewritten_query)
            # Set query timeout at Spark level
            df = df.option("spark.sql.execution.timeout", f"{self.timeout}s")
            
            rows = df.collect()
            schema = df.schema
            
            return QueryResult(
                success=True,
                rows=rows,
                schema=schema,
                execution_time=...,
                query_executed=validation.rewritten_query
            )
        except Exception as e:
            return QueryResult(
                success=False,
                error=str(e),
                rows=None,
                schema=None
            )
    
    def _apply_snapshot_pinning(self, query: str) -> str:
        """Rewrite table references to use snapshot."""
        if not self.snapshot_id:
            return query
        # Parse and rewrite: table -> table.snapshots.{snapshot_id}
        # Or use Iceberg time-travel syntax
        pass
```

**File**: `src/query/hook_factory.py`

Factory for creating standard hook pipeline:

```python
def create_investigation_hooks(
    allowed_catalogs: list[str],
    allowed_schemas: list[str]
) -> list[QueryHook]:
    """Create standard hook pipeline for investigations."""
    return [
        SingleStatementHook(),        # First: reject batches
        ReadOnlyHook(),               # Second: reject writes
        NoFilePathHook(),             # Third: block file access
        SchemaWhitelistHook(          # Fourth: check schema access
            allowed_catalogs=allowed_catalogs,
            allowed_schemas=allowed_schemas
        )
    ]
```

**Integration with LangGraph**:

The `execute_query` graph node will use the workbench:

```python
def execute_with_workbench(state: InvestigationState) -> InvestigationState:
    """Execute query through safety hooks."""
    result = workbench.execute_query(state["current_query"])
    
    # Log hook violations
    if not result.success and "Hook" in result.error:
        logger.warning(f"Query blocked by hook: {result.error}")
        db.record_hook_violation(
            investigation_id=state["investigation_id"],
            query=state["current_query"],
            hook_error=result.error
        )
    
    return {**state, "query_result": result, "execution_status": result.status}
```

**Script**: `scripts/test_query_workbench.py`

Comprehensive hook testing:

```python
def test_hooks():
    """Test each hook independently."""
    # Test ReadOnlyHook
    assert ReadOnlyHook().validate("SELECT * FROM table")[0] == True
    assert ReadOnlyHook().validate("INSERT INTO table")[0] == False
    assert ReadOnlyHook().validate("DROP TABLE table")[0] == False
    
    # Test SingleStatementHook
    assert SingleStatementHook().validate("SELECT 1")[0] == True
    assert SingleStatementHook().validate("SELECT 1; DROP TABLE x")[0] == False
    
    # Test NoFilePathHook
    assert NoFilePathHook().validate("SELECT * FROM table")[0] == True
    assert NoFilePathHook().validate("LOAD DATA FROM 'file://'")[0] == False
    
    # Test SchemaWhitelistHook
    hook = SchemaWhitelistHook(['eds_it_dev'], ['elh_comn'])
    assert hook.validate("SELECT * FROM eds_it_dev.elh_comn.table")[0] == True
    assert hook.validate("SELECT * FROM other_catalog.schema.table")[0] == False

def test_hook_pipeline():
    """Test full hook pipeline integration."""
    hooks = create_investigation_hooks(['eds_it_dev'], ['elh_comn'])
    workbench = QueryWorkbench(spark, hooks)
    
    # Valid query should pass
    result = workbench.execute_query("SELECT * FROM eds_it_dev.elh_comn.test")
    assert result.success == True
    
    # Invalid queries should be blocked
    test_cases = [
        "DROP TABLE test",
        "INSERT INTO test VALUES (1)",
        "SELECT 1; DROP TABLE test",
        "LOAD DATA FROM 'file://path'",
        "SELECT * FROM unauthorized.schema.table"
    ]
    
    for bad_query in test_cases:
        result = workbench.execute_query(bad_query)
        assert result.success == False
        assert "Hook" in result.error or "not allowed" in result.error
```

---

### Phase 3: Build Stage 4 (Investigator Loop with LangGraph) — Detailed Node Specification

**Objective**: Define every graph node's inputs, outputs, dependencies, work, and verification logic with no ambiguity.

---

#### Dependency and Data Flow Analysis

Before defining nodes, these dependencies exist:

| Layer | Depends On | Provides | Output Type |
|---|---|---|---|
| **Investigator** | graph app, LLM adapter, workbench, database, knowledge retrieval | InvestigationResult | Final report-ready findings |
| **Graph** | all node functions + state schema | Compiled LangGraph app | Orchestrated execution + checkpointing |
| **decide_check node** | baseline score, prior findings, table metadata, LLM | `current_question` + `check_type` | Natural language question |
| **fetch_knowledge node** | `current_question`, knowledge index, LLM | `knowledge_consulted` | List of fetched knowledge entries |
| **generate_query node** | `current_question`, `knowledge_consulted`, LLM | `current_query` | Valid SQL string candidate |
| **execute_query node** | `current_query`, Query Workbench | `query_result`, `execution_status` | Executed result or error |
| **analyze_result node** | `query_result`, `knowledge_consulted`, LLM | `current_analysis` | Structured analysis |
| **compact_finding node** | `current_question`, `query_result`, `current_analysis` | `findings` + persisted record | Compacted finding |
| **route_after_execution** | `execution_status`, `retry_count` | Edge name | Conditional routing decision |
| **check_budget** | `check_count`, `max_checks`, optional LLM | Edge name | Continue or complete |

Every node's output is **explicitly verified** before being allowed into state.

---

#### State Schema

**File**: `src/investigator/investigation_graph.py`

```python
from typing import Optional
from typing_extensions import TypedDict

class QueryResult(TypedDict, total=False):
    success: bool
    query: str                    # The SQL that was actually executed
    rewritten_query: str          # SQL after snapshot pinning
    rows: list[dict]              # Up to 50 rows, JSON-serialized
    schema: list[dict]            # Column names and types
    row_count: int                # Exact or approximate row count
    execution_time_ms: int        # How long query took
    error: Optional[str]          # Error message if failed
    hook_violation: Optional[str] # Which hook blocked, if any

class Finding(TypedDict, total=False):
    check_num: int
    question: str
    exact_result: str             # Literal, copied output from query
    verdict: str                  # One-line: "found", "not_found", "inconclusive", "could_not_verify"
    rationale: str                # 200 chars max, explains exact_result
    evidence_ids: list[str]       # trail:{check_num} + knowledge:{source}/{path}@{version}
    recommendation: Optional[str] # Actionable next step or null
    alternatives: list[str]       # Other options considered

class KnowledgeReference(TypedDict, total=False):
    source: str                   # iceberg, iomete, runbooks
    topic_path: str
    version: str                  # 12-char hash
    content: str                  # Full markdown content fetched

class InvestigationState(TypedDict, total=False):
    investigation_id: int
    table_name: str
    baseline_score: dict          # 6-dimension breakdown, not HealthScoreResult object
    check_count: int
    max_checks: int
    retry_count: int
    max_retries: int
    status: str                  # "running", "completed", "failed", "aborted"
    current_question: Optional[str]
    current_query: Optional[str]
    query_result: Optional[QueryResult]
    execution_status: str        # "success", "hook_failed", "timeout", "error"
    current_analysis: Optional[dict]
    knowledge_consulted: list[KnowledgeReference]
    findings: list[Finding]
    messages: list[dict]          # Conversation history with LLM (optional but useful for debug)

# File: src/investigator/investigation_graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

graph = StateGraph(InvestigationState)

graph.add_node("decide_check", decide_next_check)
graph.add_node("fetch_knowledge", fetch_relevant_knowledge)
graph.add_node("generate_query", generate_sql_query)
graph.add_node("execute_query", execute_with_workbench)
graph.add_node("analyze_result", analyze_query_result)
graph.add_node("compact_finding", compact_to_trail)

graph.set_entry_point("decide_check")
graph.add_edge("decide_check", "fetch_knowledge")
graph.add_edge("fetch_knowledge", "generate_query")
graph.add_edge("generate_query", "execute_query")
graph.add_conditional_edges(
    "execute_query",
    route_after_execution,
    {
        "success": "analyze_result",
        "retry": "generate_query",
        "failed": "compact_finding"
    }
)
graph.add_edge("analyze_result", "compact_finding")
graph.add_conditional_edges(
    "compact_finding",
    check_budget,
    {
        "continue": "decide_check",
        "complete": END
    }
)

app = graph.compile(checkpointer=SqliteSaver(conn=sqlite3.connect(db_path, check_same_thread=False)))
```

---

#### Node 1: `decide_next_check`

**Purpose**: Decide what question to ask next.

**Input**: `InvestigationState`

**Dependencies**:
- LLM adapter (Dell AIA Gateway)
- `baseline_score` (6 dimensions from health calculator)
- `findings` (already compacted)
- `check_count`, `max_checks`
- `table_name` and schema/catalog

**Work Performed**:
1. Build a compact context message to LLM with:
   - Table name
   - Baseline score breakdown (informal context only, never used as evidence)
   - Current check number and remaining budget
   - List of already-answered questions and verdicts (compacted, not full trail)
2. Ask LLM to propose one focused question for the next check.
3. Enforce output schema: `{"check_type": "layout|file_size|partitioning|skew|sort", "question": "...", "rationale": "..."}`

**Output**:
```json
{
  "current_question": "Are partition files within the recommended 128-512 MB range?",
  "check_type": "file_size",
  "decision_rationale": "Baseline score showed low file_size subscore."
}
```

**Verification**:
- `current_question` must not be empty
- `current_question` must end with `?`
- `check_type` must be in allowed set
- Duplicate question detected? If yes, reformulate or skip

**Failure Handling**:
- If LLM output is malformed → retry up to 2 times
- After 2 failures, mark `current_question` as "unspecified" and `check_type` as "general"
- Continue to next node; no hard stop

**Persist** to `investigation_trail`:
- check_num
- node name
- LLM prompt (compressed)
- LLM response (raw)
- timestamp

---

#### Node 2: `fetch_relevant_knowledge`

**Purpose**: Retrieve curated knowledge entries that are relevant to the current question.

**Input**: `InvestigationState` (uses `current_question` and `check_type`)

**Dependencies**:
- Knowledge index in SQLite (`scripts/knowledge_retrieval.py`)
- LLM adapter (for path selection)
- `knowledge/` markdown files

**Work Performed**:
1. Call `list_knowledge_paths(source, prefix=check_type)` for each source (`iceberg`, `iomete`, `runbooks`).
2. Present list to LLM with current question.
3. LLM selects exact paths to fetch.
4. Call `fetch_knowledge_path(source, path)` for each selected path.
5. Store fetched entries with versions.
6. If selected path does not exist, return empty and log warning.

**Output**:
```json
{
  "knowledge_consulted": [
    {
      "source": "iceberg",
      "topic_path": "file-sizing-best-practices",
      "version": "a3f8e91c",
      "content": "# File Sizing Best Practices\n..."
    },
    {
      "source": "runbooks",
      "topic_path": "daily-maintenance-schedule",
      "version": "7b2d4e9a",
      "content": "# Daily Maintenance Schedule\n..."
    }
  ]
}
```

**Verification**:
- Every `topic_path` must have come from `list_knowledge_paths` (no guessed paths)
- Every fetched entry must have a version hash
- Content is not truncated before storage
- Duplicate paths deduplicated

**Failure Handling**:
- If `knowledge_consulted` is empty after fetch, log `knowledge_gap`
- Allow investigation to continue, but analysis must note this gap

**Persist** to `knowledge_references` table:
- investigation_id
- source, topic_path, version
- timestamp

---

#### Node 3: `generate_sql_query`

**Purpose**: Produce a read-only SQL query that can answer `current_question` using available knowledge.

**Input**: `InvestigationState` (uses `current_question`, `knowledge_consulted`, `table_name`)

**Dependencies**:
- LLM adapter
- Table metadata (schema columns, partition columns from IOMETE)
- `knowledge_consulted`

**Work Performed**:
1. Build prompt containing:
   - `current_question`
   - Relevant knowledge entries
   - Table schema (column names, types, partition columns)
   - Allowed SQL subset (SELECT, SHOW, DESCRIBE, EXPLAIN)
   - Schema whitelist (`eds_it_dev.elh_comn`)
   - Output format constraint
2. Ask LLM to output a single SQL statement.
3. Parse LLM output and extract SQL.
4. Run through hook pipeline (ReadOnlyHook, SingleStatementHook, NoFilePathHook, SchemaWhitelistHook) immediately for a fast-fail check.

**Output**:
```json
{
  "current_query": "SELECT file_size_mb, count(*) FROM eds_it_dev.elh_comn.table_files GROUP BY file_size_mb ORDER BY count(*) DESC LIMIT 20",
  "query_intent": "Get distribution of file sizes to detect small or oversize files."
}
```

**Verification**:
- Query string is not empty
- Query passes hook pipeline
- Query references only allowed catalog/schema
- Query is a single statement (no `;` separating commands)
- No forbidden keywords

**Failure Handling**:
- If hook pipeline fails, increment `retry_count`
- If `retry_count` >= `max_retries`, set `execution_status` to "hook_failed" and route to `compact_finding`
- Otherwise route back to `generate_query` with error feedback

**Persist**:
- Generated query to `investigation_trail`
- Hook validation result (pass or fail)

---

#### Node 4: `execute_with_workbench`

**Purpose**: Run the generated SQL through the Query Workbench safely.

**Input**: `InvestigationState` (uses `current_query`)

**Dependencies**:
- `QueryWorkbench` instance
- Spark session (IOMETE connection)
- Snapshot pinning configuration

**Work Performed**:
1. Call `workbench.execute_query(current_query)`.
2. Workbench internally:
   - Validates through hook pipeline
   - Rewrites query for snapshot pinning
   - Runs with timeout (30s)
   - Collects up to 50 rows (configurable)
   - Returns structured result
3. Determine `execution_status`:
   - `success` if rows returned
   - `timeout` if query exceeded time limit
   - `hook_failed` if hook pipeline blocked
   - `error` if Spark returned an exception

**Output** (`QueryResult`):
```json
{
  "success": true,
  "query": "SELECT file_size_mb, count(*) FROM eds_it_dev.elh_comn.table_files GROUP BY file_size_mb ORDER BY count(*) DESC LIMIT 20",
  "rewritten_query": "SELECT file_size_mb, count(*) FROM eds_it_dev.elh_comn.table_files.snapshot_1234567890 GROUP BY file_size_mb ORDER BY count(*) DESC LIMIT 20",
  "rows": [
    {"file_size_mb": 8.5, "count(1)": 1247},
    {"file_size_mb": 256.0, "count(1)": 18}
  ],
  "schema": [
    {"name": "file_size_mb", "type": "double"},
    {"name": "count(1)", "type": "long"}
  ],
  "row_count": 2,
  "execution_time_ms": 1450,
  "error": null,
  "hook_violation": null
}
```

**Verification**:
- `success` is a boolean
- `rewritten_query` is captured, not just original
- `rows` is JSON-serializable (convert PySpark Row objects to dict)
- `row_count` matches actual rows returned
- If `success` is false, `error` is populated
- If `hook_violation` is present, log to `hook_violations` table

**Failure Handling**:
- Timeout: return `success=false`, `execution_status="timeout"`, truncate rows safely
- Hook violation: return `success=false`, `execution_status="hook_failed"`, log violation
- Spark error: return `success=false`, `execution_status="error"`, include exception message

**Persist** to `investigation_trail`:
- check_num
- generated query
- rewritten query
- result rows (truncated if large)
- execution_time_ms
- error message
- timestamp

---

#### Node 5: `analyze_query_result`

**Purpose**: Interpret the query result and form a structured finding.

**Input**: `InvestigationState` (uses `query_result`, `knowledge_consulted`, `current_question`)

**Dependencies**:
- LLM adapter
- `query_result`
- `knowledge_consulted`

**Work Performed**:
1. Build prompt containing:
   - `current_question`
   - Fetched knowledge entries
   - `query_result` (rows, schema, row_count, query text)
   - Instructions to use only this data, no general knowledge
2. Ask LLM for structured output:
   ```json
   {
     "verdict": "found|not_found|inconclusive",
     "exact_result": "Summary of exact numeric/string values",
     "rationale": "Short explanation in 200 chars max",
     "evidence_ids": ["trail:{check_num}", "knowledge:iceberg/file-sizing-best-practices@a3f8e91c"],
     "recommendation": "Actionable next step or null",
     "alternatives": ["Option A", "Option B"]
   }
   ```
3. Validate that `evidence_ids` point to real trail entries and knowledge references.

**Output** (`current_analysis`):
```json
{
  "verdict": "found",
  "exact_result": "1,247 files are 8.5 MB (below 128 MB target); 18 files are 256 MB (within target).",
  "rationale": "File size distribution shows most files are far below the recommended minimum, causing manifest bloat.",
  "evidence_ids": ["trail:3", "knowledge:iceberg/file-sizing-best-practices@a3f8e91c"],
  "recommendation": "Run ALTER TABLE ... REWRITE DATA FILES with target file size 256 MB.",
  "alternatives": ["Increase target to 512 MB if reads are large sequential scans.", "Do nothing if query latency is acceptable."]
}
```

**Verification**:
- `verdict` is in allowed enum
- `exact_result` is a factually faithful summary of `query_result` (not hallucinated)
- `rationale` ≤ 200 characters
- `evidence_ids` non-empty
- Each evidence ID resolves to an existing trail or knowledge reference
- `recommendation` (if provided) must be grounded in `knowledge_consulted` or `query_result`
- No claim made without evidence ID

**Failure Handling**:
- If LLM output is malformed → retry up to 2 times
- If evidence IDs cannot be validated → strip invalid IDs and add `validation_warning`
- If analysis is inconsistent with query result → mark `inconclusive` and log warning

**Persist** to `investigation_trail`:
- Raw LLM analysis response
- Validated `current_analysis`
- Validation warnings, if any

---

#### Node 6: `compact_to_trail`

**Purpose**: Convert the analysis into a fixed-format finding, save it, and update state.

**Input**: `InvestigationState` (uses `current_question`, `query_result`, `current_analysis`, `check_count`, `findings`)

**Dependencies**:
- `investigation_db` module
- `Finding` schema

**Work Performed**:
1. Construct `Finding` object:
   ```python
   finding = Finding(
       check_num=state["check_count"],
       question=state["current_question"],
       exact_result=state["current_analysis"]["exact_result"],
       verdict=state["current_analysis"]["verdict"],
       rationale=state["current_analysis"]["rationale"],
       evidence_ids=state["current_analysis"]["evidence_ids"],
       recommendation=state["current_analysis"].get("recommendation"),
       alternatives=state["current_analysis"].get("alternatives", [])
   )
   ```
2. Run `ClaimValidator` lightweight check:
   - Every evidence ID exists in this investigation
   - `exact_result` is non-empty
   - `verdict` is allowed
3. Persist finding to `investigation_findings` table.
4. Append finding to state `findings`.
5. Increment `check_count`.
6. Reset `retry_count` to 0.
7. Clear `current_question`, `current_query`, `query_result`, `current_analysis`, `knowledge_consulted` for next iteration.

**Output**:
```json
{
  "findings": [
    {
      "check_num": 3,
      "question": "Are partition files within the recommended 128-512 MB range?",
      "exact_result": "1,247 files are 8.5 MB (below 128 MB target); 18 files are 256 MB (within target).",
      "verdict": "found",
      "rationale": "File size distribution shows most files are far below the recommended minimum, causing manifest bloat.",
      "evidence_ids": ["trail:3", "knowledge:iceberg/file-sizing-best-practices@a3f8e91c"],
      "recommendation": "Run ALTER TABLE ... REWRITE DATA FILES with target file size 256 MB.",
      "alternatives": ["Increase target to 512 MB if reads are large sequential scans.", "Do nothing if query latency is acceptable."]
    }
  ],
  "check_count": 1,
  "retry_count": 0,
  "current_question": null,
  "current_query": null,
  "query_result": null,
  "current_analysis": null,
  "knowledge_consulted": []
}
```

**Verification**:
- Finding persisted successfully (INSERT returned row id)
- `check_count` incremented by exactly 1
- `findings` list grows by exactly 1
- No stale node state carried to next iteration
- For failed executions (timeout/hook_failed/error):
  - `verdict` = "could_not_verify"
  - `exact_result` = error summary
  - `recommendation` = null
  - finding is still persisted (gap is explicit, not hidden)

**Failure Handling**:
- If `ClaimValidator` finds missing evidence IDs:
  - Drop invalid IDs
  - Add validation warning to finding
  - Persist as `verdict="inconclusive"`
- If DB insert fails:
  - Set `status="failed"`
  - Route to END
  - Log exception

---

#### Edge Routing Functions

**`route_after_execution`**:

```python
def route_after_execution(state: InvestigationState) -> str:
    if state["execution_status"] == "success":
        return "success"
    elif state["retry_count"] < state["max_retries"]:
        return "retry"
    else:
        return "failed"
```

**Verification**:
- Returns one of `{"success", "retry", "failed"}`
- On `retry`, `retry_count` incremented by parent before re-entering `generate_query`
- On `failed`, `execution_status` remains non-success

**`check_budget`**:

```python
def check_budget(state: InvestigationState) -> str:
    if state["check_count"] >= state["max_checks"]:
        return "complete"
    return "continue"
```

**Verification**:
- Returns one of `{"continue", "complete"}`
- Hard stop at `max_checks` regardless of LLM preference
- Optional future: ask LLM whether it has enough information; MVP ignores LLM opinion to guarantee termination

---

#### Output of Each Query — Concrete Example

Below is the trace of one complete check for the question: "Are partition files within the recommended 128-512 MB range?"

**Check 3: File Size Distribution**

| Step | Node | Output | Verification |
|---|---|---|---|
| 1 | `decide_check` | `current_question` = "Are partition files within the recommended 128-512 MB range?" | Question ends with `?`, check_type allowed |
| 2 | `fetch_knowledge` | `knowledge_consulted` = `[iceberg/file-sizing-best-practices@v1, runbooks/maintenance-schedule@v2]` | Paths from list, versions exist |
| 3 | `generate_query` | `current_query` = `SELECT ... FROM eds_it_dev.elh_comn.table_files ...` | Hook pipeline passes, single statement, read-only |
| 4 | `execute_query` | `query_result.success=true`, rows show 8.5MB files dominate | Rewritten query pinned to snapshot, rows JSON-serializable |
| 5 | `analyze_result` | `current_analysis` with `verdict=found`, evidence IDs valid | Evidence IDs resolve, rationale ≤ 200 chars |
| 6 | `compact_finding` | `findings` list gains one entry | Persisted to DB, `check_count` increments |

**Final Output of This Check**:
```json
{
  "check_num": 3,
  "question": "Are partition files within the recommended 128-512 MB range?",
  "exact_result": "1,247 files are 8.5 MB (below 128 MB target); 18 files are 256 MB (within target).",
  "verdict": "found",
  "rationale": "File size distribution shows most files are far below the recommended minimum, causing manifest bloat.",
  "evidence_ids": ["trail:3", "knowledge:iceberg/file-sizing-best-practices@a3f8e91c"],
  "recommendation": "Run ALTER TABLE ... REWRITE DATA FILES with target file size 256 MB.",
  "alternatives": ["Increase target to 512 MB if reads are large sequential scans.", "Do nothing if query latency is acceptable."]
}
```

Every field is traceable to either:
- `trail:3` (the exact query executed and its result), or
- `knowledge:iceberg/file-sizing-best-practices@a3f8e91c` (the recommendation target file size comes from knowledge base)

---

#### Work Done by Each Agent / Node — Summary Table

| Node | Agent Role | What It Does | Output It Produces | Verification Rule | On Failure |
|---|---|---|---|---|---|
| `decide_check` | **Planner** | Chooses next question based on baseline score and previous findings | `current_question`, `check_type` | Non-empty, ends with `?`, allowed check_type | Retry 2x, then generic question |
| `fetch_knowledge` | **Researcher** | Lists and fetches curated knowledge entries | `knowledge_consulted` list | Paths from `list_knowledge`, all entries versioned | Log knowledge gap, continue |
| `generate_query` | **SQL Author** | Writes read-only SQL to answer question | `current_query` string | Passes hook pipeline, single statement, read-only | Retry up to max_retries |
| `execute_query` | **Executor** | Runs SQL through Query Workbench | `query_result`, `execution_status` | Result is JSON-serializable, snapshot pinned, timeout enforced | Route to retry or failed |
| `analyze_result` | **Interpreter** | Analyzes result and forms structured conclusion | `current_analysis` dict | Evidence IDs valid, rationale ≤200 chars, no hallucination | Retry 2x, then inconclusive |
| `compact_finding` | **Recorder** | Persists fixed-format finding to DB and state | Updated `findings`, `check_count` | Finding persisted, state reset for next check | Set status=failed, end |
| `route_after_execution` | **Router** | Decides retry vs analyze vs fail | Edge name | One of allowed routing keys | N/A |
| `check_budget` | **Controller** | Enforces max check budget | Edge name | Continue or complete | N/A |

---

#### State Transition Verification

Between every node, verify these invariants:

```python
INVARIANTS = [
    "investigation_id is always present",
    "check_count is non-negative and <= max_checks",
    "retry_count is non-negative and <= max_retries",
    "findings is a list",
    "current_query is None or non-empty string",
    "query_result.success is bool when query_result present",
    "current_analysis.evidence_ids non-empty when present",
    "findings[-1].check_num == check_count - 1 after compact"
]
```

**File**: `src/investigator/state_validator.py`

```python
def validate_state(state: InvestigationState) -> tuple[bool, list[str]]:
    """Check all state invariants."""
    errors = []
    if not state.get("investigation_id"):
        errors.append("Missing investigation_id")
    if state.get("check_count", 0) > state.get("max_checks", 0):
        errors.append("check_count exceeds max_checks")
    # ... all other invariants
    return len(errors) == 0, errors
```

This is called at the start of every node. If invariants are violated, graph aborts with detailed error.

---

#### Checkpoint and Recovery

**LangGraph 1.x Checkpointing**:
- Every node writes state to SQLite checkpoint table
- Thread ID = `investigation_id`
- If process crashes, investigation can resume from last completed node
- CLI command: `python scripts/resume_investigation.py --id {investigation_id}`

**Verification**:
- After each node, checkpoint exists in `investigation.db`
- `checkpointer.get(thread_id)` returns latest state
- Resumed state passes `validate_state`

---

#### Tools Exposed to LLM

| Tool | Input | Output | Node That Uses It |
|---|---|---|---|
| `list_knowledge` | `source`, optional `prefix` | List of `{topic_path, description}` | `fetch_relevant_knowledge` |
| `fetch_knowledge` | `source`, `topic_path` | `{content, version}` | `fetch_relevant_knowledge` |
| `execute_query` | `sql` | `QueryResult` (rows, schema, error) | `execute_with_workbench` |
| `submit_finding` | `Finding` | `{check_num}` | `compact_to_trail` |
| `request_trail_detail` | `check_num` | `{query, result, analysis}` | Optional: any node may call for context |
| `complete_investigation` | `summary` | `END` signal | Could be used by `decide_check` to terminate early (MVP: ignored) |

---

### Phase 4: Build Stage 5 (Claim Validation & Reporting)

**File**: `src/validation/claim_validator.py`

Minimal evidence-ID checker:

```python
class ClaimValidator:
    def __init__(self, investigation_db)
    
    def validate_finding(self, finding: Finding, investigation_id: int) -> ValidationResult:
        # Check each evidence ID exists in this investigation's trail
        # Query IDs → check investigation_trail table
        # Knowledge IDs → check knowledge_references table
        # Return: valid (bool), missing_ids (list), validation_errors (list)
```

**Rules**:

- Every claim must declare ≥1 evidence ID
- Every ID must exist in this run's trail or knowledge_references
- Invalid/missing ID → claim dropped, gap logged, included in report
- No content matching in MVP (deferred per §3)

**File**: `src/reporting/report_assembler.py`

Fixed-format report generation:

```python
class ReportAssembler:
    def __init__(self, investigation_db, claim_validator)
    
    def assemble_report(self, investigation_id: int) -> Report:
        # Fetch: investigation metadata, baseline score, all findings, knowledge refs
        # Validate all findings
        # Assemble into structured sections
```

**Report Structure**:

```markdown
# Investigation Report: {table_name}

## Executive Summary
- Overall Health: {score}/100
- Investigation Date: {timestamp}
- Checks Completed: {num_checks}
- Critical Findings: {num_critical}

## Baseline Score Breakdown
[6 dimensions with values]

## Findings
[For each validated finding:]
### Finding {N}: {question}
**Current State**: {exact_result_value}
**Evidence**: Query #{query_id}, Knowledge: {source}/{path}@{version}
**Gap**: {description}
**Recommendation**: {actionable_next_step}
[If recommendation exists]
**Alternatives Considered**: {other_options}

[For invalidated findings:]
### Finding {N}: VALIDATION FAILED
**Reason**: Missing evidence IDs: {list}

## Knowledge Base Consulted
[List of all knowledge entries referenced with versions]

## Investigation Metadata
- Investigation ID: {id}
- Total Queries: {count}
- Failed Validations: {count}
- Snapshot ID: {snapshot} [if applicable]
```

**Script**: `scripts/run_investigation.py`

CLI orchestrator:

```bash
python scripts/run_investigation.py \
    --table eds_it_dev.elh_comn.table_name \
    --catalog eds_it_dev \
    --schema elh_comn \
    --output reports/investigation_{timestamp}.md \
    [--snapshot {snapshot_id}] \
    [--max-checks 50]
```

**Flow**:

1. Initialize investigation DB (create if needed, populate knowledge index)
2. Connect to IOMETE via Spark Connect
3. Get current snapshot ID (or use provided)
4. Run health score calculator → baseline
5. Create investigation record
6. Run Investigator loop
7. Validate all findings
8. Assemble report
9. Write to output file
10. Print summary to console

---

### Phase 5: Integration & End-to-End Testing

**Test Script**: `scripts/test_end_to_end.py`

Full pipeline test:

1. Pick sample table from IOMETE (one with known issues)
2. Run complete investigation
3. Verify:
   - Database records created
   - All evidence IDs valid
   - Report format correct
   - No hallucinated knowledge paths
   - Findings trace to actual queries

**Sample Tables for Testing**:

From our IOMETE connection test, we have 264 tables. Pick 2-3 with different characteristics:

- Large table (667M rows) for file sizing checks
- Table with obvious skew for partition analysis
- Recently maintained table for snapshot checks

**Validation Criteria**:

- Every claim has ≥1 evidence ID
- Every evidence ID resolves to real trail entry
- No knowledge path guessing (all from list results)
- Report is human-readable and actionable
- Investigation completes within check budget

---

## File Structure (New Files to Create)

```text
src/
├── database/
│   ├── __init__.py
│   ├── investigation_schema.py    # SQLite schema definitions
│   ├── investigation_db.py         # Database access module
│   └── migrations/                 # NEW: Schema migrations for upgrades
│       ├── __init__.py
│       ├── 001_initial_schema.py
│       └── migration_manager.py
├── query/
│   ├── __init__.py
│   ├── query_hooks.py              # Individual validation hooks
│   ├── hook_factory.py             # Standard hook pipeline factory
│   ├── query_workbench.py          # Query execution with hook pipeline
│   └── custom_hooks/               # NEW: Extensibility for custom hooks
│       └── __init__.py
├── investigator/
│   ├── __init__.py
│   ├── investigation_graph.py      # LangGraph workflow definition
│   ├── graph_nodes.py              # Individual node implementations
│   ├── investigator.py             # Orchestrator (wraps graph)
│   ├── tools.py                    # LLM tool definitions
│   ├── domain_interface.py         # NEW: ABC for investigation domains
│   └── domains/                    # NEW: Pluggable investigation domains
│       ├── __init__.py
│       └── layout_domain.py        # MVP domain (partitioning, files, skew)
├── connectors/
│   ├── __init__.py
│   ├── llm_adapter.py              # NEW: ABC for LLM providers
│   ├── dell_aia_adapter.py         # Current LLM adapter
│   └── spark_adapter.py            # NEW: ABC for query engines
├── validation/
│   ├── __init__.py
│   └── claim_validator.py          # Evidence ID validation
├── reporting/
│   ├── __init__.py
│   ├── report_schema.py            # NEW: Versioned report format
│   └── report_assembler.py         # Report generation
├── config/
│   ├── __init__.py
│   └── feature_flags.py            # NEW: Feature toggle system
└── observability/
    ├── __init__.py
    ├── telemetry.py                # NEW: Telemetry interface (ABC)
    └── null_telemetry.py           # NEW: No-op implementation for MVP

scripts/
├── init_investigation_db.py        # Database initialization
├── run_investigation.py            # CLI orchestrator
├── test_query_workbench.py         # Query workbench tests
├── test_graph_flow.py              # LangGraph workflow tests
└── test_end_to_end.py              # Full pipeline test

tests/                              # NEW: Comprehensive test suite
├── unit/
│   ├── test_hooks.py
│   ├── test_graph_nodes.py
│   └── test_validators.py
├── integration/
│   ├── test_hook_pipeline.py
│   ├── test_graph_flow.py
│   └── test_database.py
├── e2e/
│   ├── test_simple_table.py
│   └── test_production_table.py
├── fixtures/
│   ├── mock_llm_responses.json
│   └── sample_tables/
└── helpers.py

docs/                               # NEW: Living documentation
├── DEVELOPMENT.md                  # Setup & local development
├── ADDING_INVESTIGATION_DOMAIN.md  # Extension guide
├── ADDING_QUERY_HOOK.md            # Hook development guide
├── MIGRATION_GUIDE.md              # Upgrade instructions
├── API_REFERENCE.md                # Public interfaces
└── TROUBLESHOOTING.md              # Common issues

reports/                            # Investigation outputs (created)
└── .gitkeep
```

---

## Configuration Updates

**Update `.env`**:

```env
# Investigation settings
MAX_INVESTIGATION_CHECKS=50
MAX_CHECK_RETRIES=3
QUERY_TIMEOUT_SECONDS=30
INVESTIGATION_DB_PATH=data/investigation.db

# Query safety settings
ALLOWED_CATALOGS=eds_it_dev
ALLOWED_SCHEMAS=elh_comn
ENABLE_QUERY_HOOKS=true
LOG_HOOK_VIOLATIONS=true

# Report settings
REPORT_OUTPUT_DIR=reports
```

---

## Dependency Verification and Analysis

### Core Production Dependencies

Before implementation begins, verify each dependency is available, compatible, and matches the environment.

| Dependency | Version | Purpose | Verification Command | Risk |
|---|---|---|---|---|
| `pyspark` | `3.5.0` (exact) | IOMETE Spark Connect | `python -c "import pyspark; print(pyspark.__version__)"` | High: must match IOMETE cluster version |
| `httpx` | `>=0.24.0` | Dell AIA Gateway HTTP client | `python -c "import httpx; print(httpx.__version__)"` | Low |
| `python-dotenv` | `>=1.0.0` | Environment loading | `python -c "import dotenv; print(dotenv.__version__)"` | Low |
| `langgraph` | `>=1.2.0,<2.0.0` | Workflow orchestration | `python -c "import langgraph; print(langgraph.__version__)"` | Medium: 1.x stable, API different from 0.x |
| `langchain-core` | `>=0.3.0` | LangGraph core | `python -c "import langchain_core; print(langchain_core.__version__)"` | Low: follows langgraph |
| `sqlparse` | `>=0.4.4` | SQL validation | `python -c "import sqlparse; print(sqlparse.__version__)"` | Low |
| `alembic` | `>=1.12.0` | Database migrations | `python -c "import alembic; print(alembic.__version__)"` | Low |
| `pydantic` | `>=2.0.0` | Data validation | `python -c "import pydantic; print(pydantic.__version__)"` | Low |
| `typing-extensions` | `>=4.8.0` | TypedDict/backport | `python -c "import typing_extensions; print(typing_extensions.__version__)"` | Low |

### Development Dependencies

| Dependency | Version | Purpose | Verification Command |
|---|---|---|---|
| `pytest` | `>=7.4.0` | Testing | `pytest --version` |
| `pytest-cov` | `>=4.1.0` | Coverage | `pytest --cov=src` |
| `pytest-mock` | `>=3.12.0` | Mocking | `python -c "import pytest_mock"` |
| `black` | `>=23.0.0` | Formatting | `black --version` |
| `mypy` | `>=1.7.0` | Type checking | `mypy --version` |
| `ruff` | `>=0.1.0` | Linting | `ruff --version` |

### Compatibility Matrix

| LangGraph | langchain-core | Python | Status |
|---|---|---|---|
| 1.2.x | 0.3.x | 3.11 | ✅ Target |
| 1.1.x | 0.2.x | 3.10 | ⚠️ Not tested |
| 0.2.x | 0.1.x | 3.9 | ❌ Deprecated |

### Verification Script

**Script**: `scripts/verify_dependencies.py`

```python
#!/usr/bin/env python3
"""Verify all required dependencies are installed and compatible."""

import sys

REQUIRED = {
    "pyspark": {"version": "3.5.0", "exact": True},
    "httpx": {"version": "0.24.0", "exact": False},
    "langgraph": {"version": "1.2.0", "exact": False},
    "langchain_core": {"version": "0.3.0", "exact": False},
    "sqlparse": {"version": "0.4.4", "exact": False},
    "alembic": {"version": "1.12.0", "exact": False},
    "pydantic": {"version": "2.0.0", "exact": False},
}


def check_version(module_name, spec):
    try:
        module = __import__(module_name)
    except ImportError:
        return False, f"{module_name} not installed"
    
    installed = module.__version__
    required = spec["version"]
    exact = spec["exact"]
    
    if exact and installed != required:
        return False, f"{module_name}: expected {required}, got {installed}"
    if not exact:
        from packaging import version
        if version.parse(installed) < version.parse(required):
            return False, f"{module_name}: expected >= {required}, got {installed}"
    
    return True, f"{module_name} {installed} ✓"


def main():
    all_ok = True
    for module, spec in REQUIRED.items():
        ok, msg = check_version(module, spec)
        print(msg)
        if not ok:
            all_ok = False
    
    if not all_ok:
        print("\n❌ Dependency check failed. Run: pip install -r requirements.txt")
        sys.exit(1)
    
    print("\n✅ All dependencies verified")


if __name__ == "__main__":
    main()
```

### Dependency Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LangGraph 1.x API differs from 0.x examples in original plan | High | Medium | Update imports and checkpointing during Session 3; run smoke test before full graph build |
| PySpark 3.5.0 not installed or wrong version | Medium | High | Pin exact; verify at start; align with IOMETE cluster |
| langchain-core incompatible with langgraph | Low | Medium | Use compatible version range; test import together |
| sqlparse fails on Spark SQL dialect | Medium | Medium | Test hook pipeline against real Spark SQL queries |
| Windows-specific SSL issues with IOMETE/LLM | High (already seen) | Medium | Keep SSL cert logic from `test_iomete_with_cert.py` and `test_dell_auth.py` |

## Dependencies to Add

**Update `requirements.txt**:

```txt
# Core dependencies (existing)
pyspark==3.5.0                 # IOMETE Spark Connect (match their version)
httpx>=0.24.0                  # Dell AIA Gateway HTTP client
python-dotenv>=1.0.0           # Environment configuration

# Investigation framework
langgraph>=1.2.0,<2.0.0        # Graph workflow (latest stable 1.x series)
langchain-core>=0.3.0          # LangGraph core dependencies
sqlparse>=0.4.4                # SQL parsing for query validation

# Database
alembic>=1.12.0                # Schema migrations (future-proofing)

# Type hints & validation
typing-extensions>=4.8.0       # Extended type hints
pydantic>=2.0.0                # Data validation (for report schemas)

# Development & Testing (requirements-dev.txt)
pytest>=7.4.0                  # Testing framework
pytest-cov>=4.1.0              # Coverage reporting
pytest-mock>=3.12.0            # Mocking utilities
black>=23.0.0                  # Code formatting
mypy>=1.7.0                    # Type checking
ruff>=0.1.0                    # Fast linting

# LLM integrations
# Using custom Dell AIA Gateway adapter (authentication_provider.py)
# Not using standard langchain LLM providers
```

---

## Risk Mitigation

**Query Safety**: Defense in Depth (5 Layers)

1. **Database Credential**: Read-only role enforced at IOMETE level (cannot write even if SQL bypassed)
2. **Hook Pipeline**: Multi-stage query validation before execution
   - `SingleStatementHook`: Reject batched queries (prevents `SELECT; DROP`)
   - `ReadOnlyHook`: Block DDL/DML keywords (INSERT, UPDATE, DELETE, DROP, etc.)
   - `NoFilePathHook`: Block file system access (LOAD, COPY, file://)
   - `SchemaWhitelistHook`: Restrict to approved catalogs/schemas only
3. **SQL Parsing**: sqlparse library validates query structure
4. **Timeout**: 30-second limit enforced at Spark level (prevents runaway queries)
5. **Snapshot Pinning**: All queries read from fixed snapshot (consistency + safety)

**Context Drift**: Trail compaction

- Fixed-format findings prevent paraphrasing
- Full trail accessible on-demand
- Explicit evidence IDs required

**Knowledge Hallucination**: List-then-fetch

- Never allow guessed paths
- All paths from list results
- Version tracking prevents reference rot

**LLM Failure Modes**:

- Per-check retry limit (3 attempts)
- Whole-investigation budget (50 checks)
- Explicit "could not verify" on exhausted retries
- Gaps visible in report, not hidden

---

## Testing Strategy

**Unit Tests** (per component):

- **Query hooks** (critical): Each hook tested independently
  - `ReadOnlyHook`: SELECT passes, INSERT/UPDATE/DELETE/DROP blocked
  - `SingleStatementHook`: Single statements pass, batched queries blocked
  - `NoFilePathHook`: Normal queries pass, LOAD/file:// blocked
  - `SchemaWhitelistHook`: Allowed schemas pass, unauthorized blocked
- **Hook pipeline**: Integration of all hooks, execution order
- Query validation: valid/invalid SQL patterns
- Claim validation: evidence ID resolution
- Trail compaction: fixed-format enforcement
- Individual graph nodes: state transformations

**Graph Flow Tests** (new):

- Test graph structure (nodes, edges, routing)
- Test conditional branching (retry logic, budget checks)
- Test state persistence (checkpointing)
- Test recovery from failures (resume from checkpoint)
- Mock LLM responses to test flow logic
- **Test each node's output shape and verification rules**
- **Test state transitions between every pair of nodes**
- **Test invariants are never violated**

**Integration Tests**:

- Database round-trip (write findings, read back)
- Knowledge retrieval with SQLite index
- Query workbench with real Spark session
- Graph + LLM + Database integration

**End-to-End Test**:

- Full investigation on real IOMETE table
- Manual review of report quality
- Evidence traceability verification
- Graph state inspection at each step

**Acceptance Criteria**:

- **Security**: All query hooks pass comprehensive tests
- **Security**: Attempt to execute non-SELECT query fails with clear error
- **Security**: Hook violations are logged to database
- **Dependencies**: `verify_dependencies.py` passes before any code runs
- **Dependencies**: No version conflicts in `requirements.txt`
- **Graph Nodes**: Each node produces correct output shape and valid values
- **Graph Nodes**: Every node's output is verified before propagation
- **Graph Nodes**: State invariants hold before and after each node
- **Findings**: Report contains ≥3 validated findings
- **Findings**: Every claim has ≥1 evidence ID
- **Findings**: All evidence IDs resolve
- **Investigation**: Completes within budget
- **Checkpointing**: Graph state is persisted at each step
- **Recovery**: Investigation can resume from any checkpoint
- **Report**: Is actionable (human can understand and act on it)
- **Visualization**: Graph flow can be rendered and inspected

---

## Implementation Order

**Before Starting**: Invoke skills

- `/codebase-design` - Review module design principles
- `/domain-modeling` - Define investigation domain terms

1. **Database Schema** (Stage 1 completion)
   - Create tables (investigation_trail, findings, etc.)
   - Test read/write operations
   - Initialize knowledge index
   - Add LangGraph checkpoint table

2. **Query Workbench with Safety Hooks** (Stage 2)
   - Implement hook base class and individual hooks
   - `ReadOnlyHook`, `SingleStatementHook`, `NoFilePathHook`, `SchemaWhitelistHook`
   - Hook factory for standard pipeline
   - Query workbench with hook execution pipeline
   - Comprehensive hook tests (each hook + full pipeline)
   - Verify snapshot pinning works
   - Follow deep module pattern (§1 in AGENTS.md)

3. **LangGraph Workflow** (Stage 4 - core innovation)
   - Define investigation state schema
   - Implement graph structure (nodes + edges)
   - Implement individual node functions (decide, fetch, query, analyze, compact)
   - Add conditional routing logic
   - Test graph flow with mock LLM
   - Verify checkpointing works

4. **LLM Integration** (Stage 4 continuation)
   - Integrate Dell AIA Gateway as LLM backend
   - Implement tool calling interface
   - Connect tools to graph nodes
   - Test with real LLM on simple investigation

5. **Validation & Reporting** (Stage 5)
   - Build claim validator (evidence ID checker)
   - Create report template
   - Test with sample findings

6. **Integration & Testing** (Stage 5 final)
   - Wire all components through LangGraph
   - CLI orchestrator (`run_investigation.py`)
   - End-to-end test on real IOMETE table
   - Verify graph state persistence

7. **Code Quality & Documentation**
   - Ensure no file exceeds 200 lines (§3 in AGENTS.md)
   - Add module docstrings and type hints
   - Every interface documented with extension points
   - Usage guide with graph visualization
   - Report interpretation guide
   - **DEVELOPMENT.md**: Setup instructions for future developers
   - **ADDING_INVESTIGATION_DOMAIN.md**: How to add new domains
   - **ADDING_QUERY_HOOK.md**: How to add custom hooks
   - **API_REFERENCE.md**: Public interface documentation
   - Known limitations and future roadmap

---

## Success Metrics

**MVP is successful if**:

1. Investigation produces readable, evidence-backed report
2. Every claim traces to executed query or fetched knowledge
3. Report is more useful than baseline score alone
4. Human can act on recommendations without additional research
5. No hallucinated facts in findings

**MVP has failed if**:

- Claims cite non-existent evidence
- Recommendations don't follow from evidence
- Report is generic advice (could apply to any table)
- Investigation runs out of budget without useful findings

---

## Out of Scope (Explicitly Deferred)

Per Architecture.md §3 and §4:

- ❌ Richer claim validator (type checking, content matching)
- ❌ Formal score-ranked check menu
- ❌ Multi-table investigation
- ❌ Concurrent query execution
- ❌ Suggestion verification on table copies
- ❌ Additional investigation domains (beyond layout)
- ❌ Human escalation / expert review loop
- ❌ Knowledge base growth from feedback
- ❌ Automatic remediation execution

These are real, well-reasoned designs. They get built **only** when a real report demonstrates the need, not before.

---

## Code Quality Standards (per AGENTS.md)

**Deep Modules** (§1):

- Each component (workbench, graph nodes, validator) is a deep module
- Small interface, large implementation
- Test through the interface, not implementation details

**File Size Limit** (§3):

- No file exceeds 200 lines
- Split graph nodes into separate files if needed
- Each node implementation in `graph_nodes.py` is its own function

**Skill Usage** (§4):

- Invoke `/codebase-design` before building graph structure
- Invoke `/domain-modeling` for investigation terminology
- Use exact vocabulary: module, interface, seam, adapter, depth, leverage, locality

**Readability** (§2):

- Flat logic, no deep nesting
- Pure functions for graph nodes (state in, state out)
- Type hints on all functions
- No comments unless code cannot express intent

---

## Future-Proofing Architecture: Extensibility & Upgradability

### Design for Evolution

**Principle**: Every component designed with **seams** for future extension without breaking existing code.

### 1. Plugin Architecture for New Investigation Domains

**Current MVP**: Table Layout investigation (partitioning, file sizing, skew)

**Future Domains** (Architecture.md §10):
- Write-path behavior analysis
- Table lifecycle/maintenance patterns
- Query performance analysis
- Data quality checks

**Extensibility Design**:

```python
# src/investigator/domain_interface.py
class InvestigationDomain(ABC):
    """Seam for adding new investigation domains."""
    
    @abstractmethod
    def get_domain_name(self) -> str:
        """Domain identifier (e.g., 'layout', 'write-path', 'lifecycle')"""
        pass
    
    @abstractmethod
    def get_graph_nodes(self) -> dict[str, Callable]:
        """Return domain-specific graph nodes."""
        pass
    
    @abstractmethod
    def get_knowledge_sources(self) -> list[str]:
        """Knowledge tree paths this domain uses."""
        pass
    
    @abstractmethod
    def should_investigate(self, baseline_score: HealthScoreResult) -> bool:
        """Decide if this domain is relevant based on score."""
        pass

# src/investigator/domains/layout_domain.py
class LayoutDomain(InvestigationDomain):
    """MVP domain: table layout investigation."""
    def get_domain_name(self) -> str:
        return "layout"
    
    def get_graph_nodes(self) -> dict[str, Callable]:
        return {
            "check_partitioning": check_partition_strategy,
            "check_file_sizing": check_file_distribution,
            "check_data_skew": check_partition_skew
        }
    
    def get_knowledge_sources(self) -> list[str]:
        return ["iceberg/partitioning", "iceberg/file-sizing", "iomete/maintenance"]

# Future domains plug in here:
# src/investigator/domains/write_path_domain.py
# src/investigator/domains/lifecycle_domain.py
```

**Benefits**:
- Add new domains without modifying core investigator
- Each domain is independently testable
- Domains can be enabled/disabled via config

### 2. Versioned Interfaces with Adapters

**Problem**: APIs change over time (IOMETE, Dell AIA Gateway, LangGraph)

**Solution**: Adapter pattern with version detection

```python
# src/connectors/llm_adapter.py
class LLMAdapter(ABC):
    """Seam for different LLM providers."""
    @abstractmethod
    def generate_response(self, messages: list[dict]) -> str:
        pass
    
    @abstractmethod
    def call_with_tools(self, messages: list[dict], tools: list[Tool]) -> dict:
        pass

# src/connectors/dell_aia_adapter.py
class DellAIAAdapter(LLMAdapter):
    """Current: Dell AIA Gateway adapter."""
    def __init__(self, auth_provider):
        self.auth = auth_provider
    
    def generate_response(self, messages: list[dict]) -> str:
        # Current implementation
        pass

# Future: Easy to swap LLM providers
# class OpenAIAdapter(LLMAdapter): ...
# class AnthropicAdapter(LLMAdapter): ...
```

**Benefits**:
- Swap LLM providers without changing investigator code
- Support multiple providers simultaneously
- A/B test different models

### 3. Hook System Extensibility

**Current**: 4 query safety hooks

**Future**: Custom hooks for specific use cases

```python
# src/query/custom_hooks/
# Each new hook is a separate file, easy to add

class PerformanceHook(QueryHook):
    """Prevent expensive queries (full table scans on large tables)."""
    def validate(self, query: str) -> tuple[bool, Optional[str]]:
        # Check for WHERE clause on large tables
        # Estimate query cost
        pass

class ComplianceHook(QueryHook):
    """Ensure queries respect data governance rules."""
    def validate(self, query: str) -> tuple[bool, Optional[str]]:
        # Check for PII column access
        # Verify compliance tags
        pass

# Add to pipeline via config:
# CUSTOM_HOOKS=PerformanceHook,ComplianceHook
```

**Hook Factory** supports dynamic loading:

```python
def create_investigation_hooks(
    allowed_catalogs: list[str],
    allowed_schemas: list[str],
    custom_hooks: list[str] = None
) -> list[QueryHook]:
    """Create hook pipeline with optional custom hooks."""
    base_hooks = [
        SingleStatementHook(),
        ReadOnlyHook(),
        NoFilePathHook(),
        SchemaWhitelistHook(allowed_catalogs, allowed_schemas)
    ]
    
    if custom_hooks:
        # Dynamically load custom hook classes
        for hook_name in custom_hooks:
            hook_class = load_hook_class(hook_name)
            base_hooks.append(hook_class())
    
    return base_hooks
```

### 4. Database Schema Migrations

**Challenge**: Schema evolves as features added

**Solution**: Alembic-style migration system

```python
# src/database/migrations/001_initial_schema.py
def upgrade():
    """Create initial tables."""
    # Create investigations, trail, findings, etc.

# src/database/migrations/002_add_hook_violations.py
def upgrade():
    """Add hook_violations table."""
    # ALTER TABLE or CREATE TABLE

# src/database/migrations/003_add_domain_tracking.py
def upgrade():
    """Track which domains were used in investigation."""
    # ALTER TABLE investigations ADD COLUMN domains_used TEXT

# src/database/migration_manager.py
class MigrationManager:
    def get_current_version(self) -> int:
        """Query schema_version table."""
    
    def apply_migrations(self, target_version: Optional[int] = None):
        """Apply all pending migrations."""
    
    def rollback(self, target_version: int):
        """Rollback to specific version."""
```

**Benefits**:
- Database evolves safely
- Rollback capability
- Clear upgrade path for users

### 5. Configuration-Driven Features

**Philosophy**: New features start disabled, enabled via config

```python
# .env (feature flags)
FEATURE_MULTI_DOMAIN_INVESTIGATION=false  # MVP: single domain
FEATURE_SUGGESTION_VERIFICATION=false     # Architecture.md §10: test suggestions
FEATURE_CONCURRENT_CHECKS=false           # Future: parallel checks
FEATURE_HUMAN_ESCALATION=false            # Architecture.md §4: expert review
FEATURE_KNOWLEDGE_GROWTH=false            # Architecture.md §4: learn from feedback

# src/config/feature_flags.py
class FeatureFlags:
    @staticmethod
    def is_enabled(feature: str) -> bool:
        return os.getenv(f"FEATURE_{feature}", "false").lower() == "true"
    
    @staticmethod
    def require_feature(feature: str):
        """Decorator to guard feature-flagged code."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not FeatureFlags.is_enabled(feature):
                    raise FeatureDisabled(f"{feature} not enabled")
                return func(*args, **kwargs)
            return wrapper
        return decorator

# Usage:
@FeatureFlags.require_feature("SUGGESTION_VERIFICATION")
def verify_suggestion_on_copy(suggestion: str, table: str) -> bool:
    # This code only runs if feature enabled
    pass
```

**Benefits**:
- Ship features incrementally
- A/B testing in production
- Easy rollback if issues found

### 6. API Versioning for Reports

**Problem**: Report format changes break downstream consumers

**Solution**: Versioned report schemas

```python
# src/reporting/report_schema.py
class ReportSchema:
    VERSION = "1.0.0"  # Semantic versioning
    
    def to_dict(self) -> dict:
        return {
            "version": self.VERSION,
            "investigation_id": ...,
            "findings": [...],
            # Future fields added here don't break v1.0 readers
        }

# src/reporting/report_assembler.py
class ReportAssembler:
    def __init__(self, schema_version: str = "1.0.0"):
        self.schema_version = schema_version
    
    def assemble_report(self, investigation_id: int) -> Report:
        # Generate report in requested version
        if self.schema_version.startswith("1."):
            return self._assemble_v1(investigation_id)
        elif self.schema_version.startswith("2."):
            return self._assemble_v2(investigation_id)
```

**Benefits**:
- Downstream tools don't break on upgrades
- Support multiple versions simultaneously
- Clear deprecation path

### 7. Telemetry & Observability Seam

**Future**: Production monitoring, metrics, tracing

**Design seam now**:

```python
# src/observability/telemetry.py
class TelemetryProvider(ABC):
    @abstractmethod
    def record_investigation_start(self, investigation_id: int):
        pass
    
    @abstractmethod
    def record_check_completed(self, check_num: int, duration: float):
        pass
    
    @abstractmethod
    def record_hook_violation(self, hook: str, query: str):
        pass

# src/observability/null_telemetry.py
class NullTelemetry(TelemetryProvider):
    """MVP: No-op implementation."""
    def record_investigation_start(self, investigation_id: int):
        pass  # Does nothing

# Future implementations:
# class PrometheusAdapter(TelemetryProvider): ...
# class DatadogAdapter(TelemetryProvider): ...
```

**Benefits**:
- Telemetry code exists but disabled in MVP
- Easy to enable for production
- No code changes needed to add monitoring

### 8. Knowledge Base Evolution

**Current**: Flat markdown files in `knowledge/{source}/`

**Future**: Hierarchical categories, tagging, versioning

```python
# knowledge/iceberg/partitioning/partition-transforms.md
---
version: 2
tags: [partitioning, transforms, performance]
category: table-layout
last_updated: 2024-01-15
supersedes: v1-partition-transforms
---

# Partition Transforms
...

# src/knowledge/knowledge_metadata.py
class KnowledgeMetadata:
    def get_entries_by_tag(self, tag: str) -> list[str]:
        """Future: Query by tag."""
    
    def get_entry_history(self, path: str) -> list[str]:
        """Future: Version history."""
    
    def search_entries(self, query: str) -> list[str]:
        """Future: Full-text search."""
```

**Migration Strategy**:
- Current: Simple path-based retrieval works
- Future: Add metadata layer on top (backwards compatible)

### 9. Testing Infrastructure for Growth

**Comprehensive test suite** that grows with codebase:

```python
# tests/
├── unit/
│   ├── test_hooks.py           # Each hook independently
│   ├── test_graph_nodes.py     # Each node independently
│   └── test_validators.py      # Each validator independently
├── integration/
│   ├── test_hook_pipeline.py   # All hooks together
│   ├── test_graph_flow.py      # Full graph execution
│   └── test_database.py        # DB operations
├── e2e/
│   ├── test_simple_table.py    # End-to-end on test table
│   └── test_production_table.py # Real IOMETE table
└── fixtures/
    ├── mock_llm_responses.json  # Deterministic LLM outputs
    ├── sample_tables/           # Test data
    └── expected_reports/        # Golden outputs
```

**Test Helpers**:

```python
# tests/helpers.py
class InvestigationTestHelper:
    @staticmethod
    def create_test_investigation(table_name: str = "test_table"):
        """Factory for test investigations."""
    
    @staticmethod
    def mock_llm_with_responses(responses: list[str]):
        """Replace LLM with deterministic mock."""
    
    @staticmethod
    def assert_report_structure(report: Report):
        """Validate report format."""
```

### 10. Documentation for Future Maintainers

**Living Documentation**:

```text
docs/
├── ARCHITECTURE.md          # Current: exists, keep updated
├── DEVELOPMENT.md           # NEW: Setup, local testing
├── ADDING_INVESTIGATION_DOMAIN.md  # NEW: How to add domain
├── ADDING_QUERY_HOOK.md     # NEW: How to add hook
├── MIGRATION_GUIDE.md       # NEW: Upgrade instructions
├── API_REFERENCE.md         # NEW: Public interfaces
└── TROUBLESHOOTING.md       # NEW: Common issues
```

**Code-Level Documentation**:

```python
# Every module has:
"""
Module: query_workbench
Purpose: Execute SQL queries through safety pipeline
Seam: QueryWorkbench interface
Adapters: Can swap Spark backend, add new hooks
Tests: tests/unit/test_query_workbench.py

Extension Points:
- Add new QueryHook subclass for custom validation
- Replace Spark with alternative engine

Example:
    workbench = QueryWorkbench(spark, hooks=[...])
    result = workbench.execute_query("SELECT * FROM table")
"""
```

---

## Upgrade Path Strategy

### MVP → Future Phases

**Phase 1 (MVP - Current Plan)**:
- Single domain (layout)
- Basic hooks (4 standard)
- Single table investigation
- Manual execution

**Phase 2 (3-6 months)**:
- Multi-domain support (add write-path domain)
- Custom hooks enabled
- Batch table investigation
- Scheduled runs

**Phase 3 (6-12 months)**:
- Suggestion verification (Architecture.md §10)
- Human escalation workflow
- Knowledge base learning from feedback
- Advanced telemetry

**Backwards Compatibility**:
- Database migrations handle schema changes
- Report versioning prevents breaking consumers
- Feature flags enable gradual rollout
- Old investigations viewable in new system

---

## Dependency Management

**Pinned Versions** (MVP):
```txt
langgraph>=1.2.0,<2.0.0     # Stable 1.x series (1.2.11 current)
langchain-core>=0.3.0       # Compatible with LangGraph 1.x
sqlparse>=0.4.4             # SQL parsing
pyspark==3.5.0              # Match IOMETE version exactly
```

**Upgrade Strategy**:
- Test upgrades in isolated environment
- Run full test suite before merging
- Document breaking changes in MIGRATION_GUIDE.md
- Keep old versions working via adapters if needed

---

## Extensibility Checklist

For **every component**, ensure:

- ✅ Interface defined (ABC or Protocol)
- ✅ At least one concrete adapter
- ✅ Tests validate interface, not implementation
- ✅ Documentation shows how to extend
- ✅ Example of extension included
- ✅ No hard-coded dependencies (inject via constructor)
- ✅ Configuration-driven where possible
- ✅ Version compatibility noted

---

## Next Steps After Plan Approval

1. **Invoke Skills**
   - `/codebase-design` - Review module design for investigation components
   - `/domain-modeling` - Define investigation domain terms

2. **Setup Phase**
   - Install LangGraph: `pip install langgraph langchain-core`
   - Create directory structure (`src/database/`, `src/query/`, `src/investigator/`)

3. **Implementation Sessions**
   - Session 1: Database schema + knowledge index + checkpointing
   - Session 2: Query workbench with validation
   - Session 3: LangGraph workflow (nodes + edges + state)
   - Session 4: LLM integration (Dell AIA Gateway + tools)
   - Session 5: Validation + reporting + CLI
   - Session 6: End-to-end test on real table

**Estimated Implementation**: 6 sessions (database → workbench → graph → LLM → validation → integration)

**First Deliverable**: Working LangGraph-based investigation that produces one validated report for one real table from IOMETE, with graph state persisted and inspectable.

**Graph Visualization**: LangGraph provides built-in visualization - we'll be able to see the investigation flow as a graph diagram.

---

## Future-Proofing Benefits Summary

### ✅ What You Get: A Codebase Built to Last

**1. Easy Feature Addition**
- **Add new investigation domains**: 1 file, implement interface, done
- **Add custom hooks**: 1 file in `custom_hooks/`, auto-loaded
- **Add new LLM provider**: Implement `LLMAdapter`, swap in config
- **Enable new features**: Flip feature flag, no code deploy needed

**2. Zero Downtime Upgrades**
- Database migrations with rollback
- Report versioning (v1 keeps working when v2 ships)
- Feature flags (enable for 10% users, roll back if issues)
- Backwards compatibility guaranteed

**3. Confidence in Changes**
- **200-line limit enforced**: No god files, easy to understand
- **80%+ test coverage**: Changes don't break existing features
- **Type checking**: Catch bugs before runtime
- **CI/CD pipeline**: Can't merge broken code

**4. Onboarding New Developers**
- **DEVELOPMENT.md**: Setup in 10 minutes
- **API_REFERENCE.md**: Know what to call
- **ADDING_*.md guides**: Know how to extend
- **Example code**: Copy-paste and adapt

**5. Production Readiness**
- Telemetry seam ready (just enable)
- Monitoring hooks built in
- Logging and audit trails
- Error handling with retry logic

**6. Flexibility**
- **Not locked into Dell AIA**: Swap LLM providers via adapter
- **Not locked into Spark**: Query engine is pluggable
- **Not locked into SQLite**: Database adapter pattern
- **Not locked into single domain**: Add write-path, lifecycle, etc.

### 🔮 Three-Year Vision

**Year 1 (MVP)**:
- Single domain (table layout)
- Manual execution
- Basic hooks
- Dell AIA Gateway LLM

**Year 2**:
- 5+ investigation domains (write-path, lifecycle, performance, quality, compliance)
- 20+ custom hooks (org-specific rules)
- Scheduled batch investigations
- Multi-LLM support (A/B testing different models)

**Year 3**:
- Suggestion auto-verification (spin up test table, verify fix works)
- Human-in-the-loop escalation (expert review)
- Knowledge base learns from production
- Fleet-wide optimization (analyze 1000s of tables, find patterns)

**Zero Code Rewrites**: Everything builds on the same foundation.

### 📊 Metrics You Can Track

**Code Quality**:
- File size: 100% under 200 lines ✓
- Test coverage: 80%+ ✓
- Type coverage: 100% ✓
- Zero linter errors ✓

**Extensibility**:
- Time to add new domain: ~4 hours (not 4 days)
- Time to add new hook: ~1 hour
- Time to swap LLM provider: ~2 hours

**Reliability**:
- Investigation success rate: Track in telemetry
- Hook violation rate: Audit in database
- Query timeout rate: Monitor and tune
- Report validation pass rate: Should be 100%

---

## Code Review & Quality Gates

**Pre-Commit Checks** (enforced):

```yaml
# .pre-commit-config.yaml (NEW)
repos:
  - repo: local
    hooks:
      - id: file-size-check
        name: Check file size (200 lines max)
        entry: python scripts/check_file_size.py
        language: python
        pass_filenames: true
      
      - id: black
        name: Format with Black
        entry: black
        language: python
        types: [python]
      
      - id: ruff
        name: Lint with Ruff
        entry: ruff check
        language: python
        types: [python]
      
      - id: mypy
        name: Type check with mypy
        entry: mypy
        language: python
        types: [python]
      
      - id: test
        name: Run unit tests
        entry: pytest tests/unit/
        language: python
        pass_filenames: false
```

**scripts/check_file_size.py** (enforce AGENTS.md §3):

```python
#!/usr/bin/env python3
"""Enforce 200-line limit per AGENTS.md §3."""
import sys

MAX_LINES = 200

for filepath in sys.argv[1:]:
    with open(filepath) as f:
        line_count = len(f.readlines())
    
    if line_count > MAX_LINES:
        print(f"❌ {filepath}: {line_count} lines (max {MAX_LINES})")
        sys.exit(1)

print("✅ All files under 200 lines")
```

**Pull Request Checklist**:

```markdown
<!-- docs/PULL_REQUEST_TEMPLATE.md -->
## Changes
- [ ] Describes what changed and why

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Ran full test suite: `pytest`
- [ ] Manual testing completed

## Code Quality
- [ ] No file exceeds 200 lines (AGENTS.md §3)
- [ ] Type hints on all functions
- [ ] Used deep module vocabulary (AGENTS.md §1)
- [ ] Updated CONTEXT.md if domain changed
- [ ] Added docstrings with extension points

## Documentation
- [ ] Updated API_REFERENCE.md if public interface changed
- [ ] Updated MIGRATION_GUIDE.md if breaking change
- [ ] Added example if new feature

## Backwards Compatibility
- [ ] No breaking changes OR migration path documented
- [ ] Feature flagged if experimental
- [ ] Database migration created if schema changed
```

**Continuous Integration** (GitHub Actions / GitLab CI):

```yaml
# .github/workflows/ci.yml (NEW)
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Check file sizes (200 line limit)
        run: python scripts/check_file_size.py $(git ls-files '*.py')
      
      - name: Format check (Black)
        run: black --check .
      
      - name: Lint (Ruff)
        run: ruff check .
      
      - name: Type check (mypy)
        run: mypy src/
      
      - name: Run unit tests
        run: pytest tests/unit/ --cov=src --cov-report=xml
      
      - name: Run integration tests
        run: pytest tests/integration/
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

---

## Contribution Guidelines

**docs/CONTRIBUTING.md** (NEW):

```markdown
# Contributing to Smart Table Analyzer

## Architecture Principles

1. **Deep Modules** (AGENTS.md §1)
   - Small interface, large implementation
   - Test through interfaces, not internals
   - Use exact vocabulary: module, seam, adapter, depth

2. **File Size Limit** (AGENTS.md §3)
   - Max 200 lines per file
   - Split along module seams if exceeded

3. **Extensibility First**
   - Every component has an interface (ABC)
   - Extension points documented
   - Examples provided

## Adding Features

### New Investigation Domain

1. Read `docs/ADDING_INVESTIGATION_DOMAIN.md`
2. Implement `InvestigationDomain` interface
3. Add to `src/investigator/domains/`
4. Add tests to `tests/unit/test_{domain}_domain.py`
5. Update `docs/API_REFERENCE.md`

### New Query Hook

1. Read `docs/ADDING_QUERY_HOOK.md`
2. Implement `QueryHook` interface
3. Add to `src/query/custom_hooks/`
4. Add tests to `tests/unit/test_{hook}_hook.py`
5. Document in hook docstring

### Database Schema Change

1. Create migration in `src/database/migrations/`
2. Increment version number
3. Test both upgrade() and downgrade()
4. Update `docs/MIGRATION_GUIDE.md`

## Testing Requirements

- **Unit tests**: Every public function
- **Integration tests**: Component interactions
- **E2E test**: At least one real scenario
- **Coverage**: Minimum 80%

## Code Review

All changes require:
- ✅ Passing CI
- ✅ Code review approval
- ✅ Documentation updated
- ✅ No file > 200 lines

