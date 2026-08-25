"""Write operations for the investigation persistence seam."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from src.evidence import CoverageEntry, EvidenceRecord
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

    def record_evidence(self, investigation_id: int, evidence: EvidenceRecord) -> int:
        """Persist one evidence observation without changing existing finding flow."""
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO evidence_records
                (investigation_id, module_name, classification, availability_state,
                 availability_reason, summary, payload_json, provenance_json,
                 confidence, exploratory)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    investigation_id, evidence.module_name, evidence.classification.value,
                    evidence.availability.state.value, evidence.availability.reason, evidence.summary,
                    json.dumps(dict(evidence.payload), default=str),
                    json.dumps(asdict(evidence.provenance), default=str), evidence.confidence,
                    1 if evidence.exploratory else 0,
                ),
            )
            return int(cursor.lastrowid)

    def record_coverage(self, investigation_id: int, entry: CoverageEntry) -> int:
        """Upsert the current coverage outcome for one evidence module."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO coverage_ledger
                (investigation_id, module_name, availability_state, reason, evidence_ids_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(investigation_id, module_name) DO UPDATE SET
                    availability_state=excluded.availability_state,
                    reason=excluded.reason,
                    evidence_ids_json=excluded.evidence_ids_json,
                    updated_at=datetime('now')""",
                (
                    investigation_id, entry.module_name, entry.availability.state.value,
                    entry.availability.reason, json.dumps(list(entry.evidence_ids)),
                ),
            )
            row = conn.execute(
                """SELECT coverage_id FROM coverage_ledger
                WHERE investigation_id = ? AND module_name = ?""",
                (investigation_id, entry.module_name),
            ).fetchone()
            return int(row["coverage_id"])

    def record_final_review(self, investigation_id: int, review: dict[str, Any]) -> None:
        """Upsert one whole-investigation critique without changing findings."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO investigation_final_reviews
                (investigation_id, review_status, review_json, error_message)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(investigation_id) DO UPDATE SET
                    review_status=excluded.review_status, review_json=excluded.review_json,
                    error_message=excluded.error_message, created_at=datetime('now')""",
                (
                    investigation_id, review["status"], json.dumps(review, default=str),
                    review.get("error"),
                ),
            )
