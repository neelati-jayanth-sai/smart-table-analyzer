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
    """Check that every evidence ID resolves to a trail entry or knowledge reference."""

    _TRAIL_RE = re.compile(r"^trail:(\d+)$")
    _KNOWLEDGE_RE = re.compile(r"^knowledge:([^/]+)/(.+)@([^@]+)$")

    def __init__(self, db: InvestigationDb):
        self._db = db

    def validate(self, investigation_id: int, finding: Finding) -> ValidationResult:
        """Validate all evidence IDs declared by a finding."""
        missing_ids: list[str] = []
        errors: list[str] = []

        if not finding.evidence_ids:
            errors.append("Finding has no evidence IDs")

        trail_checks = self._trail_check_nums(investigation_id)
        knowledge_keys = self._knowledge_keys(investigation_id)

        for evidence_id in finding.evidence_ids:
            if not self._is_valid_id(evidence_id, trail_checks, knowledge_keys):
                missing_ids.append(evidence_id)

        if missing_ids:
            errors.append(f"Missing or unrelated evidence IDs: {missing_ids}")

        return ValidationResult(valid=not errors, missing_ids=missing_ids, errors=errors)

    def _is_valid_id(
        self,
        evidence_id: str,
        trail_checks: set[int],
        knowledge_keys: set[str],
    ) -> bool:
        trail_match = self._TRAIL_RE.match(evidence_id)
        if trail_match:
            check_num = int(trail_match.group(1))
            return check_num in trail_checks

        knowledge_match = self._KNOWLEDGE_RE.match(evidence_id)
        if knowledge_match:
            source, topic_path, version = knowledge_match.groups()
            return f"{source}/{topic_path}@{version}" in knowledge_keys

        return False

    def _trail_check_nums(self, investigation_id: int) -> set[int]:
        return {entry["check_num"] for entry in self._db.list_trail(investigation_id)}

    def _knowledge_keys(self, investigation_id: int) -> set[str]:
        refs = self._db.get_knowledge_references(investigation_id)
        return {f"{ref['source']}/{ref['topic_path']}@{ref['version']}" for ref in refs}
