"""Validate finding evidence IDs against investigation records."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.database import Finding, InvestigationDb


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a finding's evidence IDs."""

    valid: bool
    missing_ids: list[str]
    errors: list[str]


class ClaimValidator:
    """Validate claims against successful evidence owned by the investigation."""

    _TRAIL_RE = re.compile(r"^trail:(\d+)$")
    _KNOWLEDGE_RE = re.compile(r"^knowledge:([^/]+)/(.+)@([^@]+)$")
    _EVIDENCE_RE = re.compile(r"^evidence:(\d+)$")

    def __init__(self, db: InvestigationDb):
        self._db = db

    def validate(self, investigation_id: int, finding: Finding) -> ValidationResult:
        """Validate all evidence IDs declared by a finding."""
        missing_ids: list[str] = []
        errors: list[str] = []

        if not finding.evidence_ids:
            errors.append("Finding has no evidence IDs")

        successful_trail_checks = self._successful_trail_check_nums(investigation_id)
        knowledge_keys = self._knowledge_keys(investigation_id)
        deterministic_records = self._deterministic_records(investigation_id)
        has_successful_table_evidence = False

        for evidence_id in finding.evidence_ids:
            if self._is_successful_trail_id(
                evidence_id, finding.check_num, successful_trail_checks
            ):
                has_successful_table_evidence = True
                continue
            if self._is_completed_evidence_id(evidence_id, deterministic_records):
                has_successful_table_evidence = True
                continue
            if not self._is_valid_id(
                evidence_id, finding.check_num, successful_trail_checks, knowledge_keys,
                deterministic_records,
            ):
                missing_ids.append(evidence_id)

        if missing_ids:
            errors.append(f"Missing or unrelated evidence IDs: {missing_ids}")
        if not has_successful_table_evidence:
            errors.append("Finding has no successful table-query or deterministic evidence")

        return ValidationResult(valid=not errors, missing_ids=missing_ids, errors=errors)

    def _is_valid_id(
        self,
        evidence_id: str,
        finding_check_num: int,
        trail_checks: set[int],
        knowledge_keys: set[str],
        deterministic_records: dict[str, bool],
    ) -> bool:
        trail_match = self._TRAIL_RE.match(evidence_id)
        if trail_match:
            check_num = int(trail_match.group(1))
            return check_num == finding_check_num and check_num in trail_checks

        knowledge_match = self._KNOWLEDGE_RE.match(evidence_id)
        if knowledge_match:
            source, topic_path, version = knowledge_match.groups()
            return f"{source}/{topic_path}@{version}" in knowledge_keys

        return evidence_id in deterministic_records

    def _is_successful_trail_id(
        self, evidence_id: str, finding_check_num: int, trail_checks: set[int]
    ) -> bool:
        match = self._TRAIL_RE.match(evidence_id)
        return bool(
            match
            and int(match.group(1)) == finding_check_num
            and int(match.group(1)) in trail_checks
        )

    def _successful_trail_check_nums(self, investigation_id: int) -> set[int]:
        return {
            entry["check_num"]
            for entry in self._db.list_trail(investigation_id)
            if entry.get("execution_status") == "success"
            and entry.get("query_text")
            and entry.get("query_result_json") is not None
        }

    def _knowledge_keys(self, investigation_id: int) -> set[str]:
        refs = self._db.get_knowledge_references(investigation_id)
        return {f"{ref['source']}/{ref['topic_path']}@{ref['version']}" for ref in refs}

    def _deterministic_records(self, investigation_id: int) -> dict[str, bool]:
        return {
            record.evidence_id: record.availability.is_available
            for record in self._db.list_evidence(investigation_id)
            if record.evidence_id
        }

    def _is_completed_evidence_id(self, evidence_id: str, records: dict[str, bool]) -> bool:
        return bool(self._EVIDENCE_RE.match(evidence_id) and records.get(evidence_id))
