"""Evidence records and coverage ledger persistence contract."""

from __future__ import annotations

import sqlite3

from src.database import InvestigationDb
from src.evidence import (
    Availability,
    AvailabilityState,
    CoverageEntry,
    EvidenceClass,
    EvidenceProvenance,
    EvidenceRecord,
)
from src.models import Finding
from src.validation import ClaimValidator


def test_evidence_and_coverage_round_trip(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-1", "cat.sch.orders", "cat", "sch")
    record_id = db.record_evidence(
        investigation_id,
        EvidenceRecord(
            module_name="layout", classification=EvidenceClass.VERIFIED_FACT,
            availability=Availability(AvailabilityState.COMPLETED),
            summary="Measured partition distribution.", payload={"partition_count": 12},
            provenance=EvidenceProvenance(source="iceberg.files", snapshot_id="123"),
            confidence=0.95,
        ),
    )
    coverage_id = db.record_coverage(
        investigation_id,
        CoverageEntry(
            "layout", Availability(AvailabilityState.COMPLETED), (f"evidence:{record_id}",)
        ),
    )

    evidence = db.get_evidence(record_id)
    ledger = db.get_coverage_ledger(investigation_id)

    assert coverage_id > 0
    assert evidence is not None
    assert evidence.evidence_id == f"evidence:{record_id}"
    assert evidence.payload == {"partition_count": 12}
    assert evidence.provenance.snapshot_id == "123"
    assert ledger.completed_modules() == ("layout",)
    assert ledger.entries[0].evidence_ids == (f"evidence:{record_id}",)


def test_coverage_upsert_retains_one_current_outcome(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-2", "cat.sch.orders", "cat", "sch")
    unavailable = CoverageEntry(
        "workload", Availability(AvailabilityState.UNAVAILABLE, "Query logs are unavailable")
    )
    db.record_coverage(investigation_id, unavailable)
    db.record_coverage(
        investigation_id,
        CoverageEntry("workload", Availability(AvailabilityState.COMPLETED), ("evidence:2",)),
    )

    ledger = db.get_coverage_ledger(investigation_id)

    assert len(ledger.entries) == 1
    assert ledger.entries[0].availability.is_available
    assert ledger.entries[0].evidence_ids == ("evidence:2",)


def test_legacy_database_receives_evidence_tables_with_valid_foreign_keys(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """CREATE TABLE investigations (
        investigation_id INTEGER PRIMARY KEY, run_id TEXT UNIQUE NOT NULL, table_name TEXT NOT NULL,
        catalog_name TEXT NOT NULL, schema_name TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'aborted')),
        baseline_score_json TEXT, snapshot_id TEXT, max_checks INTEGER NOT NULL DEFAULT 50,
        current_check INTEGER NOT NULL DEFAULT 0, started_at TEXT NOT NULL, completed_at TEXT);
        CREATE TABLE investigation_findings (
        finding_id INTEGER PRIMARY KEY, investigation_id INTEGER NOT NULL, check_num INTEGER NOT NULL,
        question TEXT NOT NULL, exact_result TEXT NOT NULL, verdict TEXT NOT NULL,
        rationale TEXT NOT NULL, evidence_ids TEXT NOT NULL);"""
    )
    conn.close()

    db = InvestigationDb(db_path)

    with db._connect() as check:
        foreign_key = check.execute("PRAGMA foreign_key_list(evidence_records)").fetchone()
    assert foreign_key["table"] == "investigations"


def test_completed_deterministic_evidence_can_validate_a_finding(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-3", "cat.sch.orders", "cat", "sch")
    record_id = db.record_evidence(
        investigation_id,
        EvidenceRecord(
            module_name="iceberg_layout", classification=EvidenceClass.VERIFIED_FACT,
            availability=Availability(AvailabilityState.COMPLETED), summary="Measured layout.",
        ),
    )
    finding = Finding(
        check_num=0, question="Is layout evidence available?", exact_result="Yes.",
        verdict="found", rationale="The persisted deterministic layout measurement is available.",
        evidence_ids=[f"evidence:{record_id}"], validated=True,
    )

    result = ClaimValidator(db).validate(investigation_id, finding)

    assert result.valid


def test_skipped_or_foreign_deterministic_evidence_cannot_validate_a_finding(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-4", "cat.sch.orders", "cat", "sch")
    skipped_id = db.record_evidence(
        investigation_id,
        EvidenceRecord(
            module_name="column_profile", classification=EvidenceClass.NOT_ASSESSED,
            availability=Availability(AvailabilityState.SKIPPED, "Fast mode"), summary="Not collected.",
        ),
    )
    finding = Finding(
        check_num=0, question="Was the column profile measured?", exact_result="No.",
        verdict="found", rationale="The cited deterministic evidence was intentionally skipped.",
        evidence_ids=[f"evidence:{skipped_id}"], validated=True,
    )

    result = ClaimValidator(db).validate(investigation_id, finding)

    assert not result.valid
    assert "deterministic evidence" in result.errors[0]

    other_investigation = db.create_investigation("run-5", "cat.sch.other", "cat", "sch")
    foreign_id = db.record_evidence(
        other_investigation,
        EvidenceRecord(
            module_name="iceberg_layout", classification=EvidenceClass.VERIFIED_FACT,
            availability=Availability(AvailabilityState.COMPLETED), summary="Other table.",
        ),
    )
    foreign = Finding(
        check_num=1, question="Is foreign evidence valid?", exact_result="No.", verdict="found",
        rationale="Evidence records are scoped to their investigation before validation.",
        evidence_ids=[f"evidence:{foreign_id}"], validated=True,
    )

    foreign_result = ClaimValidator(db).validate(investigation_id, foreign)

    assert not foreign_result.valid
    assert foreign_result.missing_ids == [f"evidence:{foreign_id}"]
