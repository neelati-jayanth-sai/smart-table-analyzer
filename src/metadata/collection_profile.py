"""Choose whether collection may read table data or only Iceberg metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass


_PROFILE_ENV = "METADATA_COLLECTION_PROFILE"


@dataclass(frozen=True)
class MetadataCollectionProfile:
    """The collection Interface for controlling data-reading work."""

    name: str
    include_sample_rows: bool
    analyze_column_stats: bool

    @classmethod
    def from_name(cls, name: str | None) -> "MetadataCollectionProfile":
        profile = (name or os.getenv(_PROFILE_ENV, "fast")).strip().lower()
        if profile == "fast":
            return cls("fast", include_sample_rows=False, analyze_column_stats=False)
        if profile == "deep":
            return cls("deep", include_sample_rows=True, analyze_column_stats=True)
        raise ValueError("METADATA_COLLECTION_PROFILE must be 'fast' or 'deep'")

