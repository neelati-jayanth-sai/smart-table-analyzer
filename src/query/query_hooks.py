"""Query safety hooks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

import sqlparse
from sqlparse import sql


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    hook_name: str = ""
    error_message: str = ""


class QueryHook:
    def validate(self, query: str) -> ValidationResult:
        raise NotImplementedError


class ReadOnlyHook(QueryHook):
    ALLOWED_STATEMENTS: ClassVar[set[str]] = {"SELECT", "SHOW", "DESCRIBE", "EXPLAIN"}
    FORBIDDEN_KEYWORDS: ClassVar[set[str]] = {
        "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "REPLACE", "MERGE",
        "GRANT", "REVOKE", "LOAD", "COPY", "EXPORT", "IMPORT", "ATTACH", "DETACH",
    }

    def validate(self, query: str) -> ValidationResult:
        statements = sqlparse.parse(query)
        if not statements:
            return ValidationResult(False, self.__class__.__name__, "Empty query")
        for statement in statements:
            if not statement.tokens:
                return ValidationResult(False, self.__class__.__name__, "Empty statement")
            stmt_type = statement.get_type().upper()
            if stmt_type == "UNKNOWN":
                first = next((t for t in statement.tokens if not t.is_whitespace), None)
                stmt_type = first.normalized if first else "UNKNOWN"
            if stmt_type not in self.ALLOWED_STATEMENTS and stmt_type != "UNKNOWN":
                return ValidationResult(
                    False, self.__class__.__name__,
                    f"Statement type '{stmt_type}' is not allowed",
                )
            keyword_types = (sqlparse.tokens.Keyword, sqlparse.tokens.Keyword.DML, sqlparse.tokens.Keyword.DDL, sqlparse.tokens.Keyword.DCL)
            for token in statement.flatten():
                if token.normalized in self.FORBIDDEN_KEYWORDS and token.ttype in keyword_types:
                    return ValidationResult(
                        False, self.__class__.__name__,
                        f"Forbidden keyword '{token.normalized}' detected",
                    )
        return ValidationResult(True, self.__class__.__name__)


class SingleStatementHook(QueryHook):
    def validate(self, query: str) -> ValidationResult:
        statements = sqlparse.parse(query)
        non_empty = [s for s in statements if s.token_first(skip_cm=True) is not None]
        if len(non_empty) > 1:
            return ValidationResult(
                False, self.__class__.__name__,
                "Only one statement per query is allowed",
            )
        return ValidationResult(True, self.__class__.__name__)


class NoFilePathHook(QueryHook):
    PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"file://", re.IGNORECASE),
        re.compile(r"\bLOAD\s+DATA\b", re.IGNORECASE),
        re.compile(r"\bCOPY\s+INTO\b", re.IGNORECASE),
        re.compile(r"\bEXPORT\b", re.IGNORECASE),
        re.compile(r"\bIMPORT\b", re.IGNORECASE),
    ]

    def validate(self, query: str) -> ValidationResult:
        for pattern in self.PATTERNS:
            if pattern.search(query):
                return ValidationResult(
                    False, self.__class__.__name__,
                    "File path or external data access detected",
                )
        return ValidationResult(True, self.__class__.__name__)


class SchemaWhitelistHook(QueryHook):
    METADATA_SUFFIXES: ClassVar[set[str]] = {
        "files", "partitions", "history", "snapshots", "manifests",
    }
    _STOP_KEYWORDS: ClassVar[set[str]] = {
        "WHERE", "GROUP", "GROUP BY", "ORDER", "ORDER BY", "HAVING", "LIMIT",
        "UNION", "INTERSECT", "EXCEPT", "ON", "USING", "SELECT", "WITH", "BY",
    }

    def __init__(self, allowed_catalogs: set[str], allowed_schemas: set[str]):
        self.allowed_catalogs = {c.lower() for c in allowed_catalogs}
        self.allowed_schemas = {s.lower() for s in allowed_schemas}

    @staticmethod
    def _identifier_parts(identifier: sql.Identifier) -> list[str]:
        parts: list[str] = []
        for token in identifier.tokens:
            if token.is_whitespace or isinstance(token, sql.Identifier):
                break
            if token.ttype is sqlparse.tokens.Keyword and token.normalized == "AS":
                break
            if token.ttype is sqlparse.tokens.Punctuation:
                if token.value == ".":
                    continue
                break
            if token.ttype is sqlparse.tokens.Name:
                parts.append(token.value)
            else:
                break
        return parts

    def _add_ref(self, parts: list[str], refs: set[tuple[str, str]]) -> None:
        if not parts:
            return
        if parts[-1].lower() in self.METADATA_SUFFIXES:
            parts = parts[:-1]
        if len(parts) < 2:
            return
        catalog = parts[0].lower() if len(parts) >= 3 else ""
        schema = parts[-2].lower()
        refs.add((catalog, schema))

    def _collect_refs(
        self,
        tokens: list,
        refs: set[tuple[str, str]],
        in_from: bool = False,
    ) -> None:
        i = 0
        while i < len(tokens):
            token = tokens[i]
            i += 1
            if token.is_whitespace:
                continue
            if (
                token.ttype in (sqlparse.tokens.Keyword, sqlparse.tokens.Keyword.DML)
                and token.normalized in ("FROM", "JOIN")
            ):
                in_from = True
                continue
            if in_from:
                if token.ttype is sqlparse.tokens.Keyword and token.normalized in self._STOP_KEYWORDS:
                    in_from = False
                    continue
                if isinstance(token, sql.Parenthesis):
                    self._collect_refs(token.tokens, refs, False)
                    continue
                if isinstance(token, sql.Identifier):
                    if any(isinstance(t, sql.Parenthesis) for t in token.tokens):
                        self._collect_refs(token.tokens, refs, False)
                    else:
                        self._add_ref(self._identifier_parts(token), refs)
                    continue
                if isinstance(token, sql.IdentifierList):
                    for ident in token.get_identifiers():
                        if isinstance(ident, sql.Identifier):
                            if any(isinstance(t, sql.Parenthesis) for t in ident.tokens):
                                self._collect_refs(ident.tokens, refs, False)
                            else:
                                self._add_ref(self._identifier_parts(ident), refs)
                    continue
                if token.ttype is sqlparse.tokens.Punctuation and token.value == ",":
                    continue
            if token.is_group:
                self._collect_refs(token.tokens, refs, in_from)

    def _extract_table_refs(self, query: str) -> set[tuple[str, str]]:
        refs: set[tuple[str, str]] = set()
        for statement in sqlparse.parse(query):
            self._collect_refs(statement.tokens, refs)
        return refs

    def validate(self, query: str) -> ValidationResult:
        refs = self._extract_table_refs(query)
        for catalog, schema in refs:
            if catalog and catalog not in self.allowed_catalogs:
                return ValidationResult(
                    False, self.__class__.__name__,
                    f"Catalog '{catalog}' is not whitelisted",
                )
            if schema and schema not in self.allowed_schemas:
                return ValidationResult(
                    False, self.__class__.__name__,
                    f"Schema '{schema}' is not whitelisted",
                )
        return ValidationResult(True, self.__class__.__name__)
