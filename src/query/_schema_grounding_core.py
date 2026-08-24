from __future__ import annotations

from sqlparse import sql
from sqlparse import tokens as T

METADATA_SUFFIXES = {"files", "partitions", "history", "snapshots"}

_STRUCTURAL_KEYWORDS = {"SELECT", "FROM", "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "UNION", "INTERSECT", "EXCEPT", "BY", "AS", "ASC", "DESC", "DISTINCT", "ALL", "AND", "OR", "NOT", "IN", "IS", "NULL", "TRUE", "FALSE", "BETWEEN", "LIKE", "ILIKE", "ESCAPE", "CASE", "WHEN", "THEN", "ELSE", "END", "EXISTS", "ANY", "SOME", "OVER", "ROWS", "RANGE", "PRECEDING", "FOLLOWING", "CURRENT", "ROW", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "NATURAL", "ON", "USING", "UNIQUE", "VALUES", "SET", "RETURNING", "WITH", "RECURSIVE", "FILTER", "WITHIN", "CUBE", "ROLLUP", "GROUPING", "SETS", "OFFSET", "FETCH", "OF"}

_FROM_STOP = {"WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "UNION", "INTERSECT", "EXCEPT", "SELECT", "WITH", "ON", "USING", "BY", "GROUP BY", "ORDER BY"}


def _first_meaningful(tokens):
    for t in tokens:
        if not t.is_whitespace:
            return t
    return None


def _first_name(token):
    if isinstance(token, sql.Identifier):
        for sub in token.tokens:
            if sub.is_whitespace or (sub.ttype is T.Punctuation and sub.value == "."):
                continue
            if sub.ttype is T.Name:
                return sub.value
    return None


def _identifier_parts(identifier: sql.Identifier) -> list[str]:
    parts: list[str] = []
    for token in identifier.tokens:
        if token.is_whitespace or (token.ttype is T.Punctuation and token.value == "."):
            continue
        if isinstance(token, sql.Identifier):
            break
        if token.ttype in (T.Keyword, T.Keyword.DML) and token.normalized == "AS":
            break
        if token.ttype is T.Name:
            parts.append(token.value)
        else:
            break
    return parts


def _parse_source_identifier(identifier: sql.Identifier):
    parts: list[str] = []
    alias = None
    for token in identifier.tokens:
        if token.is_whitespace or (token.ttype is T.Punctuation and token.value == "."):
            continue
        if isinstance(token, sql.Identifier):
            alias = _first_name(token)
            break
        if token.ttype in (T.Keyword, T.Keyword.DML) and token.normalized == "AS":
            continue
        if token.ttype is T.Name:
            parts.append(token.value)
        else:
            break
    return (".".join(parts), alias) if parts else None


def _extract_sources(tokens):
    sources: list[tuple[str, str | None]] = []
    in_from = False
    for token in tokens:
        if token.is_whitespace:
            continue
        if token.ttype in (T.Keyword, T.Keyword.DML):
            if token.normalized in ("FROM", "JOIN"):
                in_from = True
                continue
            if in_from and token.normalized in _FROM_STOP:
                in_from = False
                continue
        if in_from:
            if isinstance(token, sql.IdentifierList):
                for ident in token.get_identifiers():
                    src = _parse_source_identifier(ident)
                    if src:
                        sources.append(src)
            elif isinstance(token, sql.Identifier):
                src = _parse_source_identifier(token)
                if src:
                    sources.append(src)
            continue
        if token.is_group and not isinstance(token, sql.Parenthesis):
            sources.extend(_extract_sources(token.tokens))
    return sources


def _is_candidate_token(token, tokens, i):
    if token.ttype not in (T.Name, T.Keyword):
        return False
    if token.ttype is T.Keyword:
        if any(part in _STRUCTURAL_KEYWORDS for part in token.normalized.split()):
            return False
        if token.normalized == "PARTITION":
            j = i
            while j < len(tokens) and tokens[j].is_whitespace:
                j += 1
            if j < len(tokens) and tokens[j].ttype in (T.Keyword,) and tokens[j].normalized == "BY":
                return False
    return True


def _collect_candidates(tokens):
    candidates: list[list[str]] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if token.is_whitespace:
            continue
        if isinstance(token, sql.Function):
            for child in token.tokens[1:]:
                candidates.extend(_collect_candidates(child.tokens if child.is_group else [child]))
            continue
        if isinstance(token, sql.IdentifierList):
            for ident in token.get_identifiers():
                if isinstance(ident, sql.Identifier):
                    parts = _identifier_parts(ident)
                    if parts:
                        candidates.append(parts)
                elif isinstance(ident, sql.Function):
                    candidates.extend(_collect_candidates([ident]))
                elif _is_candidate_token(ident, token.tokens, 0):
                    candidates.append([ident.value])
            continue
        if isinstance(token, sql.Identifier):
            parts = _identifier_parts(token)
            if parts:
                candidates.append(parts)
            continue
        if isinstance(token, sql.Parenthesis):
            first = _first_meaningful(token.tokens)
            if first and first.ttype in (T.Keyword.DML,) and first.normalized == "SELECT":
                continue
            candidates.extend(_collect_candidates(token.tokens))
            continue
        if _is_candidate_token(token, tokens, i):
            candidates.append([token.value])
            continue
        if token.is_group:
            candidates.extend(_collect_candidates(token.tokens))
    return candidates


def _resolve_table_str(table_str: str, alias_map: dict[str, str], canonical_refs: list[str]):
    tl = table_str.lower()
    if tl in alias_map:
        return alias_map[tl]
    if "." in tl:
        for ref in canonical_refs:
            if ref.lower().endswith("." + tl):
                return ref
    return None


def _build_alias_map(canonical_refs: list[str], sources: list[tuple[str, str | None]]):
    alias_map = {ref.lower(): ref for ref in canonical_refs}
    base = canonical_refs[0] if canonical_refs else None
    if base:
        short = base.split(".")[-1].lower()
        alias_map.setdefault(short, base)
        for suffix in METADATA_SUFFIXES:
            meta = f"{base}.{suffix}"
            if meta in canonical_refs:
                alias_map.setdefault(f"{short}.{suffix}".lower(), meta)
    for table_str, alias in sources:
        canon = _resolve_table_str(table_str, alias_map, canonical_refs)
        if canon:
            alias_map[table_str.lower()] = canon
            if alias:
                alias_map[alias.lower()] = canon
    return alias_map


def _resolve_column_ref(parts: list[str], alias_map: dict[str, str], source_names: set[str], default_table: str | None, canonical_refs: list[str]):
    if not parts:
        return None, None
    full = ".".join(parts).lower()
    if full in source_names or full in alias_map or any(ref.lower() == full for ref in canonical_refs):
        return None, None
    if len(parts) > 1:
        prefix = ".".join(parts[:-1]).lower()
        col = parts[-1]
        if prefix in alias_map:
            return alias_map[prefix], col
        if "." in prefix:
            for ref in canonical_refs:
                if ref.lower().endswith("." + prefix):
                    return ref, col
        return None, None
    if default_table:
        return default_table, parts[0]
    return None, None
