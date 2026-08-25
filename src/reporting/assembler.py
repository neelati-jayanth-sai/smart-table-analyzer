"""Assemble an InvestigationReport from persisted investigation records."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.calculators.baseline_scorer import explain_score
from src.database import InvestigationDb
from src.validation import ClaimValidator

from .assessment_policy import assess


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
        coverage = _coverage_rows(self._db.get_coverage_ledger(investigation_id))
        final_review = self._db.get_final_review(investigation_id) or {
            "status": "not_available", "summary": "Whole-run review was not recorded."
        }
        evidence = self._db.list_evidence(investigation_id)

        finding_dicts = []
        for finding in findings:
            result = self._validator.validate(investigation_id, finding)
            entry: dict[str, Any] = asdict(finding)
            entry["db_validated"] = bool(finding.validated)
            entry["evidence_validated"] = result.valid
            entry["validated"] = bool(finding.validated and result.valid)
            entry["validation"] = {
                "valid": result.valid,
                "missing_ids": result.missing_ids,
                "errors": result.errors,
            }
            entry["sql"] = _sql_for_check(trail, finding.check_num)
            finding_dicts.append(entry)

        baseline = investigation.baseline_score or {}
        dimensions = baseline.get("dimensions") or {}

        validated = sum(
            1 for f in finding_dicts if f["db_validated"] and f["validation"]["valid"]
        )
        summary = {
            "total_findings": len(finding_dicts),
            "validated_findings": validated,
            "hook_violations": len(hook_violations),
            "total_queries": len(trail),
            "root_causes": sum(
                1
                for f in finding_dicts
                if f.get("verdict") == "found"
                and f.get("issue_state") == "issue_found"
                and f.get("db_validated")
                and f["validation"]["valid"]
            ),
            "coverage_completed": sum(item["status"] == "completed" for item in coverage),
            "coverage_total": len(coverage),
        }

        assessment = assess(
            investigation.status, baseline, finding_dicts, hook_violations,
            coverage=coverage, collection_profile=_collection_profile(evidence), final_review=final_review,
        )
        return InvestigationReport(
            investigation_id=investigation_id,
            run_id=investigation.run_id,
            table_name=investigation.table_name,
            catalog_name=investigation.catalog_name,
            schema_name=investigation.schema_name,
            status=investigation.status,
            started_at=investigation.started_at,
            completed_at=investigation.completed_at,
            snapshot_id=investigation.snapshot_id,
            baseline_score=baseline,
            score_explanation=explain_score(dimensions),
            findings=finding_dicts,
            knowledge_references=knowledge_references,
            trail=trail,
            hook_violations=hook_violations,
            summary=summary,
            assessment=assessment,
            warnings=_warnings(
                finding_dicts,
                trail,
                hook_violations,
                investigation.status,
                baseline.get("signals") or [],
                coverage,
                final_review,
            ),
            coverage=coverage,
            final_review=final_review,
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


def _coverage_rows(ledger) -> list[dict[str, Any]]:
    return [
        {"module": entry.module_name, "status": entry.availability.state.value,
         "reason": entry.availability.reason, "evidence_ids": list(entry.evidence_ids)}
        for entry in ledger.entries
    ]


def _collection_profile(evidence) -> str | None:
    identity = next((record for record in evidence if record.module_name == "identity_schema"), None)
    return identity.payload.get("collection_profile") if identity else None


def _warnings(
    findings: list[dict[str, Any]],
    trail: list[dict[str, Any]],
    hook_violations: list[dict[str, Any]],
    status: str,
    signals: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    final_review: dict[str, Any],
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

    unvalidated = [
        f for f in findings if not f["db_validated"] or not f["validation"]["valid"]
    ]
    if unvalidated:
        warnings.append(
            f"{len(unvalidated)} finding(s) cite evidence that could not be resolved and "
            "are reported as unvalidated."
        )
    high_signals = [signal for signal in signals if signal.get("severity") == "HIGH"]
    if high_signals:
        details = "; ".join(signal.get("detail", signal.get("name", "signal")) for signal in high_signals)
        warnings.append(
            "High-severity deterministic measurement(s) require review even when an "
            f"LLM check returns no root cause: {details}."
        )
    if status != "completed":
        warnings.append(f"Investigation ended with status '{status}'.")
    fast_skips = [item for item in coverage if item["module"] == "column_profile" and item["status"] == "skipped"]
    if fast_skips:
        warnings.append("Column profiling was not assessed in Fast collection.")
    if final_review.get("status") != "completed":
        warnings.append("Whole-run consistency review was unavailable; inspect coverage directly.")
    return warnings
