"""Contract tests for Analyst access to persisted investigation evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evidence import Availability, AvailabilityState, EvidenceClass, EvidenceProvenance, EvidenceRecord
from src.investigator.executors.analyst_tools import AnalystToolRunner


def _record(record_id: int, module: str = "layout") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=f"evidence:{record_id}", module_name=module,
        classification=EvidenceClass.VERIFIED_FACT,
        availability=Availability(AvailabilityState.COMPLETED), summary="Measured file layout.",
        payload={"file_count": 12, "small_file_count": 2},
        provenance=EvidenceProvenance(source="iceberg.files", snapshot_id="snap-7"),
        confidence=0.92,
    )


class FakeDatabase:
    def __init__(self, evidence_by_investigation: dict[int, list[EvidenceRecord]]):
        self.evidence_by_investigation = evidence_by_investigation
        self.read_ids: list[int] = []

    def list_evidence(self, investigation_id: int) -> list[EvidenceRecord]:
        self.read_ids.append(investigation_id)
        return self.evidence_by_investigation.get(investigation_id, [])


class FakeLlm:
    def __init__(self, responses: list[dict]):
        self.responses = responses
        self.calls: list[dict] = []

    def generate(self, messages, tools=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        return self.responses.pop(0)


class UnusedWorkbench:
    def execute_query(self, sql):
        raise AssertionError(f"Evidence access must not run SQL: {sql}")


def _state() -> dict:
    return {"investigation_id": 7, "check_count": 3, "table_name": "catalog.schema.table"}


def _tool_messages(llm: FakeLlm) -> list[dict]:
    result = []
    for call in llm.calls:
        message = call["messages"][-1]
        content = message["content"]
        if message["role"] == "user" and isinstance(content, str) and content.startswith('{"tool"'):
            result.append(json.loads(content))
    return result


def test_analyst_lists_then_fetches_scoped_evidence_with_payload_and_provenance():
    llm = FakeLlm([
        {"tool_calls": [{"name": "list_evidence", "arguments": {"limit": 1}}]},
        {"tool_calls": [{"name": "fetch_evidence", "arguments": {"evidence_id": "evidence:4"}}]},
        {"content": '{"verdict":"found"}'},
    ])
    db = FakeDatabase({7: [_record(4)], 8: [_record(9, "other_investigation")]})

    result = AnalystToolRunner(llm, UnusedWorkbench(), db).run("analyse", _state())

    assert result["content"] == '{"verdict":"found"}'
    assert {tool["function"]["name"] for tool in llm.calls[0]["tools"]} == {
        "run_query", "list_evidence", "fetch_evidence"
    }
    messages = _tool_messages(llm)
    assert messages[0]["evidence"] == [{
        "evidence_id": "evidence:4", "module_name": "layout",
        "classification": "verified_fact", "availability": "completed",
        "summary": "Measured file layout.", "confidence": 0.92, "exploratory": False,
    }]
    assert messages[1]["payload"] == {"file_count": 12, "small_file_count": 2}
    assert messages[1]["provenance"] == {
        "source": "iceberg.files", "snapshot_id": "snap-7", "query_text": None,
        "query_parameters": {}, "observed_at": None,
    }
    assert db.read_ids == [7, 7]


def test_analyst_cannot_fetch_an_evidence_id_from_another_investigation():
    llm = FakeLlm([
        {"tool_calls": [{"name": "fetch_evidence", "arguments": {"evidence_id": "evidence:9"}}]},
        {"content": "final"},
    ])
    db = FakeDatabase({7: [_record(4)], 8: [_record(9)]})

    AnalystToolRunner(llm, UnusedWorkbench(), db).run("analyse", _state())

    messages = _tool_messages(llm)
    assert messages[0] == {
        "tool": "fetch_evidence", "error": "Evidence was not found in this investigation."
    }
    assert "evidence:9" not in json.dumps(messages)


def test_evidence_summary_limit_is_bounded_and_read_only():
    llm = FakeLlm([
        {"tool_calls": [{"name": "list_evidence", "arguments": {"limit": 1000}}]},
        {"content": "final"},
    ])
    db = FakeDatabase({7: [_record(index) for index in range(30)]})

    AnalystToolRunner(llm, UnusedWorkbench(), db).run("analyse", _state())

    summary = _tool_messages(llm)[0]
    assert summary["total_matching"] == 30
    assert summary["returned_count"] == 20
    assert len(summary["evidence"]) == 20
