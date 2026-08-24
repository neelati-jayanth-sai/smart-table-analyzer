"""Write operations for the investigation persistence seam."""

from __future__ import annotations

import json
from typing import Any

from src.models import Finding


class InvestigationWriteOperations:
    """Append or upsert investigation evidence through the owning database."""

    def record_knowledge_fetch(
        self, investigation_id: int, check_num: int, source: str, topic_path: str, version: str
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO knowledge_references
                (investigation_id, check_num, source, topic_path, version) VALUES (?, ?, ?, ?, ?)""",
                (investigation_id, check_num, source, topic_path, version),
            )
            return int(cursor.lastrowid)

    def record_query(
        self, investigation_id: int, check_num: int, node_name: str, query_text: str | None,
        rewritten_query: str | None = None, query_result: dict[str, Any] | None = None,
        execution_status: str | None = None, execution_time_ms: int | None = None,
        error_message: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO investigation_trail
                (investigation_id, check_num, node_name, query_text, rewritten_query,
                 query_result_json, execution_status, execution_time_ms, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    investigation_id, check_num, node_name, query_text, rewritten_query,
                    json.dumps(query_result, default=str) if query_result is not None else None,
                    execution_status, execution_time_ms, error_message,
                ),
            )
            return int(cursor.lastrowid)

    def record_finding(self, investigation_id: int, finding: Finding) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO investigation_findings
                (investigation_id, check_num, question, exact_result, verdict, rationale,
                 evidence_ids, recommendation, alternatives_json, validated,
                 check_type, actionable_sql, confidence, issue_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(investigation_id, check_num) DO UPDATE SET
                    question=excluded.question, exact_result=excluded.exact_result,
                    verdict=excluded.verdict, rationale=excluded.rationale,
                    evidence_ids=excluded.evidence_ids, recommendation=excluded.recommendation,
                    alternatives_json=excluded.alternatives_json, validated=excluded.validated,
                    check_type=excluded.check_type, actionable_sql=excluded.actionable_sql,
                    confidence=excluded.confidence, issue_state=excluded.issue_state""",
                (
                    investigation_id, finding.check_num, finding.question, finding.exact_result,
                    finding.verdict, finding.rationale, json.dumps(list(finding.evidence_ids or [])),
                    finding.recommendation, json.dumps(list(finding.alternatives or [])),
                    1 if finding.validated else 0, finding.check_type, finding.actionable_sql,
                    finding.confidence, finding.issue_state,
                ),
            )
            conn.execute(
                "UPDATE investigations SET current_check = MAX(current_check, ?) WHERE investigation_id = ?",
                (finding.check_num + 1, investigation_id),
            )
            return int(cursor.lastrowid)

    def record_hook_violation(
        self, investigation_id: int, check_num: int, query_text: str, hook_name: str,
        reason: str | None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO hook_violations
                (investigation_id, check_num, query_text, hook_name, reason) VALUES (?, ?, ?, ?, ?)""",
                (investigation_id, check_num, query_text, hook_name, reason or ""),
            )
            return int(cursor.lastrowid)
