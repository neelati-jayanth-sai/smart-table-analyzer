"""Evidence domain records independent of collection and persistence adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class EvidenceClass(str, Enum):
    """How strongly the investigation may rely on an evidence record."""

    VERIFIED_FACT = "verified_fact"
    CONFIGURATION_RISK = "configuration_risk"
    HYPOTHESIS = "hypothesis"
    NOT_ASSESSED = "not_assessed"


class AvailabilityState(str, Enum):
    """Whether an evidence module completed for the observed table state."""

    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class Availability:
    """Result status and a human-readable reason when evidence is absent."""

    state: AvailabilityState
    reason: str | None = None

    @property
    def is_available(self) -> bool:
        return self.state is AvailabilityState.COMPLETED


@dataclass(frozen=True)
class EvidenceProvenance:
    """The reproducibility details for one observation."""

    source: str
    snapshot_id: str | None = None
    query_text: str | None = None
    query_parameters: Mapping[str, Any] = field(default_factory=dict)
    observed_at: str | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    """One typed observation returned by an evidence module."""

    module_name: str
    classification: EvidenceClass
    availability: Availability
    summary: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    provenance: EvidenceProvenance = field(default_factory=lambda: EvidenceProvenance(source="unknown"))
    confidence: float | None = None
    exploratory: bool = False
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        if not self.module_name:
            raise ValueError("Evidence module_name is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Evidence confidence must be between 0 and 1")
