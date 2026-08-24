"""Iceberg/IOMETE snapshot pinning helper."""

from __future__ import annotations

import re
from collections.abc import Callable

METADATA_SUFFIXES = {"files", "partitions", "history", "snapshots"}


_SELECT_STARTERS = ("SELECT", "WITH")


def pin_snapshot(query: str, table_name: str | None, snapshot_id: str | None) -> str:
    """Rewrite table references to use a pinned Iceberg snapshot.

    Only applied to SELECT/WITH queries — VERSION AS OF is not valid syntax
    for DESCRIBE, SHOW, EXPLAIN, or other DDL statements.
    If snapshot_id or table_name is missing, return the query unchanged.
    """
    if not snapshot_id or not table_name:
        return query
    stripped_upper = query.lstrip().upper()
    if not any(stripped_upper.startswith(s) for s in _SELECT_STARTERS):
        return query
    parts = table_name.split(".")
    if len(parts) < 2:
        return query
    base = r"\.".join(re.escape(part) for part in parts)
    suffixes = "|".join(METADATA_SUFFIXES)
    pattern = re.compile(
        r"(?<![\w.])" + base + r"(?:\.(" + suffixes + r"))?(?![\w.])",
        re.IGNORECASE,
    )
    return _replace_outside_quotes(
        query, pattern, lambda match: f"{match.group(0)} VERSION AS OF {snapshot_id}"
    )


def _replace_outside_quotes(
    text: str, pattern: re.Pattern, repl: Callable[[re.Match], str]
) -> str:
    """Apply a regex replacement only outside single-quoted string literals."""
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escape = False

    for char in text:
        if escape:
            current.append(char)
            escape = False
            continue
        if quote:
            current.append(char)
            if char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            segments.append(pattern.sub(repl, "".join(current)))
            current = [char]
            quote = char
            continue
        current.append(char)

    segments.append(pattern.sub(repl, "".join(current)))
    return "".join(segments)


def fetch_current_snapshot(spark, table_name: str) -> str | None:
    """Fetch the latest committed snapshot ID for an Iceberg table.

    Returns the snapshot_id string, or None if the table has no snapshots
    or if Spark raises any error.
    """
    try:
        row = spark.sql(
            f"SELECT snapshot_id FROM {table_name}.snapshots"
            f" ORDER BY committed_at DESC LIMIT 1"
        ).first()
        return str(row[0]) if row is not None else None
    except Exception:
        return None
