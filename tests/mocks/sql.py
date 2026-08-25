"""A tiny read-only SQL evaluator over in-memory rows.

Enough of Spark SQL to answer the queries the analyzer and the Investigator
actually emit, so mock results are derived from the scenario's data rather than
hardcoded per test. Supported:

    SELECT <items> FROM <table> [WHERE <conds>] [GROUP BY <col>]
                               [ORDER BY <expr> [ASC|DESC]] [LIMIT <n>]

    items : COUNT(*) | COUNT([DISTINCT] col) | SUM|MIN|MAX|AVG(col)
          | COALESCE(<agg>, <n>) | COUNT(*) - COUNT(col) | col   [AS alias]
    conds : col <op> <literal> [AND ...]   op in = != <> > >= < <=

ponytail: no joins, subqueries, HAVING, or expressions beyond the above. If a
test needs one, extend this rather than hardcoding a canned result — the point
is that mock evidence stays consistent with mock metadata.
"""

from __future__ import annotations

import re
from typing import Any, Callable

_VERSION_AS_OF = re.compile(r"\s+VERSION\s+AS\s+OF\s+\d+", re.IGNORECASE)

_CLAUSES = re.compile(
    r"^\s*SELECT\s+(?P<items>.+?)"
    r"\s+FROM\s+(?P<table>[\w.`]+)"
    r"(?:\s+WHERE\s+(?P<where>.+?))?"
    r"(?:\s+GROUP\s+BY\s+(?P<group>[\w.]+))?"
    r"(?:\s+ORDER\s+BY\s+(?P<order>.+?))?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?\s*$",
    re.IGNORECASE | re.DOTALL,
)

_CONDITION = re.compile(r"^\s*(?P<col>[\w.]+)\s*(?P<op>!=|<>|>=|<=|=|>|<)\s*(?P<value>.+?)\s*$")

_COUNT_STAR_MINUS_COUNT = re.compile(
    r"^COUNT\(\s*\*\s*\)\s*-\s*COUNT\(\s*(?P<col>[\w.`]+)\s*\)$", re.IGNORECASE
)
_COALESCE = re.compile(r"^COALESCE\(\s*(?P<inner>.+?)\s*,\s*(?P<default>[^,()]+)\s*\)$", re.IGNORECASE)
_AGGREGATE = re.compile(
    r"^(?P<func>COUNT|SUM|MIN|MAX|AVG)\(\s*(?P<distinct>DISTINCT\s+)?(?P<col>\*|[\w.`]+)\s*\)$",
    re.IGNORECASE,
)

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "=": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<>": lambda a, b: a != b,
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
}


class UnsupportedQuery(Exception):
    """The evaluator does not understand this SQL. Extend the evaluator."""


class TableStats:
    """Whole-table counts that Iceberg answers from metadata, not from a scan.

    `COUNT(*)` and `COUNT(DISTINCT col)` on a 600M-row table never touch the
    sample rows a mock can hold, so the scenario declares them and the evaluator
    serves them for unfiltered, ungrouped aggregates. Anything narrower (a
    WHERE, a GROUP BY) falls back to the sample rows.
    """

    def __init__(self, row_count: int, column_stats: dict[str, tuple[int, int]] | None = None):
        self.row_count = row_count
        self.column_stats = column_stats or {}

    def count_all(self) -> int:
        return self.row_count

    def count_column(self, column: str) -> int | None:
        stat = self.column_stats.get(column)
        return self.row_count - stat[1] if stat else None

    def count_distinct(self, column: str) -> int | None:
        stat = self.column_stats.get(column)
        return stat[0] if stat else None


def evaluate(
    query: str,
    rows: list[dict[str, Any]],
    stats: TableStats | None = None,
) -> list[dict[str, Any]]:
    """Run `query` against `rows` and return result rows."""
    cleaned = _VERSION_AS_OF.sub("", query.strip().rstrip(";"))
    cleaned = " ".join(cleaned.split())

    match = _CLAUSES.match(cleaned)
    if not match:
        raise UnsupportedQuery(cleaned)

    selected = _split_top_level(match.group("items"))
    working = [r for r in rows if _matches(r, match.group("where"))]

    group_col = match.group("group")
    # Declared totals only describe the whole table, never a filtered subset.
    whole_table = stats if not match.group("where") and not group_col else None

    order = match.group("order")

    if group_col:
        results = _ordered(_grouped(selected, working, group_col), order)
    elif any(_is_aggregate(item) for item in selected):
        results = [_project_aggregates(selected, working, whole_table)]
    else:
        # Plain selects sort the source rows, so ORDER BY works on a column
        # that is not in the select list — as it does in SQL.
        results = [_project_row(selected, row) for row in _ordered(working, order)]
    if match.group("limit"):
        results = results[: int(match.group("limit"))]
    return results


# ------------------------------------------------------------------ selection


def _split_top_level(items: str) -> list[str]:
    """Split a select list on commas that are not inside parentheses."""
    parts, depth, current = [], 0, []
    for char in items:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


