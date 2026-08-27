"""Core collection and full-profile completion for one investigation."""

from __future__ import annotations

from src.context import InvestigationContext
from src.metadata.collection_profile import MetadataCollectionProfile

from .legacy_analyzer import LegacyAnalyzer


def collect_core(
    spark,
    profile: MetadataCollectionProfile,
    table_name: str,
    catalog_name: str,
    schema_name: str,
    snapshot_id: str | None,
    query_metrics_table: str | None,
) -> InvestigationContext:
    """Return enough deterministic evidence for the investigation to begin."""
    return LegacyAnalyzer(spark, profile).collect_core(
        table_name, catalog_name, schema_name, snapshot_id, query_metrics_table
    )


def complete_profile(
    spark, profile: MetadataCollectionProfile, context: InvestigationContext
) -> InvestigationContext:
    """Append the requested column profile to the core context."""
    return LegacyAnalyzer(spark, profile).complete_profile(context)


def report_core_findings(progress, context: InvestigationContext, investigation_id: int) -> None:
    """Publish measured signals as human-readable live updates."""
    for signal in context.signals:
        progress("finding", _finding_message(signal), investigation_id)


def _finding_message(signal: dict) -> str:
    if signal.get("name") != "table_property_naming":
        return str(signal["detail"])
    properties = signal.get("metrics", {}).get("properties") or []
    canonical = signal.get("metrics", {}).get("canonical_properties") or []
    if properties and canonical:
        return (
            f"I found a configuration risk: '{properties[0]}' uses uppercase or mixed case. "
            f"Iceberg expects '{canonical[0]}', so the intended setting may be ignored."
        )
    return "I found Iceberg configuration properties with noncanonical casing."
