"""Whole-run LLM critique constrained to persisted evidence and coverage."""

from __future__ import annotations

import json
from typing import Any


_LIST_FIELDS = (
    "consistency_issues", "unsupported_certainty", "duplicate_recommendations",
    "missing_justification", "coverage_gaps",
)


def run_final_review(llm, db, investigation_id: int) -> dict[str, Any]:
    """Request a structured final critique and safely preserve a fallback."""
    prompt = _prompt(db, investigation_id)
    try:
        response = llm.generate(prompt)
        return _parse(response.get("content") or "")
    except Exception as exc:
        return _fallback(f"Final review unavailable: {exc}")


def _prompt(db, investigation_id: int) -> list[dict[str, str]]:
    findings = [
        {
            "check_num": finding.check_num, "verdict": finding.verdict,
            "exact_result": finding.exact_result, "rationale": finding.rationale,
            "recommendation": finding.recommendation, "confidence": finding.confidence,
            "evidence_ids": finding.evidence_ids,
        }
        for finding in db.list_findings(investigation_id)
    ]
    coverage = [
        {"module": entry.module_name, "status": entry.availability.state.value,
         "reason": entry.availability.reason, "evidence_ids": entry.evidence_ids}
        for entry in db.get_coverage_ledger(investigation_id).entries
    ]
    payload = {"findings": findings, "coverage": coverage}
    return [
        {"role": "system", "content": (
            "Review the supplied investigation for internal consistency and evidence completeness. "
            "Do not introduce facts. Return JSON only with outcome ('approved' or 'needs_review'), "
            "summary, and arrays named consistency_issues, unsupported_certainty, "
            "duplicate_recommendations, missing_justification, coverage_gaps."
        )},
        {"role": "user", "content": json.dumps(payload, default=str)},
    ]


def _parse(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return _fallback("Final review did not return JSON.", status="invalid")
    if not isinstance(payload, dict) or payload.get("outcome") not in {"approved", "needs_review"}:
        return _fallback("Final review omitted a valid outcome.", status="invalid")
    if not isinstance(payload.get("summary"), str):
        return _fallback("Final review omitted a summary.", status="invalid")
    review = {"status": "completed", "outcome": payload["outcome"], "summary": payload["summary"]}
    for field in _LIST_FIELDS:
        values = payload.get(field, [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            return _fallback(f"Final review field '{field}' is invalid.", status="invalid")
        review[field] = values
    return review


def _fallback(error: str, status: str = "fallback") -> dict[str, Any]:
    return {
        "status": status, "outcome": "not_assessed", "summary": "Whole-run review is unavailable.",
        "consistency_issues": [], "unsupported_certainty": [], "duplicate_recommendations": [],
        "missing_justification": [], "coverage_gaps": [], "error": error,
    }
