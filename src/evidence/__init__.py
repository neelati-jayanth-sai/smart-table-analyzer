"""Typed evidence and coverage records for investigations."""

from .coverage import CoverageEntry, CoverageLedger
from .collection_adapter import (
    CollectionEvidenceAdapter,
    CollectionEvidenceBundle,
    persist_collection_evidence,
    persist_column_profile_evidence,
)
from .models import (
    Availability,
    AvailabilityState,
    EvidenceClass,
    EvidenceProvenance,
    EvidenceRecord,
)

__all__ = [
    "Availability",
    "AvailabilityState",
    "CollectionEvidenceAdapter",
    "CollectionEvidenceBundle",
    "CoverageEntry",
    "CoverageLedger",
    "EvidenceClass",
    "EvidenceProvenance",
    "EvidenceRecord",
    "persist_collection_evidence",
    "persist_column_profile_evidence",
]
