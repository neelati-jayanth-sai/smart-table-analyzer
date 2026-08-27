"""Restrict evidence SQL to the investigated table and its Iceberg metadata."""

from __future__ import annotations

import re
import sqlparse

from ._schema_grounding_core import METADATA_SUFFIXES, _extract_sources
from .query_hooks import QueryHook, ValidationResult


class TargetTableHook(QueryHook):
    """Reject a query whose data sources are outside the investigation scope."""

    def __init__(self, table_name: str):
        self._table_name = table_name.casefold().strip("`")
        short = self._table_name.split(".")[-1]
        self._allowed = {self._table_name, short}
        for suffix in METADATA_SUFFIXES:
            self._allowed.update({f"{self._table_name}.{suffix}", f"{short}.{suffix}"})

    def validate(self, query: str) -> ValidationResult:
        sources = [
            source
            for statement in sqlparse.parse(query)
            for source, _ in _extract_sources(statement.tokens)
        ]
        aliases = {name.casefold() for name in re.findall(
            r"(?:\bWITH\b|,)\s*([A-Za-z_][\w]*)\s+AS\s*\(", query, re.IGNORECASE
        )}
        outside = [
            source for source in sources
            if source.casefold().strip("`") not in aliases and not self._is_allowed(source)
        ]
        if outside:
            return ValidationResult(
                False,
                self.__class__.__name__,
                f"Evidence queries may only read {self._table_name}; found {', '.join(outside)}",
            )
        return ValidationResult(True, self.__class__.__name__)

    def _is_allowed(self, source: str) -> bool:
        normalized = source.casefold().strip("`").replace("`", "")
        return normalized in self._allowed
