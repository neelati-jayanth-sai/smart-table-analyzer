"""Read immutable report artifacts into the dashboard report model."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.models import Assessment, InvestigationReport
from src.reporting.assessment_policy import assess


def load_report(path: Path) -> InvestigationReport:
    """Load one JSON report artifact without consulting its originating database."""
    data = json.loads(path.read_text(encoding="utf-8"))
    findings = list(data.get("findings") or [])
    assessment = _assessment(data, findings)
    trail = list(data.get("trail") or _trail_from_findings(findings))
    return InvestigationReport(
        investigation_id=int(data["investigation_id"]),
        run_id=str(data["run_id"]),
        table_name=str(data["table_name"]),
        catalog_name=str(data.get("catalog_name") or ""),
        schema_name=str(data.get("schema_name") or ""),
        status=str(data.get("lifecycle_state") or data.get("status") or "incomplete"),
        started_at=str(data.get("started_at") or "unknown"),
        completed_at=data.get("completed_at"),
        snapshot_id=data.get("snapshot_id") or _snapshot_from_findings(findings),
        baseline_score=dict(data.get("baseline_score") or {}),
        score_explanation=dict(data.get("score_explanation") or {}),
        findings=findings,
        knowledge_references=list(data.get("knowledge_references") or []),
        trail=trail,
        hook_violations=list(data.get("hook_violations") or []),
        summary=dict(data.get("summary") or {}),
        assessment=assessment,
        warnings=list(data.get("warnings") or []),
        version=str(data.get("version") or "artifact"),
    )


def _assessment(data: dict[str, Any], findings: list[dict[str, Any]]) -> Assessment:
    saved = data.get("assessment")
    if isinstance(saved, dict) and saved.get("state"):
        return Assessment(
            str(saved["state"]),
            list(saved.get("reasons") or []),
            list(saved.get("required_review_checks") or []),
        )
    return assess(
        str(data.get("lifecycle_state") or data.get("status") or "incomplete"),
        dict(data.get("baseline_score") or {}),
        findings,
        list(data.get("hook_violations") or []),
    )


def _trail_from_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recover the SQL audit supplied by report versions before trail serialization."""
    trail: list[dict[str, Any]] = []
    for finding in findings:
        for query in finding.get("sql") or []:
            trail.append(
                {
                    "check_num": finding.get("check_num", 0),
                    "node_name": "report_query",
                    "query_text": query.get("query"),
                    "rewritten_query": query.get("query"),
                    "execution_status": query.get("status"),
                    "execution_time_ms": query.get("execution_time_ms"),
                    "error_message": query.get("error"),
                }
            )
    return trail


def _snapshot_from_findings(findings: list[dict[str, Any]]) -> str | None:
    """Recover a pinned snapshot from legacy SQL when its report field is absent."""
    for finding in findings:
        for query in finding.get("sql") or []:
            match = re.search(r"VERSION\s+AS\s+OF\s+(\d+)", str(query.get("query") or ""), re.I)
            if match:
                return match.group(1)
    return None
