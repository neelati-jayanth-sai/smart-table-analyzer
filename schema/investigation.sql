-- Investigation Harness SQLite Schema
-- Canonical reference generated from migration 002.
-- Use `scripts/init_investigation_db.py` to create the database.

-- Knowledge index (§5: topic path → current version)
CREATE TABLE IF NOT EXISTS knowledge_index (
    source TEXT NOT NULL,
    topic_path TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    content_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source, topic_path)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_source ON knowledge_index(source);
CREATE INDEX IF NOT EXISTS idx_knowledge_path ON knowledge_index(topic_path);

-- Investigation runs
CREATE TABLE IF NOT EXISTS investigations (
    investigation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    table_name TEXT NOT NULL,
    catalog_name TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'running', 'metadata_collected', 'planning', 'checks_running',
        'evidence_validated', 'completed', 'failed', 'aborted')),
    baseline_score_json TEXT,
    snapshot_id TEXT,
    max_checks INTEGER NOT NULL DEFAULT 50,
    current_check INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_investigations_run_id ON investigations(run_id);
CREATE INDEX IF NOT EXISTS idx_investigations_table ON investigations(table_name);

-- Query execution trail
CREATE TABLE IF NOT EXISTS investigation_trail (
    trail_id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id INTEGER NOT NULL,
    check_num INTEGER NOT NULL,
    node_name TEXT NOT NULL,
    query_text TEXT,
    rewritten_query TEXT,
    query_result_json TEXT,
    execution_status TEXT CHECK (execution_status IN ('success', 'timeout', 'hook_failed', 'error')),
    execution_time_ms INTEGER,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trail_investigation ON investigation_trail(investigation_id);
CREATE INDEX IF NOT EXISTS idx_trail_check ON investigation_trail(investigation_id, check_num);

-- Knowledge references consulted
CREATE TABLE IF NOT EXISTS knowledge_references (
    reference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id INTEGER NOT NULL,
    check_num INTEGER NOT NULL,
    source TEXT NOT NULL,
    topic_path TEXT NOT NULL,
    version TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_knowledge_ref_investigation ON knowledge_references(investigation_id);

-- Compacted findings
CREATE TABLE IF NOT EXISTS investigation_findings (
    finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id INTEGER NOT NULL,
    check_num INTEGER NOT NULL,
    question TEXT NOT NULL,
    exact_result TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('found', 'not_found', 'inconclusive', 'could_not_verify')),
    rationale TEXT NOT NULL,
    evidence_ids TEXT NOT NULL,
    recommendation TEXT,
    alternatives_json TEXT,
    validated BOOLEAN NOT NULL DEFAULT 0,
    check_type TEXT,
    actionable_sql TEXT,
    confidence REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id) ON DELETE CASCADE,
    UNIQUE(investigation_id, check_num)
);

CREATE INDEX IF NOT EXISTS idx_findings_investigation ON investigation_findings(investigation_id);
CREATE INDEX IF NOT EXISTS idx_findings_verdict ON investigation_findings(verdict);

-- Baseline score
CREATE TABLE IF NOT EXISTS baseline_scores (
    baseline_score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id INTEGER NOT NULL UNIQUE,
    overall_score REAL NOT NULL,
    dimensions_json TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_baseline_investigation ON baseline_scores(investigation_id);

-- Schema migration tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Security audit: query hook violations
CREATE TABLE IF NOT EXISTS hook_violations (
    violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id INTEGER NOT NULL,
    check_num INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    hook_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hook_violations_investigation ON hook_violations(investigation_id);


-- Optional state snapshots
CREATE TABLE IF NOT EXISTS investigation_state_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id INTEGER NOT NULL,
    check_num INTEGER NOT NULL,
    node_name TEXT NOT NULL,
    state_json TEXT NOT NULL,
    captured_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (investigation_id) REFERENCES investigations(investigation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_state_snapshots_investigation ON investigation_state_snapshots(investigation_id, check_num);
