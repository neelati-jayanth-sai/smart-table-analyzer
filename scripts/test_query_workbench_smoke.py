"""Smoke test for query workbench (no Spark required)."""

from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.query import QueryWorkbench, create_investigation_hooks


def _run_hook_tests() -> int:
    hooks = create_investigation_hooks(["eds_it_dev"], ["elh_comn"])
    wb = QueryWorkbench(_FakeSpark(), hooks=hooks, timeout_seconds=1)

    cases = [
        ("SELECT * FROM eds_it_dev.elh_comn.table", True, "valid read-only"),
        ("DROP TABLE eds_it_dev.elh_comn.table", False, "blocked DDL"),
        ("SELECT 1; DROP TABLE x", False, "blocked multi-statement"),
        ("LOAD DATA FROM 'file://x'", False, "blocked file access"),
        ("SELECT * FROM other_catalog.schema.table", False, "blocked schema"),
    ]

    for query, should_succeed, description in cases:
        ok, hook_result, _ = wb.validate_query(query)
        if ok != should_succeed:
            print(f"\u274c {description}: expected ok={should_succeed}, got {ok}")
            print(f"   Query: {query}")
            print(f"   Error: {hook_result.error_message}")
            return 1
        status = "passed" if ok else f"blocked by {hook_result.hook_name}"
        print(f"\u2705 {description}: {status}")

    return 0


def _run_snapshot_pinning_tests() -> int:
    hooks = create_investigation_hooks(["eds_it_dev"], ["elh_comn"])
    table_name = "eds_it_dev.elh_comn.table"
    snapshot_id = "snap-123456"

    wb = QueryWorkbench(
        _FakeSpark(),
        hooks=hooks,
        timeout_seconds=1,
        table_name=table_name,
        snapshot_id=snapshot_id,
    )

    for suffix in ("", ".files", ".partitions", ".history", ".snapshots"):
        query = f"SELECT * FROM {table_name}{suffix}"
        ok, _, rewritten = wb.validate_query(query)
        if not ok:
            print(f"\u274c Snapshot pinning blocked valid query: {query}")
            return 1
        if snapshot_id not in rewritten or "VERSION AS OF" not in rewritten:
            print(f"\u274c Snapshot pinning missing for {query}: {rewritten}")
            return 1
        print(f"\u2705 Snapshot pinning applied for {table_name}{suffix}: {rewritten}")

    wb_no_pin = QueryWorkbench(_FakeSpark(), hooks=hooks, timeout_seconds=1, table_name=table_name)
    ok, _, rewritten = wb_no_pin.validate_query(f"SELECT * FROM {table_name}")
    if "VERSION AS OF" in rewritten:
        print(f"\u274c Snapshot pinning applied without snapshot_id: {rewritten}")
        return 1
    print(f"\u2705 Snapshot pinning skipped when no snapshot configured")

    return 0


def _run_double_execution_tests() -> int:
    hooks = create_investigation_hooks(["eds_it_dev"], ["elh_comn"])
    spark = _CountingSpark()

    wb = QueryWorkbench(spark, hooks=hooks, timeout_seconds=1)
    result = wb.execute_query("SELECT * FROM eds_it_dev.elh_comn.table")
    if not result.success:
        print(f"\u274c Default execution failed: {result.error}")
        return 1
    if _CountingDf.count_calls != 0:
        print(f"\u274c Default execution called count() {_CountingDf.count_calls} times")
        return 1
    print("\u2705 Default execution avoids double count()")

    _CountingDf.count_calls = 0
    wb_full = QueryWorkbench(spark, hooks=hooks, timeout_seconds=1, full_count=True)
    result = wb_full.execute_query("SELECT * FROM eds_it_dev.elh_comn.table")
    if not result.success:
        print(f"\u274c Full-count execution failed: {result.error}")
        return 1
    if _CountingDf.count_calls != 1:
        print(f"\u274c Full-count execution called count() {_CountingDf.count_calls} times")
        return 1
    print("\u2705 Full-count execution calls count() once")

    return 0


class _FakeSpark:
    def sql(self, query: str):
        class FakeDf:
            def limit(self, n: int):
                return self

            def collect(self):
                return []

            @property
            def schema(self):
                return type("Schema", (), {"fields": []})()

        return FakeDf()


class _CountingDf:
    count_calls = 0

    def limit(self, n: int):
        return self

    def collect(self):
        return []

    @property
    def schema(self):
        return type("Schema", (), {"fields": []})()

    def count(self):
        _CountingDf.count_calls += 1
        return 0


class _CountingSpark:
    def sql(self, query: str):
        return _CountingDf()


def main() -> int:
    for test in (_run_hook_tests, _run_snapshot_pinning_tests, _run_double_execution_tests):
        if test() != 0:
            return 1

    print("\n\u2705 Query workbench smoke tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
