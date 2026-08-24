"""Legacy Analyzer — the deterministic sensor layer.

It observes the table once and emits facts:

    InvestigationContext(metadata, signals, baseline, runtime)

It must never call an LLM, never explain a root cause, never prioritise an
investigation, and never emit a recommendation. Every interpretation of these
facts belongs to `src/investigator/`.
"""

from __future__ import annotations

import logging

from src.calculators.baseline_scorer import score as compute_score
from src.context import InvestigationContext
from src.metadata.loader import load_table_metadata
from src.metadata.collection_profile import MetadataCollectionProfile

from .metrics import MetadataUnavailable, collect_raw_metrics, extract_query_patterns
from .signals import detect_signals

logger = logging.getLogger(__name__)

__all__ = ["LegacyAnalyzer", "MetadataUnavailable"]


class LegacyAnalyzer:
    """Collect Iceberg metadata once and turn it into an InvestigationContext."""

    def __init__(self, spark, metadata_profile: MetadataCollectionProfile | None = None):
        self.spark = spark
        self.metadata_profile = metadata_profile or MetadataCollectionProfile.from_name(None)

    def collect(
        self,
        table_name: str,
        catalog_name: str = "",
        schema_name: str = "",
        snapshot_id: str | None = None,
        query_metrics_table: str | None = None,
    ) -> InvestigationContext:
        """Read the table once and return the investigation's source of truth."""
        logger.info("Legacy Analyzer: collecting %s", table_name)

        raw = collect_raw_metrics(self.spark, table_name, snapshot_id)
        patterns = extract_query_patterns(self.spark, table_name, query_metrics_table)
        metadata = load_table_metadata(
            self.spark,
            table_name,
            row_count=int(raw.get("row_count", 0)),
            profile=self.metadata_profile,
        )
        metadata["observation"] = {
            "snapshot_id": snapshot_id,
            "metrics_snapshot_pinned": bool(snapshot_id),
            "live_sources": ["schema", "ddl", "table_properties"],
            "consistency": "metrics pinned; table setup observed live" if snapshot_id else "snapshot unavailable",
        }
        if patterns:
            metadata["query_patterns"] = patterns

        signals = detect_signals(raw, metadata, patterns)
        baseline = compute_score(raw, patterns)
        baseline["signals"] = signals

        logger.info(
            "Legacy Analyzer: score=%.1f, %d signal(s): %s",
            baseline["overall"],
            len(signals),
            ", ".join(f"{s['name']}={s['severity']}" for s in signals) or "none",
        )

        return InvestigationContext(
            table_name=table_name,
            catalog_name=catalog_name,
            schema_name=schema_name,
            snapshot_id=snapshot_id,
            metadata=metadata,
            signals=signals,
            baseline=baseline,
        )
