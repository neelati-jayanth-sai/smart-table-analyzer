"""SQLite persistence for investigations, findings, and the audit trail.

One connection per operation: investigations run checks on a thread pool, and
short-lived connections are the simplest thing that is safe there.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.models import LIFECYCLE_STATES, Finding, Investigation

from .schema import create_schema

logger = logging.getLogger(__name__)

class InvestigationDb:
    """Create, record into, and read back investigation runs."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------ setup

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            create_schema(conn)

    # ----------------------------------------------------------------- writes

    def create_investigation(
        self,
        run_id: str,
        table_name: str,
        catalog_name: str,
        schema_name: str,
        max_checks: int = 50,
        snapshot_id: str | None = None,
        status: str = "running",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO investigations
                    (run_id, table_name, catalog_name, schema_name, status,
                     snapshot_id, max_checks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, table_name, catalog_name, schema_name, status, snapshot_id, max_checks),
            )
            return int(cursor.lastrowid)

    def set_status(self, investigation_id: int, status: str) -> None:
        """Advance the lifecycle without terminating the investigation."""
        if status not in LIFECYCLE_STATES:
            raise ValueError(f"Unknown investigation status: {status}")
        with self._connect() as conn:
            conn.execute(
                "UPDATE investigations SET status = ? WHERE investigation_id = ?",
                (status, investigation_id),
            )
        logger.info(
            "Investigation status -> %s", status, extra={"investigation_id": investigation_id}
        )

    def record_baseline_score(
        self, investigation_id: int, overall_score: float, dimensions: dict[str, Any]
    ) -> None:
        payload = json.dumps({"overall": overall_score, "dimensions": dimensions}, default=str)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO baseline_scores (investigation_id, overall_score, dimensions_json)
                VALUES (?, ?, ?)
                ON CONFLICT(investigation_id) DO UPDATE SET
                    overall_score = excluded.overall_score,
                    dimensions_json = excluded.dimensions_json
                """,
                (investigation_id, float(overall_score), json.dumps(dimensions, default=str)),
            )
            conn.execute(
                "UPDATE investigations SET baseline_score_json = ? WHERE investigation_id = ?",
                (payload, investigation_id),
            )

    def record_knowledge_fetch(
        self,
        investigation_id: int,
        check_num: int,
        source: str,
        topic_path: str,
        version: str,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO knowledge_references
                    (investigation_id, check_num, source, topic_path, version)
                VALUES (?, ?, ?, ?, ?)
                """,
                (investigation_id, check_num, source, topic_path, version),
            )
            return int(cursor.lastrowid)

    def record_query(
        self,
        investigation_id: int,
        check_num: int,
        node_name: str,
        query_text: str | None,
        rewritten_query: str | None = None,
        query_result: dict[str, Any] | None = None,
        execution_status: str | None = None,
        execution_time_ms: int | None = None,
        error_message: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO investigation_trail
                    (investigation_id, check_num, node_name, query_text, rewritten_query,
                     query_result_json, execution_status, execution_time_ms, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    investigation_id,
                    check_num,
                    node_name,
                    query_text,
                    rewritten_query,
                    json.dumps(query_result, default=str) if query_result is not None else None,
                    execution_status,
                    execution_time_ms,
                    error_message,
                ),
            )
            return int(cursor.lastrowid)

    def record_finding(self, investigation_id: int, finding: Finding) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO investigation_findings
                    (investigation_id, check_num, question, exact_result, verdict, rationale,
                     evidence_ids, recommendation, alternatives_json, validated,
                     check_type, actionable_sql, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(investigation_id, check_num) DO UPDATE SET
                    question = excluded.question,
                    exact_result = excluded.exact_result,
                    verdict = excluded.verdict,
                    rationale = excluded.rationale,
                    evidence_ids = excluded.evidence_ids,
                    recommendation = excluded.recommendation,
                    alternatives_json = excluded.alternatives_json,
                    validated = excluded.validated,
                    check_type = excluded.check_type,
                    actionable_sql = excluded.actionable_sql,
                    confidence = excluded.confidence
                """,
                (
                    investigation_id,
                    finding.check_num,
                    finding.question,
                    finding.exact_result,
                    finding.verdict,
                    finding.rationale,
                    json.dumps(list(finding.evidence_ids or [])),
                    finding.recommendation,
                    json.dumps(list(finding.alternatives or [])),
                    1 if finding.validated else 0,
                    finding.check_type,
                    finding.actionable_sql,
                    finding.confidence,
                ),
            )
            conn.execute(
                "UPDATE investigations SET current_check = MAX(current_check, ?)"
                " WHERE investigation_id = ?",
                (finding.check_num + 1, investigation_id),
            )
            return int(cursor.lastrowid)

    def record_hook_violation(
        self,
        investigation_id: int,
        check_num: int,
        query_text: str,
        hook_name: str,
        reason: str | None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO hook_violations
                    (investigation_id, check_num, query_text, hook_name, reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (investigation_id, check_num, query_text, hook_name, reason or ""),
            )
            return int(cursor.lastrowid)

    def complete_investigation(
        self,
        investigation_id: int,
        status: str,
        final_state: dict[str, Any] | None = None,
    ) -> None:
        """Terminate an investigation.

        `completed` is only honoured when at least one finding carries evidence;
        otherwise the run is recorded as `failed`, so a report can never claim
        success over an empty evidence set.
        """
        if status not in LIFECYCLE_STATES:
            raise ValueError(f"Unknown investigation status: {status}")
        if status == "completed" and not self.has_evidence(investigation_id):
            logger.warning(
                "Refusing status 'completed' with no evidence-backed finding; recording 'failed'",
                extra={"investigation_id": investigation_id},
            )
            status = "failed"

        completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute(
                "UPDATE investigations SET status = ?, completed_at = ? WHERE investigation_id = ?",
                (status, completed_at, investigation_id),
            )
            if final_state is not None:
                conn.execute(
                    """
                    INSERT INTO investigation_state_snapshots
                        (investigation_id, check_num, node_name, state_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        investigation_id,
                        int(final_state.get("check_count", 0)),
                        "final",
                        json.dumps(final_state, default=str),
                    ),
                )

    # ------------------------------------------------------------------ reads

    def has_evidence(self, investigation_id: int) -> bool:
        """True when at least one recorded finding cites evidence."""
        for finding in self.list_findings(investigation_id):
            if finding.evidence_ids:
                return True
        return False

    def get_investigation(self, investigation_id: int) -> Investigation | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investigations WHERE investigation_id = ?", (investigation_id,)
            ).fetchone()
        if row is None:
            return None
        baseline = json.loads(row["baseline_score_json"]) if row["baseline_score_json"] else None
        return Investigation(
            investigation_id=row["investigation_id"],
            run_id=row["run_id"],
            table_name=row["table_name"],
            catalog_name=row["catalog_name"],
            schema_name=row["schema_name"],
            status=row["status"],
            max_checks=row["max_checks"],
            current_check=row["current_check"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            snapshot_id=row["snapshot_id"],
            baseline_score=baseline,
        )

    def list_findings(self, investigation_id: int) -> list[Finding]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investigation_findings WHERE investigation_id = ?"
                " ORDER BY check_num",
                (investigation_id,),
            ).fetchall()
        keys = rows[0].keys() if rows else []
        return [
            Finding(
                check_num=row["check_num"],
                question=row["question"],
                exact_result=row["exact_result"],
                verdict=row["verdict"],
                rationale=row["rationale"],
                evidence_ids=json.loads(row["evidence_ids"] or "[]"),
                recommendation=row["recommendation"],
                alternatives=json.loads(row["alternatives_json"] or "[]"),
                validated=bool(row["validated"]),
                check_type=row["check_type"] if "check_type" in keys else None,
                actionable_sql=row["actionable_sql"] if "actionable_sql" in keys else None,
                confidence=row["confidence"] if "confidence" in keys else None,
            )
            for row in rows
        ]

    def list_trail(self, investigation_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investigation_trail WHERE investigation_id = ? ORDER BY trail_id",
                (investigation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_knowledge_references(self, investigation_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM knowledge_references WHERE investigation_id = ?"
                " ORDER BY reference_id",
                (investigation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_hook_violations(self, investigation_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM hook_violations WHERE investigation_id = ? ORDER BY violation_id",
                (investigation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_investigations(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT investigation_id, run_id, table_name, status, started_at, completed_at"
                " FROM investigations ORDER BY investigation_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
