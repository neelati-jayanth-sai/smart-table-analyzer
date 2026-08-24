"""Validate review-only remediation SQL before it becomes a finding."""

from __future__ import annotations

import re

import sqlparse


_ALTER_PROPERTIES = re.compile(
    r"^ALTER\s+TABLE\s+([\w.]+)\s+SET\s+TBLPROPERTIES\s*\((.+)\)$",
    re.IGNORECASE | re.DOTALL,
)
_REWRITE_FILES = re.compile(
    r"^CALL\s+[\w.]*system\.rewrite_data_files\s*\(\s*table\s*=>\s*'([^']+)'",
    re.IGNORECASE | re.DOTALL,
)
_PROPERTY_KEY = re.compile(r"['`]([^'`]+)['`]\s*=")


def approve_actionable_sql(sql: str | None, table_name: str | None) -> str | None:
    """Return one reviewed statement for this table, or ``None`` when unsafe.

    The Investigator never executes this text.  This module only permits the
    two remediation forms supported by the curated runbooks and rejects any
    statement whose table target or Iceberg property keys cannot be verified.
    """
    if not sql or not table_name:
        return None
    statement = sql.strip().rstrip(";").strip()
    if not _is_single_statement(statement):
        return None
    if _is_safe_rewrite(statement, table_name) or _is_safe_property_update(statement, table_name):
        return f"{statement};"
    return None


def _is_single_statement(statement: str) -> bool:
    parsed = [item for item in sqlparse.parse(statement) if item.token_first(skip_cm=True)]
    return len(parsed) == 1


def _is_safe_rewrite(statement: str, table_name: str) -> bool:
    match = _REWRITE_FILES.match(statement)
    return bool(match and _same_table(match.group(1), table_name))


def _is_safe_property_update(statement: str, table_name: str) -> bool:
    match = _ALTER_PROPERTIES.match(statement)
    if not match or not _same_table(match.group(1), table_name):
        return False
    keys = _PROPERTY_KEY.findall(match.group(2))
    return bool(keys) and all(key == key.lower() for key in keys)


def _same_table(candidate: str, table_name: str) -> bool:
    return candidate.strip("`").casefold() == table_name.strip("`").casefold()
