"""Schema grounding hook: validate SQL columns against table metadata."""

from __future__ import annotations

from typing import Any

import sqlparse

from .query_hooks import QueryHook, ValidationResult
from ._schema_grounding_core import (
    METADATA_SUFFIXES,
    _build_alias_map,
    _collect_candidates,
    _extract_sources,
    _resolve_column_ref,
    _resolve_table_str,
)


class SchemaResolver:
    """Resolve columns for the base table and Iceberg metadata tables."""

    def __init__(self, metadata: dict[str, Any] | None):
        self._metadata = metadata or {}

    @property
    def base_table(self) -> str | None:
        return self._metadata.get("table_name")

    def available_columns(self, table_ref: str) -> set[str]:
        last = table_ref.split(".")[-1].lower()
        source = self._metadata.get(last, {}) if last in METADATA_SUFFIXES else self._metadata
        if not isinstance(source, dict):
            source = {}
        cols = source.get("columns", [])
        return {str(c["name"]).lower() for c in cols if c.get("name")}

    def all_table_refs(self) -> list[str]:
        base = self.base_table
        if not base:
            return []
        refs = [base]
        for suffix in METADATA_SUFFIXES:
            if suffix in self._metadata and isinstance(self._metadata[suffix], dict) and "columns" in self._metadata[suffix]:
                refs.append(f"{base}.{suffix}")
        return refs


class SqlGroundingHook(QueryHook):
    """Reject queries that reference columns absent from table metadata."""

    def __init__(
        self,
        schema_resolver: SchemaResolver | None = None,
        table_name: str | None = None,
        table_metadata: dict[str, Any] | None = None,
    ):
        if schema_resolver is not None:
            self.resolver = schema_resolver
        elif table_name and table_metadata:
            metadata = dict(table_metadata)
            metadata.setdefault("table_name", table_name)
            self.resolver = SchemaResolver(metadata)
        else:
            self.resolver = None

    def validate(self, query: str) -> ValidationResult:
        if not self.resolver:
            return ValidationResult(True, self.__class__.__name__)
        base = self.resolver.base_table
        if not base:
            return ValidationResult(True, self.__class__.__name__)
        statements = sqlparse.parse(query)
        if not statements:
            return ValidationResult(True, self.__class__.__name__)
        canonical_refs = self.resolver.all_table_refs()
        if not canonical_refs:
            return ValidationResult(True, self.__class__.__name__)

        sources = []
        for stmt in statements:
            for table_str, alias in _extract_sources(stmt.tokens):
                sources.append((table_str, alias))
        alias_map = _build_alias_map(canonical_refs, sources)
        source_names = {s.lower() for s, _ in sources} | {a.lower() for _, a in sources if a}

        resolved_sources = []
        for table_str, _ in sources:
            canon = _resolve_table_str(table_str, alias_map, canonical_refs)
            if canon:
                resolved_sources.append(canon)
        default_table = resolved_sources[0] if len(resolved_sources) == 1 else None

        for stmt in statements:
            for parts in _collect_candidates(stmt.tokens):
                table_ref, col = _resolve_column_ref(parts, alias_map, source_names, default_table, canonical_refs)
                if table_ref and col:
                    available = self.resolver.available_columns(table_ref)
                    if available and col.lower() not in available:
                        return ValidationResult(
                            False,
                            self.__class__.__name__,
                            f"Column '{col}' is not present in {table_ref}. Available columns: {', '.join(sorted(available))}",
                        )
        return ValidationResult(True, self.__class__.__name__)