def _split_alias(item: str) -> tuple[str, str]:
    """Return (expression, output name) for one select item."""
    alias_match = re.match(r"^(?P<expr>.+?)\s+AS\s+(?P<alias>[\w]+)$", item, re.IGNORECASE)
    if alias_match:
        return alias_match.group("expr").strip(), alias_match.group("alias")
    return item, re.sub(r"[^\w]+", "_", item).strip("_").lower()


def _is_aggregate(item: str) -> bool:
    expr, _ = _split_alias(item)
    return bool(
        _AGGREGATE.match(expr) or _COALESCE.match(expr) or _COUNT_STAR_MINUS_COUNT.match(expr)
    )


def _project_aggregates(
    selected: list[str], rows: list[dict], stats: "TableStats | None" = None
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in selected:
        expr, name = _split_alias(item)
        out[name] = _evaluate_expression(expr, rows, stats)
    return out


def _project_row(selected: list[str], row: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in selected:
        expr, name = _split_alias(item)
        if expr == "*":
            out.update(row)
        else:
            out[name] = row.get(_bare(expr))
    return out


def _evaluate_expression(
    expr: str, rows: list[dict], stats: "TableStats | None" = None
) -> Any:
    minus = _COUNT_STAR_MINUS_COUNT.match(expr)
    if minus:
        col = _bare(minus.group("col"))
        non_null = _aggregate("COUNT", col, False, rows, stats)
        return _aggregate("COUNT", "*", False, rows, stats) - non_null

    coalesce = _COALESCE.match(expr)
    if coalesce:
        value = _evaluate_expression(coalesce.group("inner").strip(), rows, stats)
        return value if value is not None else _literal(coalesce.group("default"))

    aggregate = _AGGREGATE.match(expr)
    if aggregate:
        return _aggregate(
            aggregate.group("func").upper(),
            aggregate.group("col"),
            bool(aggregate.group("distinct")),
            rows,
            stats,
        )

    if rows:
        return rows[0].get(_bare(expr))
    raise UnsupportedQuery(expr)


def _aggregate(
    func: str,
    column: str,
    distinct: bool,
    rows: list[dict],
    stats: "TableStats | None" = None,
) -> Any:
    if column == "*":
        if func != "COUNT":
            raise UnsupportedQuery(f"{func}(*)")
        return stats.count_all() if stats else len(rows)

    col = _bare(column)
    if stats and func == "COUNT":
        declared = stats.count_distinct(col) if distinct else stats.count_column(col)
        if declared is not None:
            return declared

    values = [r.get(col) for r in rows if r.get(col) is not None]
    if distinct:
        values = list({_hashable(v) for v in values})

    if func == "COUNT":
        return len(values)
    if not values:
        return None
    if func == "SUM":
        return sum(values)
    if func == "MIN":
        return min(values)
    if func == "MAX":
        return max(values)
    if func == "AVG":
        return sum(values) / len(values)
    raise UnsupportedQuery(func)


def _grouped(selected: list[str], rows: list[dict], group_col: str) -> list[dict[str, Any]]:
    col = _bare(group_col)
    buckets: dict[Any, list[dict]] = {}
    for row in rows:
        buckets.setdefault(_hashable(row.get(col)), []).append(row)

    results = []
    for key, bucket in buckets.items():
        out: dict[str, Any] = {}
        for item in selected:
            expr, name = _split_alias(item)
            if _is_aggregate(expr):
                out[name] = _evaluate_expression(expr, bucket)
            elif _bare(expr) == col:
                out[name] = bucket[0].get(col)
            else:
                out[name] = bucket[0].get(_bare(expr))
        results.append(out)
    return results


# -------------------------------------------------------------------- filters


def _matches(row: dict, where: str | None) -> bool:
    if not where:
        return True
    for clause in re.split(r"\s+AND\s+", where, flags=re.IGNORECASE):
        condition = _CONDITION.match(clause)
        if not condition:
            raise UnsupportedQuery(clause)
        value = row.get(_bare(condition.group("col")))
        if not _OPS[condition.group("op")](value, _literal(condition.group("value"))):
            return False
    return True


def _ordered(rows: list[dict], order: str | None) -> list[dict]:
    if not order:
        return rows
    expr = order.strip()
    descending = bool(re.search(r"\bDESC\b", expr, re.IGNORECASE))
    expr = re.sub(r"\s+(ASC|DESC)$", "", expr, flags=re.IGNORECASE).strip()
    key = _bare(expr)
    if rows and key not in rows[0]:
        # Ordering by an aggregate expression: match it to its output name.
        _, key = _split_alias(expr)
    return sorted(rows, key=lambda r: _sort_key(r.get(key)), reverse=descending)


def _sort_key(value: Any) -> tuple[int, Any]:
    if value is None:
        return (0, 0)
    return (1, value) if isinstance(value, (int, float)) else (2, str(value))


# ------------------------------------------------------------------- literals


def _bare(name: str) -> str:
    """Strip a table qualifier and backticks from a column reference."""
    return name.replace("`", "").split(".")[-1]


def _literal(token: str) -> Any:
    text = token.strip()
    if text.upper() == "NULL":
        return None
    if (text.startswith("'") and text.endswith("'")) or (text.startswith('"') and text.endswith('"')):
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _hashable(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_hashable(v) for v in value)
    return value
