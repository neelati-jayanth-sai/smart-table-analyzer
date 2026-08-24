"""SQLite connection and lifecycle ownership for investigation persistence."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.models import ASSESSMENT_VERSION, LIFECYCLE_STATES

from .investigation_reads import InvestigationReadOperations
from .investigation_writes import InvestigationWriteOperations
from .schema import create_schema

logger = logging.getLogger(__name__)


class InvestigationDb(InvestigationWriteOperations, InvestigationReadOperations):
    """Own SQLite lifecycle; read and write adapters share its connection seam."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

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
                """INSERT INTO investigations
                (run_id, table_name, catalog_name, schema_name, status, snapshot_id, max_checks)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
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
        logger.info("Investigation status -> %s", status, extra={"investigation_id": investigation_id})

    def record_baseline_score(
        self,
        investigation_id: int,
        overall_score: float,
        dimensions: dict[str, Any],
        signals: list[dict[str, Any]] | None = None,
        metadata_evidence: dict[str, Any] | None = None,
    ) -> None:
        payload = json.dumps(
            {
                "overall": overall_score,
                "dimensions": dimensions,
                "signals": signals or [],
                "metadata_evidence": metadata_evidence or {},
                "assessment_version": ASSESSMENT_VERSION,
            },
            default=str,
        )
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO baseline_scores (investigation_id, overall_score, dimensions_json)
                VALUES (?, ?, ?)
                ON CONFLICT(investigation_id) DO UPDATE SET
                    overall_score=excluded.overall_score, dimensions_json=excluded.dimensions_json""",
                (investigation_id, float(overall_score), json.dumps(dimensions, default=str)),
            )
            conn.execute(
                "UPDATE investigations SET baseline_score_json = ? WHERE investigation_id = ?",
                (payload, investigation_id),
            )

    def complete_investigation(
        self,
        investigation_id: int,
        status: str,
        final_state: dict[str, Any] | None = None,
    ) -> None:
        """Terminate only an evidence-backed completed investigation."""
        if status not in LIFECYCLE_STATES:
            raise ValueError(f"Unknown investigation status: {status}")
        if status == "completed" and not self.has_evidence(investigation_id):
            logger.warning(
                "Refusing completed status without evidence", extra={"investigation_id": investigation_id}
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
                    """INSERT INTO investigation_state_snapshots
                    (investigation_id, check_num, node_name, state_json) VALUES (?, ?, ?, ?)""",
                    (
                        investigation_id,
                        int(final_state.get("check_count", 0)),
                        "final",
                        json.dumps(final_state, default=str),
                    ),
                )
