"""Assemble an InvestigationReport from persisted investigation records."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.calculators.baseline_scorer import explain_score
from src.database import InvestigationDb
from src.validation import ClaimValidator


class ReportAssembler:
    """Read one investigation back out of SQLite and validate every claim.

    This layer consumes findings — it never invents them. A finding whose
    evidence IDs do not resolve is reported as unvalidated, not dropped and not
    silently promoted.
    """

    def __init__(self, db: InvestigationDb):
        self._db = db
        self._validator = ClaimValidator(db)

    def assemble(self, investigation_id: int):
        from src.models import InvestigationReport

        investigation = self._db.get_investigation(investigation_id)
        if investigation is None:
            raise ValueError(f"Investigation {investigation_id} not found")

        findings = self._db.list_findings(investigation_id)
        trail = self._db.list_trail(investigation_id)
        hook_violations = self._db.list_hook_violations(investigation_id)
        knowledge_references = self._db.get_knowledge_references(investigation_id)

        finding_dicts = []
        for finding in findings:
            result = self._validator.validate(investigation_id, finding)
            entry: dict[str, Any] = asdict(finding)
            entry["db_validated"] = bool(finding.validated)
            entry["validation"] = {
                "valid": result.valid,
                "missing_ids": result.missing_ids,
                "errors": result.errors,
            }
            entry["sql"] = _sql_for_check(trail, finding.check_num)
            finding_dicts.append(entry)

        baseline = investigation.baseline_score or {}
        dimensions = baseline.get("dimensions") or {}

        validated = sum(1 for f in finding_dicts if f["validation"]["valid"])
        summary = {
            "total_findings": len(finding_dicts),
            "validated_findings": validated,
            "hook_violations": len(hook_violations),
            "total_queries": len(trail),
            "root_causes": sum(
                1
                for f in finding_dicts
                if f["verdict"] == "found" and f["validation"]["valid"]
            ),
        }

        return InvestigationReport(
            investigation_id=investigation_id,
            run_id=investigation.run_id,
            table_name=investigation.table_name,
            catalog_name=investigation.catalog_name,
            schema_name=investigation.schema_name,
            status=investigation.status,
            started_at=investigation.started_at,
            completed_at=investigation.completed_at,
            baseline_score=baseline,
            score_explanation=explain_score(dimensions),
            findings=finding_dicts,
            knowledge_references=knowledge_references,
            trail=trail,
            hook_violations=hook_violations,
            summary=summary,
            warnings=_warnings(finding_dicts, trail, hook_violations, investigation.status),
        )


def _sql_for_check(trail: list[dict[str, Any]], check_num: int) -> list[dict[str, Any]]:
    """Return the queries executed for one check, for the SQL Validation section."""
    return [
        {
            "query": entry.get("rewritten_query") or entry.get("query_text"),
            "status": entry.get("execution_status"),
            "execution_time_ms": entry.get("execution_time_ms"),
            "error": entry.get("error_message"),
        }
        for entry in trail
        if entry.get("check_num") == check_num and entry.get("query_text")
    ]


def _warnings(
    findings: list[dict[str, Any]],
    trail: list[dict[str, Any]],
    hook_violations: list[dict[str, Any]],
    status: str,
) -> list[str]:
    """Surface degraded execution instead of hiding it behind an empty finding."""
    warnings: list[str] = []

    blocked = [e for e in trail if e.get("execution_status") == "hook_failed"]
    if blocked:
        warnings.append(
            f"{len(blocked)} query/queries were blocked by a safety hook; those checks "
            "fell back to metadata-only reasoning and their evidence is weaker."
        )
    if hook_violations:
        names = sorted({v["hook_name"] for v in hook_violations})
        warnings.append(f"Hook violations recorded by: {', '.join(names)}.")

    failed = [e for e in trail if e.get("execution_status") in ("error", "timeout")]
    if failed:
        warnings.append(f"{len(failed)} query/queries failed or timed out during execution.")

    unvalidated = [f for f in findings if not f["validation"]["valid"]]
    if unvalidated:
        warnings.append(
            f"{len(unvalidated)} finding(s) cite evidence that could not be resolved and "
            "are reported as unvalidated."
        )
    if status != "completed":
        warnings.append(f"Investigation ended with status '{status}'.")
    return warnings
