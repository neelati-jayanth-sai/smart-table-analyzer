"""Collection facts persist as typed evidence before LLM investigation."""

from __future__ import annotations

from src.analyzer import LegacyAnalyzer, SmartTableAnalyzer
from src.database import InvestigationDb, KnowledgeStore
from src.evidence import (
    AvailabilityState,
    CollectionEvidenceAdapter,
    persist_collection_evidence,
)
from src.metadata import MetadataCollectionProfile

from tests.mocks import MockSpark, SCENARIOS, ScriptedLLM


def test_fast_collection_records_a_skipped_column_profile_with_coverage_id(tmp_path):
    table = SCENARIOS["healthy"]()
    context = LegacyAnalyzer(MockSpark(table)).collect(table.name, "cat", "sch", "snapshot-1")
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-fast", table.name, "cat", "sch")

    ids = persist_collection_evidence(
        db, investigation_id, CollectionEvidenceAdapter().build(context)
    )
    records = {record.module_name: record for record in db.list_evidence(investigation_id)}
    coverage = {entry.module_name: entry for entry in db.get_coverage_ledger(investigation_id).entries}

    assert len(ids) == 5
    assert set(records) == {
        "identity_schema", "iceberg_layout", "table_properties", "column_profile", "workload"
    }
    assert records["identity_schema"].payload["observation_state"] == "snapshot_pinned"
    assert records["column_profile"].availability.state is AvailabilityState.SKIPPED
    assert "Fast collection" in (records["column_profile"].availability.reason or "")
    assert coverage["column_profile"].evidence_ids == (records["column_profile"].evidence_id,)


def test_deep_partial_profile_retains_failure_reason_and_evidence_id(tmp_path):
    table = SCENARIOS["healthy"]()
    context = LegacyAnalyzer(
        MockSpark(table, fail_on=r"`order_id`"), MetadataCollectionProfile.from_name("deep")
    ).collect(table.name)
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-deep", table.name, "cat", "sch")

    persist_collection_evidence(db, investigation_id, CollectionEvidenceAdapter().build(context))
    profile = next(record for record in db.list_evidence(investigation_id) if record.module_name == "column_profile")
    ledger = db.get_coverage_ledger(investigation_id)
    entry = next(item for item in ledger.entries if item.module_name == "column_profile")

    assert profile.payload["column_analysis"]["status"] == "partial"
    assert profile.availability.state is AvailabilityState.FAILED
    assert "partial" in (profile.availability.reason or "").lower()
    assert entry.evidence_ids == (profile.evidence_id,)


def test_deep_completed_profile_is_available_evidence(tmp_path):
    table = SCENARIOS["healthy"]()
    context = LegacyAnalyzer(
        MockSpark(table), MetadataCollectionProfile.from_name("deep")
    ).collect(table.name)
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-deep-complete", table.name, "cat", "sch")

    persist_collection_evidence(db, investigation_id, CollectionEvidenceAdapter().build(context))
    profile = next(record for record in db.list_evidence(investigation_id) if record.module_name == "column_profile")

    assert profile.availability.state is AvailabilityState.COMPLETED
    assert profile.evidence_id is not None


def test_pipeline_persists_collection_evidence_before_running_investigation(tmp_path):
    table = SCENARIOS["healthy"]()
    spark = MockSpark(table)
    db_path = tmp_path / "investigation.db"
    db = InvestigationDb(db_path)
    analyzer = SmartTableAnalyzer(
        spark, db, ScriptedLLM(table=table.name), KnowledgeStore(db_path, repo_root=tmp_path), max_checks=1
    )

    outcome = analyzer.analyze(table.name, "cat", "sch")

    records = db.list_evidence(outcome.investigation_id)
    assert len(records) == 5
    assert [record.module_name for record in records] == [
        "identity_schema", "iceberg_layout", "table_properties", "column_profile", "workload"
    ]
