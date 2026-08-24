"""A Spark Connect stand-in backed by MockIcebergTable data.

Answers real SQL through `tests.mocks.sql`, so evidence returned to the
Investigator is derived from the scenario rather than hardcoded. Also records
every query and table read, which is how the "read Iceberg metadata once" rule
is asserted.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .iceberg import MockIcebergTable
from .sql import TableStats, UnsupportedQuery, evaluate

_SHOW_TBLPROPERTIES = re.compile(r"^\s*SHOW\s+TBLPROPERTIES\s+(?P<table>[\w.`]+)\s*$", re.IGNORECASE)
_DESCRIBE = re.compile(r"^\s*DESCRIBE\s+(?:EXTENDED\s+|FORMATTED\s+)?(?P<table>[\w.`]+)\s*$", re.IGNORECASE)


class MockRow:
    def __init__(self, values: dict[str, Any]):
        self._values = dict(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._values.values())[key]
        return self._values[key]

    def get(self, key, default=None):
        return self._values.get(key, default)

    def asDict(self, recursive: bool = False) -> dict[str, Any]:
        return dict(self._values)

    def __repr__(self) -> str:
        return f"MockRow({self._values})"


class MockField:
    def __init__(self, name: str, type_name: str):
        self.name = name
        self._type = type_name

    @property
    def dataType(self):
        return self

    def simpleString(self) -> str:
        return self._type

    def __str__(self) -> str:
        return self._type


class MockSchema:
    def __init__(self, columns: list[tuple[str, str]]):
        self.fields = [MockField(name, type_name) for name, type_name in columns]


class MockDataFrame:
    def __init__(self, rows: list[dict[str, Any]], columns: list[tuple[str, str]]):
        self._rows = rows
        self.schema = MockSchema(columns)

    def first(self) -> MockRow | None:
        return MockRow(self._rows[0]) if self._rows else None

    def collect(self) -> list[MockRow]:
        return [MockRow(row) for row in self._rows]

    def limit(self, n: int) -> "MockDataFrame":
        return MockDataFrame(self._rows[:n], [(f.name, str(f)) for f in self.schema.fields])

    def count(self) -> int:
        return len(self._rows)


class MockSpark:
    """Serves one or more MockIcebergTables.

    `fail_on` is a regex; matching queries raise `failure`, simulating a
    Spark-side error. `on_query` observes every statement executed.
    """

    def __init__(
        self,
        *tables: MockIcebergTable,
        fail_on: str | None = None,
        failure: Exception | None = None,
        on_query: Callable[[str], None] | None = None,
    ):
        self.tables = {table.name: table for table in tables}
        self.fail_on = re.compile(fail_on, re.IGNORECASE) if fail_on else None
        self.failure = failure or RuntimeError(
            "AnalysisException: cannot resolve column in simulated Spark failure"
        )
        self.on_query = on_query
        self.queries: list[str] = []
        self.table_reads: list[str] = []
        self.stopped = False

    # ---------------------------------------------------------------- lookup

    def _resolve(self, reference: str) -> tuple[MockIcebergTable, str | None]:
        """Split `cat.sch.tbl[.files]` into its table and metadata suffix."""
        name = reference.replace("`", "")
        if name in self.tables:
            return self.tables[name], None
        base, _, suffix = name.rpartition(".")
        if base in self.tables and suffix in ("files", "partitions", "snapshots", "history"):
            return self.tables[base], suffix
        raise RuntimeError(f"Table or view not found: {name}")

    def _rows_and_columns(self, reference: str) -> tuple[list[dict], list[tuple[str, str]]]:
        table, suffix = self._resolve(reference)
        if suffix:
            return table.metadata_rows(suffix), table.metadata_columns(suffix)
        return table.rows, table.columns

    # ------------------------------------------------------------- execution

    def sql(self, query: str) -> MockDataFrame:
        self.queries.append(query)
        if self.on_query:
            self.on_query(query)
        if self.fail_on and self.fail_on.search(query):
            raise self.failure

        show = _SHOW_TBLPROPERTIES.match(query)
        if show:
            table, _ = self._resolve(show.group("table"))
            return MockDataFrame(
                [{"key": k, "value": v} for k, v in table.properties.items()],
                [("key", "string"), ("value", "string")],
            )

        describe = _DESCRIBE.match(query)
        if describe:
            return self._describe(describe.group("table"))

        return self._select(query)

    def _describe(self, reference: str) -> MockDataFrame:
        table, suffix = self._resolve(reference)
        columns = table.metadata_columns(suffix) if suffix else table.columns
        rows = [{"col_name": name, "data_type": type_name, "comment": None}
                for name, type_name in columns]
        if not suffix and table.partition_columns:
            rows.append(
                {
                    "col_name": "Partition Columns",
                    "data_type": f"[{', '.join(table.partition_columns)}]",
                    "comment": None,
                }
            )
        return MockDataFrame(
            rows, [("col_name", "string"), ("data_type", "string"), ("comment", "string")]
        )

    def _select(self, query: str) -> MockDataFrame:
        reference = _from_table(query)
        table, suffix = self._resolve(reference)
        rows, _ = self._rows_and_columns(reference)

        # Metadata tables are fully materialised, so they need no declared
        # totals; the base table's row count and cardinality come from
        # Iceberg metadata rather than from the sample rows.
        stats = None if suffix else TableStats(table.row_count, table.column_stats)

        result = evaluate(query, rows, stats)
        columns = [(key, _infer_type(value)) for key, value in (result[0] if result else {}).items()]
        return MockDataFrame(result, columns)

    # --------------------------------------------------------------- catalog

    def table(self, name: str) -> MockDataFrame:
        self.table_reads.append(name)
        rows, columns = self._rows_and_columns(name)
        return MockDataFrame(rows, columns)

    def stop(self) -> None:
        self.stopped = True


def _from_table(query: str) -> str:
    match = re.search(r"\bFROM\s+([\w.`]+)", query, re.IGNORECASE)
    if not match:
        raise UnsupportedQuery(query)
    return match.group(1)


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "bigint"
    if isinstance(value, float):
        return "double"
    if isinstance(value, dict):
        return "struct"
    return "string"
