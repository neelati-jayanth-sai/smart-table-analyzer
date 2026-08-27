"""Durable investigation timeline contract."""

from src.database import InvestigationDb, TimelineEvent


def test_timeline_events_round_trip_in_append_order(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-1", "cat.sch.orders", "cat", "sch")

    first_id = db.append_timeline_event(
        investigation_id,
        "table_identified",
        "I identified the table and pinned its snapshot.",
    )
    second_id = db.append_timeline_event(
        investigation_id,
        "finding",
        "I found a property naming risk.",
        status="confirmed",
        evidence_ids=["evidence:12"],
        confidence=0.9,
        details={"observed": "WRITE.TARGET-FILE-SIZE-BYTES"},
    )

    events = db.list_timeline_events(investigation_id)

    assert [event.event_id for event in events] == [first_id, second_id]
    assert isinstance(events[0], TimelineEvent)
    assert events[1].evidence_ids == ("evidence:12",)
    assert events[1].details["observed"] == "WRITE.TARGET-FILE-SIZE-BYTES"


def test_timeline_limit_returns_oldest_events(tmp_path):
    db = InvestigationDb(tmp_path / "investigation.db")
    investigation_id = db.create_investigation("run-2", "cat.sch.orders", "cat", "sch")
    for index in range(3):
        db.append_timeline_event(investigation_id, "progress", f"Step {index}")

    events = db.list_timeline_events(investigation_id, limit=2)

    assert [event.message for event in events] == ["Step 0", "Step 1"]
