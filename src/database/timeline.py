"""Durable append-only investigation timeline storage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TimelineEvent:
    """One user-facing observation in the investigation journal."""

    event_id: int
    investigation_id: int
    event_type: str
    message: str
    status: str
    evidence_ids: tuple[str, ...]
    confidence: float | None
    details: dict[str, Any]
    created_at: str


class TimelineWriteOperations:
    """Append timeline events through the owning database connection."""

    def append_timeline_event(
        self,
        investigation_id: int,
        event_type: str,
        message: str,
        status: str = "info",
        evidence_ids: tuple[str, ...] | list[str] = (),
        confidence: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        if not message.strip():
            raise ValueError("Timeline event message cannot be empty")
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO timeline_events
                (investigation_id, event_type, message, status, evidence_ids_json,
                 confidence, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    investigation_id,
                    event_type,
                    message,
                    status,
                    json.dumps(list(evidence_ids)),
                    confidence,
                    json.dumps(details or {}, default=str),
                ),
            )
            return int(cursor.lastrowid)


class TimelineReadOperations:
    """Read timeline events in durable append order."""

    def list_timeline_events(
        self, investigation_id: int, limit: int | None = None
    ) -> list[TimelineEvent]:
        query = "SELECT * FROM timeline_events WHERE investigation_id = ? ORDER BY event_id"
        params: tuple[Any, ...] = (investigation_id,)
        if limit is not None:
            if limit < 1:
                return []
            query += " LIMIT ?"
            params += (limit,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._timeline_event(row) for row in rows]

    @staticmethod
    def _timeline_event(row: Any) -> TimelineEvent:
        return TimelineEvent(
            event_id=row["event_id"],
            investigation_id=row["investigation_id"],
            event_type=row["event_type"],
            message=row["message"],
            status=row["status"],
            evidence_ids=tuple(json.loads(row["evidence_ids_json"] or "[]")),
            confidence=row["confidence"],
            details=json.loads(row["details_json"] or "{}"),
            created_at=row["created_at"],
        )
