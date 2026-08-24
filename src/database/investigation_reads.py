"""Read operations for the investigation persistence seam."""

from __future__ import annotations

import json
from typing import Any

from src.models import Finding, Investigation


class InvestigationReadOperations:
    """Load investigations and evidence in their domain ordering."""

    def has_evidence(self, investigation_id: int) -> bool:
        """Return whether at least one finding has authoritative table evidence."""
        from src.validation import ClaimValidator

        validator = ClaimValidator(self)
        return any(
            validator.validate(investigation_id, finding).valid
            for finding in self.list_findings(investigation_id)
        )

    def get_investigation(self, investigation_id: int) -> Investigation | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investigations WHERE investigation_id = ?", (investigation_id,)
            ).fetchone()
        if row is None:
            return None
        baseline = json.loads(row["baseline_score_json"]) if row["baseline_score_json"] else None
        return Investigation(
            investigation_id=row["investigation_id"], run_id=row["run_id"],
            table_name=row["table_name"], catalog_name=row["catalog_name"],
            schema_name=row["schema_name"], status=row["status"], max_checks=row["max_checks"],
            current_check=row["current_check"], started_at=row["started_at"],
            completed_at=row["completed_at"], snapshot_id=row["snapshot_id"], baseline_score=baseline,
        )

    def list_findings(self, investigation_id: int) -> list[Finding]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investigation_findings WHERE investigation_id = ? ORDER BY check_num",
                (investigation_id,),
            ).fetchall()
        keys = rows[0].keys() if rows else []
        return [
            Finding(
                check_num=row["check_num"], question=row["question"],
                exact_result=row["exact_result"], verdict=row["verdict"], rationale=row["rationale"],
                evidence_ids=json.loads(row["evidence_ids"] or "[]"), recommendation=row["recommendation"],
                alternatives=json.loads(row["alternatives_json"] or "[]"), validated=bool(row["validated"]),
                check_type=row["check_type"] if "check_type" in keys else None,
                actionable_sql=row["actionable_sql"] if "actionable_sql" in keys else None,
                confidence=row["confidence"] if "confidence" in keys else None,
                issue_state=row["issue_state"] if "issue_state" in keys else "needs_review",
            )
            for row in rows
        ]

    def list_trail(self, investigation_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investigation_trail WHERE investigation_id = ? ORDER BY check_num, trail_id",
                (investigation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_knowledge_references(self, investigation_id: int) -> list[dict[str, Any]]:
        return self._list_rows(
            "knowledge_references", "reference_id", investigation_id
        )

    def list_hook_violations(self, investigation_id: int) -> list[dict[str, Any]]:
        return self._list_rows("hook_violations", "violation_id", investigation_id)

    def _list_rows(self, table: str, order: str, investigation_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE investigation_id = ? ORDER BY {order}",
                (investigation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_investigations(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT investigation_id, run_id, table_name, status, started_at, completed_at
                FROM investigations ORDER BY investigation_id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
