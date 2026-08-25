"""Choose whether collection may read table data or only Iceberg metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


_PROFILE_ENV = "METADATA_COLLECTION_PROFILE"


@dataclass(frozen=True)
class MetadataCollectionProfile:
    """The collection Interface for controlling data-reading work."""

    name: str
    include_sample_rows: bool
    analyze_column_stats: bool
    profile_all_primitive_columns: bool = False

    def contract(self) -> dict[str, Any]:
        """Describe the deterministic collection work this profile guarantees."""
        return {
            "mode": self.name,
            "sample_rows": "bounded" if self.include_sample_rows else "disabled",
            "column_profile": (
                "all_primitive_columns_in_bounded_batches"
                if self.profile_all_primitive_columns else "disabled"
            ),
        }

    @classmethod
    def from_name(cls, name: str | None) -> "MetadataCollectionProfile":
        profile = (name or os.getenv(_PROFILE_ENV, "fast")).strip().lower()
        if profile in {"fast", "shallow"}:
            return cls(
                "fast", include_sample_rows=False, analyze_column_stats=False,
                profile_all_primitive_columns=False,
            )
        if profile == "deep":
            return cls(
                "deep", include_sample_rows=True, analyze_column_stats=True,
                profile_all_primitive_columns=True,
            )
        raise ValueError("METADATA_COLLECTION_PROFILE must be 'fast' or 'deep' (legacy: 'shallow')")
