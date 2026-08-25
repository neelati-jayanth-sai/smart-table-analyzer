"""Coverage records that make completed and unavailable evidence explicit."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Availability


@dataclass(frozen=True)
class CoverageEntry:
    """Coverage outcome for one applicable evidence module."""

    module_name: str
    availability: Availability
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.module_name:
            raise ValueError("Coverage module_name is required")


@dataclass(frozen=True)
class CoverageLedger:
    """Ordered coverage view for one investigation."""

    entries: tuple[CoverageEntry, ...] = field(default_factory=tuple)

    def completed_modules(self) -> tuple[str, ...]:
        return tuple(entry.module_name for entry in self.entries if entry.availability.is_available)

    def incomplete_modules(self) -> tuple[CoverageEntry, ...]:
        return tuple(entry for entry in self.entries if not entry.availability.is_available)
