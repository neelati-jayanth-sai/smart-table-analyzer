"""Test baseline scoring for empty tables."""

from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._investigation_cli import compute_baseline


class FakeRow:
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key: str | int):
        if isinstance(key, int):
            return list(self._data.values())[key]
        return self._data[key]


class FakeDf:
    def __init__(self, first_value):
        self._first_value = first_value

    def first(self):
        if self._first_value is None:
            return None
        return FakeRow({"count": self._first_value})


class EmptySpark:
    def sql(self, query: str):
        q = query.upper()
        if "COUNT(*)" in q:
            return FakeDf(0)
        return FakeDf(None)


def test_empty_table_baseline() -> None:
    baseline = compute_baseline(EmptySpark(), "eds_it_dev.elh_comn.empty_table")
    dims = baseline["dimensions"]
    assert dims["row_count"] == 0, f"expected row_count 0, got {dims['row_count']}"
    assert dims["num_data_files"] == 0, f"expected num_data_files 0, got {dims['num_data_files']}"
    assert dims["is_empty"] is True, f"expected is_empty True, got {dims['is_empty']}"
    print("✅ Empty table baseline has is_empty=True")


class NonEmptySpark:
    def sql(self, query: str):
        q = query.upper()
        if ".FILES" in q and "COUNT(*)" in q:
            return FakeDf(5)
        if "COUNT(*)" in q:
            return FakeDf(100)
        return FakeDf(None)


def test_non_empty_table_baseline() -> None:
    baseline = compute_baseline(NonEmptySpark(), "eds_it_dev.elh_comn.nonempty_table")
    dims = baseline["dimensions"]
    assert dims["row_count"] == 100
    assert dims["num_data_files"] == 5
    assert dims["is_empty"] is False
    print("✅ Non-empty table baseline has is_empty=False")


def main() -> int:
    test_empty_table_baseline()
    test_non_empty_table_baseline()
    print("\n✅ Empty baseline tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
