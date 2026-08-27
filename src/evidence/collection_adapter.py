"""Adapt deterministic collection facts into persisted evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coverage import CoverageEntry
from .models import Availability, AvailabilityState, EvidenceClass, EvidenceProvenance, EvidenceRecord

_LAYOUT_SIGNALS = {
    "empty_table", "measurement_unavailable", "small_files", "large_files",
    "undersized_partitions", "partition_skew", "unpartitioned", "missing_sort_order",
    "delete_overhead", "manifest_health", "snapshot_retention",
}
_PROPERTY_SIGNALS = {"table_property_naming", "custom_property_naming"}
_WORKLOAD_SIGNALS = {"poor_pruning"}


@dataclass(frozen=True)
class CollectionEvidenceBundle:
    """Collection records and their matching coverage outcomes."""

    records: tuple[EvidenceRecord, ...]
    coverage: tuple[CoverageEntry, ...]


class CollectionEvidenceAdapter:
    """Map collected facts to evidence without interpreting table health."""

    def build(self, context) -> CollectionEvidenceBundle:
        records = (
            self._identity_schema(context),
            self._layout(context),
            self._properties(context),
            self._column_profile(context),
            self._workload(context),
        )
        coverage = tuple(
            CoverageEntry(record.module_name, record.availability) for record in records
        )
        return CollectionEvidenceBundle(records, coverage)

    def _identity_schema(self, context) -> EvidenceRecord:
        metadata = context.metadata
        columns = metadata.get("columns") or []
        available = Availability(AvailabilityState.COMPLETED) if columns else Availability(
            AvailabilityState.UNAVAILABLE, "Schema metadata could not be read."
        )
        return self._record(
            context, "identity_schema", available,
            f"Collected identity and {len(columns)} schema columns.",
            {"table_name": context.table_name, "catalog_name": context.catalog_name,
             "schema_name": context.schema_name, "collection_profile": metadata.get("collection_profile"),
             "collection_contract": metadata.get("collection_contract"), "columns": columns,
             "observation_state": "snapshot_pinned" if context.snapshot_id else "live_unpinned",
             "signals": context.signals},
        )

    def _layout(self, context) -> EvidenceRecord:
        metadata = context.metadata
        analysis = metadata.get("partition_analysis") or {}
        if analysis.get("error"):
            available = Availability(AvailabilityState.FAILED, str(analysis["error"]))
        elif self._missing_layout_measurement(context):
            available = Availability(AvailabilityState.UNAVAILABLE, "Required Iceberg layout metric is unavailable.")
        elif not metadata.get("files", {}).get("columns"):
            available = Availability(AvailabilityState.UNAVAILABLE, "Iceberg files metadata is unavailable.")
        else:
            available = Availability(AvailabilityState.COMPLETED)
        dimensions = context.baseline.get("dimensions") or {}
        payload = {
            "partition_analysis": analysis, "files_schema": metadata.get("files"),
            "partitions_schema": metadata.get("partitions"),
            "metrics": {key: dimensions.get(key) for key in (
                "row_count", "num_data_files", "total_data_file_bytes", "partition_count",
                "snapshot_count", "row_count_source", "row_count_is_exact", "unavailable_metrics",
            )},
            "signals": self._signals(context, _LAYOUT_SIGNALS),
        }
        return self._record(context, "iceberg_layout", available, "Collected Iceberg layout metadata.", payload)

    def _properties(self, context) -> EvidenceRecord:
        properties = context.metadata.get("table_properties") or {}
        if properties.get("error"):
            available = Availability(AvailabilityState.FAILED, str(properties["error"]))
        else:
            available = Availability(AvailabilityState.COMPLETED)
        classification = EvidenceClass.CONFIGURATION_RISK if properties.get("caps_warnings") else None
        return self._record(
            context, "table_properties", available, "Collected table property metadata.",
            {"table_properties": properties, "signals": self._signals(context, _PROPERTY_SIGNALS)},
            classification,
        )

    def _column_profile(self, context) -> EvidenceRecord:
        analysis = context.metadata.get("column_analysis") or {}
        status = analysis.get("status")
        if status == "not_collected_in_fast_profile":
            available = Availability(AvailabilityState.SKIPPED, "Fast collection does not profile base-table columns.")
        elif status == "pending_full_profile":
            available = Availability(AvailabilityState.SKIPPED, "Full column profile is running.")
        elif status == "partial":
            failed = int(analysis.get("total_columns_failed", 0))
            available = Availability(AvailabilityState.FAILED, f"Column profile is partial; {failed} column(s) failed.")
        elif status == "completed":
            completed = int(analysis.get("total_columns_analyzed", 0))
            available = Availability(AvailabilityState.COMPLETED) if completed else Availability(
                AvailabilityState.SKIPPED, "No rows were available for primitive-column profiling."
            )
        else:
            available = Availability(AvailabilityState.FAILED, str(analysis.get("error") or "Column profile failed."))
        return self._record(
            context, "column_profile", available, "Collected deterministic column profile.",
            {"column_analysis": analysis},
            EvidenceClass.NOT_ASSESSED if not available.is_available else None,
        )

    def column_profile_record(self, context) -> EvidenceRecord:
        """Expose the column-profile record for an enrichment revision."""
        return self._column_profile(context)

    def _workload(self, context) -> EvidenceRecord:
        patterns = context.metadata.get("query_patterns")
        available = Availability(AvailabilityState.COMPLETED) if patterns else Availability(
            AvailabilityState.UNAVAILABLE, "Query workload metadata is unavailable."
        )
        return self._record(
            context, "workload", available, "Collected query workload metadata." if patterns else "No workload metadata was collected.",
            {"query_patterns": patterns or {}, "signals": self._signals(context, _WORKLOAD_SIGNALS)},
        )

    @staticmethod
    def _signals(context, names: set[str]) -> list[dict[str, Any]]:
        return [signal for signal in context.signals if signal.get("name") in names]

    @staticmethod
    def _missing_layout_measurement(context) -> bool:
        for signal in context.signals:
            if signal.get("name") != "measurement_unavailable":
                continue
            missing = signal.get("metrics", {}).get("unavailable_metrics") or []
            if {"data_file_stats", "partition_stats"}.intersection(missing):
                return True
        return False

    @staticmethod
    def _record(context, module: str, availability: Availability, summary: str,
                payload: dict[str, Any], classification: EvidenceClass | None = None) -> EvidenceRecord:
        return EvidenceRecord(
            module_name=module, classification=classification or (
                EvidenceClass.VERIFIED_FACT if availability.is_available else EvidenceClass.NOT_ASSESSED
            ), availability=availability, summary=summary, payload=payload,
            provenance=EvidenceProvenance(source="deterministic_collection", snapshot_id=context.snapshot_id),
        )


def persist_collection_evidence(db, investigation_id: int, bundle: CollectionEvidenceBundle) -> tuple[str, ...]:
    """Persist collection facts, then attach their generated IDs to coverage."""
    evidence_ids: list[str] = []
    for record, coverage in zip(bundle.records, bundle.coverage):
        record_id = db.record_evidence(investigation_id, record)
        evidence_id = f"evidence:{record_id}"
        db.record_coverage(
            investigation_id,
            CoverageEntry(coverage.module_name, coverage.availability, (evidence_id,)),
        )
        evidence_ids.append(evidence_id)
    return tuple(evidence_ids)


def persist_column_profile_evidence(db, investigation_id: int, context) -> str:
    """Append completed full-profile evidence and advance its coverage entry."""
    record = CollectionEvidenceAdapter().column_profile_record(context)
    evidence_id = f"evidence:{db.record_evidence(investigation_id, record)}"
    db.record_coverage(
        investigation_id,
        CoverageEntry(record.module_name, record.availability, (evidence_id,)),
    )
    return evidence_id
