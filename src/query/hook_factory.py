"""Factory for the standard query hook pipeline."""

from __future__ import annotations

from .query_hooks import (
    NoFilePathHook,
    QueryHook,
    ReadOnlyHook,
    SchemaWhitelistHook,
    SingleStatementHook,
)


def create_investigation_hooks(
    allowed_catalogs: list[str] | set[str] | None = None,
    allowed_schemas: list[str] | set[str] | None = None,
    custom_hooks: list[QueryHook] | None = None,
) -> list[QueryHook]:
    """Return the standard hook pipeline for investigations.

    Order matters: single-statement, read-only, file-path, schema-whitelist.
    Custom hooks are appended at the end.
    """
    cats = set(allowed_catalogs) if allowed_catalogs else set()
    schemas = set(allowed_schemas) if allowed_schemas else set()

    hooks: list[QueryHook] = [
        SingleStatementHook(),
        ReadOnlyHook(),
        NoFilePathHook(),
        SchemaWhitelistHook(cats, schemas),
    ]

    if custom_hooks:
        hooks.extend(custom_hooks)

    return hooks
