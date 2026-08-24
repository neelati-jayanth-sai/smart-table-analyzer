"""Tests for knowledge fetch scoping (knowledge over-fetching fix).

Root cause: fetch_relevant_knowledge overrides check_types_to_fetch for
check_count < 3, fetching for all 3 coverage types regardless of the
current check_type. This triples the number of knowledge fetches per check.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.investigator.executors import InvestigationNodes
from src.investigator.state import InvestigationState


def _make_nodes(search_results=None):
    """Build InvestigationNodes with fully stubbed dependencies."""
    llm = MagicMock()
    llm.generate.return_value = {"content": "", "tool_calls": []}

    knowledge_store = MagicMock()
    knowledge_store.list.return_value = []
    knowledge_store.fetch.return_value = {}

    db = MagicMock()
    db.record_knowledge_fetch.return_value = None

    context_engine = MagicMock()
    from src.context import PromptContext
    context_engine.render.return_value = PromptContext(table_name="test_table")

    nodes = InvestigationNodes(
        llm=llm,
        workbench=MagicMock(),
        knowledge_store=knowledge_store,
        db=db,
        context_engine=context_engine,
    )

    # Override retriever.search to return empty list (forces fallback path)
    nodes.retriever.search = MagicMock(return_value=search_results or [])
    return nodes


def _state(check_count=0, check_type="table_properties") -> InvestigationState:
    return {
        "investigation_id": 1,
        "table_name": "test_table",
        "baseline_score": {"overall": 70.0, "dimensions": {}, "weakest": []},
        "check_count": check_count,
        "max_checks": 5,
        "retry_count": 0,
        "max_retries": 3,
        "step_count": 0,
        "max_steps": 50,
        "status": "running",
        "findings": [],
        "table_metadata": None,
        "current_question": "Are there CAPS issues in table properties?",
        "current_check_type": check_type,
        "asked_questions": [],
        "knowledge_consulted": [],
    }


class TestKnowledgeScoping:

    def test_check0_calls_retriever_once_not_three_times(self):
        """For check 0 (table_properties), search must be called once, not 3×."""
        nodes = _make_nodes()
        nodes.fetch_relevant_knowledge(_state(check_count=0, check_type="table_properties"))
        call_count = nodes.retriever.search.call_count
        assert call_count == 1, (
            f"retriever.search called {call_count}× for check 0 — "
            "over-fetching: should be 1 (current check_type only)"
        )

    def test_check1_calls_retriever_once(self):
        """For check 1 (column_analysis), search must be called once."""
        nodes = _make_nodes()
        nodes.fetch_relevant_knowledge(_state(check_count=1, check_type="column_analysis"))
        assert nodes.retriever.search.call_count == 1

    def test_check2_calls_retriever_once(self):
        """For check 2 (partition_suggestions), search must be called once."""
        nodes = _make_nodes()
        nodes.fetch_relevant_knowledge(_state(check_count=2, check_type="partition_suggestions"))
        assert nodes.retriever.search.call_count == 1

    def test_search_called_with_current_check_type(self):
        """The retriever must be called with the current check_type, not all types."""
        nodes = _make_nodes()
        nodes.fetch_relevant_knowledge(_state(check_count=0, check_type="table_properties"))
        _, kwargs = nodes.retriever.search.call_args
        called_check_type = nodes.retriever.search.call_args[0][1] if nodes.retriever.search.call_args[0] else kwargs.get("check_type")
        assert called_check_type == "table_properties", (
            f"search called with check_type={called_check_type!r}, expected 'table_properties'"
        )

    def test_check_beyond_3_also_scoped_correctly(self):
        """Checks after the first 3 must also be scoped to current check_type."""
        nodes = _make_nodes()
        nodes.fetch_relevant_knowledge(_state(check_count=4, check_type="file_size"))
        assert nodes.retriever.search.call_count == 1


if __name__ == "__main__":
    t = TestKnowledgeScoping()
    tests = [
        t.test_check0_calls_retriever_once_not_three_times,
        t.test_check1_calls_retriever_once,
        t.test_check2_calls_retriever_once,
        t.test_search_called_with_current_check_type,
        t.test_check_beyond_3_also_scoped_correctly,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as e:
            print(f"FAIL  {test.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(failed)
