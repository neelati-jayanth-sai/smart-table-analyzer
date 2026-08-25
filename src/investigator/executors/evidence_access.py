"""Read-only evidence access for the Analyst tool seam."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from src.evidence import EvidenceRecord


def list_evidence_tool() -> dict[str, Any]:
    """Describe the bounded evidence-summary tool exposed to the Analyst."""
    return {
        "type": "function",
        "function": {
            "name": "list_evidence",
            "description": "List persisted evidence summaries for this investigation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "module_name": {"type": "string", "description": "Exact module filter."},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": EvidenceAccess.MAX_SUMMARIES,
                        "description": "Maximum summaries to return.",
                    },
                },
            },
        },
    }


def fetch_evidence_tool() -> dict[str, Any]:
    """Describe the one-record evidence tool exposed to the Analyst."""
    return {
        "type": "function",
        "function": {
            "name": "fetch_evidence",
            "description": "Fetch the payload and provenance of one listed evidence record.",
            "parameters": {
                "type": "object",
                "properties": {"evidence_id": {"type": "string"}},
                "required": ["evidence_id"],
            },
        },
    }


class EvidenceAccess:
    """Scope and format persisted evidence without mutating the investigation."""

    MAX_SUMMARIES = 20
    MAX_PAYLOAD_CHARACTERS = 20_000

    def __init__(self, db) -> None:
        self.db = db

    def list(self, investigation_id: int, arguments: dict[str, Any]) -> str:
        records = self._records(investigation_id)
        module_name = arguments.get("module_name")
        if isinstance(module_name, str) and module_name:
            records = [record for record in records if record.module_name == module_name]
        limit = self._limit(arguments.get("limit"))
        summaries = [self._summary(record) for record in records[:limit]]
        return self._render({
            "tool": "list_evidence",
            "total_matching": len(records),
            "returned_count": len(summaries),
            "evidence": summaries,
        })

    def fetch(self, investigation_id: int, arguments: dict[str, Any]) -> str:
        evidence_id = arguments.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id.startswith("evidence:"):
            return self._render({"tool": "fetch_evidence", "error": "A listed evidence_id is required."})
        record = next(
            (item for item in self._records(investigation_id) if item.evidence_id == evidence_id),
            None,
        )
        if record is None:
            return self._render({
                "tool": "fetch_evidence",
                "error": "Evidence was not found in this investigation.",
            })
        payload, truncated = self._bounded_payload(record.payload)
        return self._render({
            "tool": "fetch_evidence",
            "evidence_id": record.evidence_id,
            "module_name": record.module_name,
            "classification": record.classification.value,
            "availability": record.availability.state.value,
            "summary": record.summary,
            "payload": payload,
            "payload_truncated": truncated,
            "provenance": asdict(record.provenance),
            "confidence": record.confidence,
            "exploratory": record.exploratory,
        })

    def _records(self, investigation_id: int) -> list[EvidenceRecord]:
        return list(self.db.list_evidence(investigation_id))

    def _limit(self, value: Any) -> int:
        return min(value, self.MAX_SUMMARIES) if isinstance(value, int) and value > 0 else self.MAX_SUMMARIES

    def _bounded_payload(self, payload: Any) -> tuple[Any, bool]:
        encoded = json.dumps(payload, default=str)
        if len(encoded) <= self.MAX_PAYLOAD_CHARACTERS:
            return payload, False
        return {"preview": encoded[:self.MAX_PAYLOAD_CHARACTERS]}, True

    @staticmethod
    def _summary(record: EvidenceRecord) -> dict[str, Any]:
        return {
            "evidence_id": record.evidence_id,
            "module_name": record.module_name,
            "classification": record.classification.value,
            "availability": record.availability.state.value,
            "summary": record.summary,
            "confidence": record.confidence,
            "exploratory": record.exploratory,
        }

    @staticmethod
    def _render(payload: dict[str, Any]) -> str:
        return json.dumps(payload, default=str)
