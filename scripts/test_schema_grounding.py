"""Unit tests for the schema grounding hook and resolver."""

from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.query import SchemaResolver, SqlGroundingHook


TABLE = "eds_it_dev.elh_comn.DISTI_SELL_THRU_F_test"

METADATA = {
    "table_name": TABLE,
    "columns": [
        {"name": "id", "type": "string"},
        {"name": "name", "type": "string"},
    ],
    "files": {
        "columns": [
            {"name": "content", "type": "int"},
            {"name": "file_path", "type": "string"},
            {"name": "file_size_in_bytes", "type": "long"},
        ],
    },
    "partitions": {
        "columns": [
            {"name": "partition", "type": "struct"},
            {"name": "row_count", "type": "long"},
        ],
    },
    "history": {"columns": [{"name": "made_current_at", "type": "timestamp"}]},
    "snapshots": {
        "columns": [
            {"name": "committed_at", "type": "timestamp"},
            {"name": "snapshot_id", "type": "long"},
        ],
    },
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_resolver() -> None:
    resolver = SchemaResolver(METADATA)
    _assert(resolver.base_table == TABLE, "base table name mismatch")
    _assert(resolver.available_columns(TABLE) == {"id", "name"}, "base columns mismatch")
    _assert(
        resolver.available_columns(f"{TABLE}.files") == {"content", "file_path", "file_size_in_bytes"},
        ".files columns mismatch",
    )
    _assert(
        resolver.available_columns(f"{TABLE}.partitions") == {"partition", "row_count"},
        ".partitions columns mismatch",
    )
    _assert(
        resolver.available_columns(f"{TABLE}.snapshots") == {"committed_at", "snapshot_id"},
        ".snapshots columns mismatch",
    )


def test_valid_base_columns() -> None:
    hook = SqlGroundingHook(schema_resolver=SchemaResolver(METADATA))
    result = hook.validate(f"SELECT id, name FROM {TABLE}")
    _assert(result.is_valid, f"valid base query rejected: {result.error_message}")


def test_invalid_partition_on_files() -> None:
    hook = SqlGroundingHook(schema_resolver=SchemaResolver(METADATA))
    result = hook.validate(f"SELECT partition FROM {TABLE}.files")
    _assert(not result.is_valid, "expected partition on .files to be rejected")
    _assert("Column 'partition' is not present in" in result.error_message, "missing column name in error")
    _assert(f"{TABLE}.files" in result.error_message, "missing table ref in error")
    _assert("content" in result.error_message, "missing available columns in error")


def test_valid_partition_on_partitions() -> None:
    hook = SqlGroundingHook(schema_resolver=SchemaResolver(METADATA))
    result = hook.validate(f"SELECT partition, row_count FROM {TABLE}.partitions")
    _assert(result.is_valid, f"valid .partitions query rejected: {result.error_message}")


def test_snapshots_columns() -> None:
    hook = SqlGroundingHook(schema_resolver=SchemaResolver(METADATA))
    _assert(hook.validate(f"SELECT committed_at FROM {TABLE}.snapshots").is_valid, "valid snapshot column rejected")
    result = hook.validate(f"SELECT no_such_column FROM {TABLE}.snapshots")
    _assert(not result.is_valid, "expected missing snapshot column to be rejected")


def test_function_and_alias() -> None:
    hook = SqlGroundingHook(schema_resolver=SchemaResolver(METADATA))
    _assert(
        hook.validate(f"SELECT count(1), sum(file_size_in_bytes) FROM {TABLE}.files").is_valid,
        "aggregate on .files rejected",
    )
    result = hook.validate(f"SELECT f.partition FROM {TABLE}.files f")
    _assert(not result.is_valid, "expected aliased partition on .files to be rejected")


def test_missing_metadata_is_tolerated() -> None:
    empty_resolver = SchemaResolver(None)
    _assert(empty_resolver.base_table is None, "resolver should not require metadata")
    hook = SqlGroundingHook(schema_resolver=empty_resolver)
    _assert(hook.validate(f"SELECT fake FROM {TABLE}.files").is_valid, "missing metadata should be tolerated")
    hook2 = SqlGroundingHook(table_name=TABLE, table_metadata={})
    _assert(hook2.validate(f"SELECT fake FROM {TABLE}").is_valid, "empty metadata should be tolerated")


def main() -> int:
    tests = [
        test_resolver,
        test_valid_base_columns,
        test_invalid_partition_on_files,
        test_valid_partition_on_partitions,
        test_snapshots_columns,
        test_function_and_alias,
        test_missing_metadata_is_tolerated,
    ]
    for test in tests:
        try:
            test()
            print(f"\u2705 {test.__name__}")
        except AssertionError as exc:
            print(f"\u274c {test.__name__}: {exc}")
            return 1
    print("\n\u2705 All schema grounding tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
