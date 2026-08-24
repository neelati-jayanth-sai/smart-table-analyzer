"""Test parallel investigation flow with mock LLM."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import init_investigation_db as init_db
from src.connectors import MockLLMAdapter
from src.database import InvestigationDb
from src.database.knowledge_store import KnowledgeStore
from src.investigator import Investigator
from src.query import QueryWorkbench, create_investigation_hooks


class FakeRow:
    def __init__(self, data: dict):
        self._data = data

    def asDict(self, recursive: bool = True) -> dict:
        return self._data

    def __getitem__(self, key: str | int):
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]


class FakeField:
    def __init__(self, name: str, data_type: str):
        self.name = name
        self.dataType = data_type


class FakeSchema:
    fields = [FakeField("count", "long")]


class FakeDf:
    def __init__(self, rows: list | None = None):
        self._rows = rows or []

    def limit(self, n: int):
        return FakeDf(self._rows[:n])

    def collect(self):
        return self._rows

    def count(self):
        return len(self._rows)

    @property
    def schema(self):
        return FakeSchema()


class FakeSpark:
    def sql(self, query: str):
        q = query.upper()
        if "DESCRIBE" in q:
            return FakeDf([FakeRow({"col_name": "id", "data_type": "string", "comment": ""})])
        if ".FILES" in q:
            return FakeDf([FakeRow({"content": 0, "file_path": "f", "file_size_in_bytes": 100, "record_count": 1})])
        if ".PARTITIONS" in q or ".HISTORY" in q or ".SNAPSHOTS" in q:
            return FakeDf([FakeRow({"value": "sample"})])
        if "COUNT" in q:
            return FakeDf([FakeRow({"count": 100})])
        return FakeDf([FakeRow({"value": "sample"})])


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = repo_root / "data" / "graph_test.db"
    db_path.unlink(missing_ok=True)

    db = InvestigationDb(db_path)
    entries = init_db.scan_knowledge_entries(repo_root)
    if entries:
        init_db.seed_knowledge_index(db_path, entries)

    knowledge = KnowledgeStore(db_path, repo_root=repo_root)

    inv_id = db.create_investigation(
        run_id=str(uuid.uuid4()),
        table_name="eds_it_dev.elh_comn.test_table",
        catalog_name="eds_it_dev",
        schema_name="elh_comn",
        max_checks=2,
    )

    print(f"Created investigation {inv_id}")

    hooks = create_investigation_hooks(["eds_it_dev"], ["elh_comn"])
    workbench = QueryWorkbench(FakeSpark(), hooks=hooks, timeout_seconds=1)

    # Parallel path: plan_checks uses the coverage sequence (no LLM decide calls).
    # Each check runs: knowledge tool calls → SQL generate → analyze.
    # With max_checks=2: check 0 = table_properties, check 1 = column_analysis.
    # MockLLMAdapter serves responses round-robin across threads; supply enough
    # for both checks interleaved: 3 responses per check × 2 checks = 6 minimum.
    responses = [
        # check 0 (table_properties) — knowledge phase
        {"content": "", "tool_calls": [{"name": "list_knowledge", "arguments": {"source": "iceberg"}}]},
        {"content": "", "tool_calls": [{"name": "fetch_knowledge", "arguments": {"source": "iceberg", "topic_path": "file-sizing-best-practices"}}]},
        # check 0 — generate SQL
        {"content": '{"sql": "SELECT COUNT(*) FROM eds_it_dev.elh_comn.test_table", "intent": "Count rows"}'},
        # check 0 — analyze: LLM asks for one extra query before answering,
        # exercising the AnalystToolRunner tool-calling loop end-to-end.
        {"content": "", "tool_calls": [{"name": "run_query", "arguments": {
            "sql": "SELECT COUNT(*) FROM eds_it_dev.elh_comn.test_table",
            "reason": "Confirm row count before finalizing"}}]},
        {"content": '{"verdict": "found", "exact_result": "Table has 100 rows", "rationale": "Row count is small", "evidence_ids": ["trail:0"], "recommendation": "Do nothing"}'},
        # check 0 — critic
        {"content": '{"verdict": "found", "exact_result": "Table has 100 rows", "rationale": "Row count is small but well-justified", "evidence_ids": ["trail:0"], "recommendation": "Do nothing", "actionable_sql": null}'},
        # check 1 (column_analysis) — knowledge phase
        {"content": "", "tool_calls": [{"name": "list_knowledge", "arguments": {"source": "iceberg"}}]},
        {"content": "", "tool_calls": [{"name": "fetch_knowledge", "arguments": {"source": "iceberg", "topic_path": "partition-transforms"}}]},
        # check 1 — generate SQL
        {"content": '{"sql": "SELECT COUNT(*) FROM eds_it_dev.elh_comn.test_table", "intent": "Count columns"}'},
        # check 1 — analyze
        {"content": '{"verdict": "not_found", "exact_result": "No partition column detected", "rationale": "Schema does not show partition", "evidence_ids": ["trail:1"], "recommendation": "Add partition"}'},
        # check 1 — critic
        {"content": '{"verdict": "not_found", "exact_result": "No partition column detected", "rationale": "Schema missing partition and justified", "evidence_ids": ["trail:1"], "recommendation": "Add partition", "actionable_sql": null}'},
    ]

    llm = MockLLMAdapter(responses)

    # max_workers=1 ensures serial execution so mock LLM responses arrive in order.
    investigator = Investigator(
        llm=llm,
        workbench=workbench,
        knowledge_retrieval=knowledge,
        db=db,
        db_path=db_path,
        max_checks=2,
        max_workers=1,
    )

    result = investigator.run_investigation(
        inv_id,
        table_name="eds_it_dev.elh_comn.test_table",
        baseline_score={
            "overall": 42.0,
            "dimensions": {"file_size": 30.0, "partition_aware": 45.0},
        },
    )

    print(f"Investigation status: {result.status}")
    print(f"Checks completed: {result.checks_completed}")
    print(f"Findings: {len(result.findings)}")

    assert result.checks_completed == 2, f"Expected 2 checks, got {result.checks_completed}"
    assert len(result.findings) == 2, f"Expected 2 findings, got {len(result.findings)}"

    for finding in result.findings:
        print(f"\nCheck {finding['check_num']}: {finding['question']}")
        print(f"  Verdict: {finding['verdict']}")
        print(f"  Evidence: {finding['evidence_ids']}")

    refs = db.get_knowledge_references(inv_id)
    print(f"\nKnowledge references stored: {len(refs)}")
    for ref in refs:
        print(f"  {ref['source']}/{ref['topic_path']}@{ref['version']}")
    assert len(refs) > 0, "Expected knowledge references to be recorded"

    print("\nGraph flow test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
