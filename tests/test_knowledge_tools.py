"""Tests for knowledge source validation (CU-8).

CU-8: _normalize_source must not silently map unknown source names to 'iceberg'.
An unrecognised source name must return an empty source so callers skip it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.investigator.knowledge import KnowledgeToolRunner


class _StubDeps:
    """Minimal stubs so KnowledgeToolRunner can be instantiated without real deps."""

    class FakeLLM:
        def generate(self, *a, **kw):
            return {}

    class FakeStore:
        def list(self, *a, **kw):
            return []
        def fetch(self, *a, **kw):
            return {}

    class FakeDb:
        def record_knowledge_fetch(self, *a, **kw):
            pass

    class FakeEngine:
        def render(self, *a, **kw):
            from src.context import PromptContext
            return PromptContext(table_name="t")


def _runner() -> KnowledgeToolRunner:
    s = _StubDeps()
    return KnowledgeToolRunner(
        llm=s.FakeLLM(),
        knowledge_store=s.FakeStore(),
        db=s.FakeDb(),
        context_engine=s.FakeEngine(),
    )


class TestCU8KnowledgeSourceNormalization:
    """CU-8: unknown source names must not silently resolve to 'iceberg'."""

    def test_valid_sources_pass_through(self):
        """Known source names are returned unchanged."""
        r = _runner()
        for source in ("iceberg", "iomete", "runbooks"):
            result_source, prefix = r._normalize_source(source)
            assert result_source == source, f"Expected '{source}', got '{result_source}'"
            assert prefix is None

    def test_unknown_source_returns_empty(self):
        """An unrecognised source name must return empty string, not 'iceberg'."""
        r = _runner()
        result_source, prefix = r._normalize_source("runbooks_v2")
        assert result_source == "", (
            f"Unknown source 'runbooks_v2' silently mapped to '{result_source}' — RC-11: "
            "callers receive wrong tree content without any error signal"
        )

    def test_hallucinated_source_returns_empty(self):
        """Common LLM hallucinations of source names must not misdirect."""
        r = _runner()
        for bad_name in ("Iceberg", "ICEBERG", "runbook", "general", "default"):
            result_source, _ = r._normalize_source(bad_name)
            if bad_name.lower() in ("iceberg", "iomete", "runbooks"):
                continue  # case-normalised valid name — allowed
            assert result_source == "", (
                f"Hallucinated source '{bad_name}' should produce empty source, got '{result_source}'"
            )

    def test_none_source_returns_empty(self):
        """None input already returns empty — must not regress."""
        r = _runner()
        result_source, prefix = r._normalize_source(None)
        assert result_source == ""
        assert prefix is None

    def test_empty_string_source_returns_empty(self):
        r = _runner()
        result_source, _ = r._normalize_source("")
        assert result_source == ""

if __name__ == "__main__":
    t = TestCU8KnowledgeSourceNormalization()

    # Structural tests (should pass before and after fix)
    structural = [
        t.test_valid_sources_pass_through,
        t.test_none_source_returns_empty,
        t.test_empty_string_source_returns_empty,
    ]
    # Tests that capture the bug (fail before fix, pass after)
    bug_tests = [
        t.test_unknown_source_returns_empty,
        t.test_hallucinated_source_returns_empty,
    ]

    print("=== Structural tests (must always pass) ===")
    s_failed = 0
    for test in structural:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as e:
            print(f"FAIL  {test.__name__}: {e}")
            s_failed += 1

    print("\n=== Bug tests (FAIL before fix, PASS after) ===")
    b_failed = 0
    for test in bug_tests:
        try:
            test()
            print(f"PASS  {test.__name__} (CU-8 already applied?)")
        except AssertionError as e:
            print(f"FAIL  {test.__name__} (expected — bug confirmed): {e}")
            b_failed += 1

    sys.exit(s_failed)
