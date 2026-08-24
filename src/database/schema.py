"""Database creation and additive migrations.

The canonical DDL lives in `schema/investigation.sql`; the migrations here bring
databases created by an older version of that file up to date.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "investigation.sql"


def create_schema(conn: sqlite3.Connection) -> None:
    """Create every table, then apply migrations for pre-existing databases."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for databases created by an older schema."""
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(investigation_findings)")
    }
    for name, decl in (
        ("check_type", "TEXT"),
        ("actionable_sql", "TEXT"),
        ("confidence", "REAL"),
        ("issue_state", "TEXT NOT NULL DEFAULT 'needs_review'"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE investigation_findings ADD COLUMN {name} {decl}")

    # The original schema constrained status to a 4-value CHECK. Rebuilding the
    # table to widen a CHECK is not worth it: drop the constraint by recreating
    # only when the old constraint is still present.
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='investigations'"
    ).fetchone()
    if sql and "metadata_collected" not in (sql["sql"] or ""):
        conn.executescript(
            """
            PRAGMA foreign_keys=OFF;
            ALTER TABLE investigations RENAME TO investigations_old;
            CREATE TABLE investigations (
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
            INSERT INTO investigations SELECT * FROM investigations_old;
            DROP TABLE investigations_old;
            PRAGMA foreign_keys=ON;
            """
        )
