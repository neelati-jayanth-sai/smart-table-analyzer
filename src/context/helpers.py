"""Helper functions for building PromptContext from InvestigationState fields."""

from __future__ import annotations

from typing import Any

from src.models.state import InvestigationState


def weakest_dimensions(dimensions: dict[str, Any], n: int = 3) -> list[tuple[str, Any]]:
    """Return the n weakest dimensions, excluding placeholder values (50.0)."""
    placeholder_dimensions = {"scan_efficiency", "sort_order"}
    numeric = {k: v for k, v in dimensions.items() if isinstance(v, (int, float))}
    filtered = {
        k: v for k, v in numeric.items()
        if not (k in placeholder_dimensions and v == 50.0)
    }
    if not filtered:
        filtered = numeric
    return sorted(filtered.items(), key=lambda x: x[1])[:n]


def partition_info(
    metadata: dict[str, Any] | None, baseline_score: dict[str, Any] | None
) -> dict[str, Any]:
    """Derive partition queryability summary from metadata and baseline dimensions."""
    metadata = metadata or {}
    dims = (baseline_score or {}).get("dimensions") or {}
    partition_count = dims.get("partition_count", 0)
    partition_cols = [
        c.get("name", "").lower()
        for c in (metadata.get("partitions") or {}).get("columns", [])
    ]
    return {"partition_count": partition_count, "partition_queryable": "partition" in partition_cols}


def previous_error(state: InvestigationState) -> str:
    """Return a formatted error message if the last query attempt failed."""
    if state.get("retry_count", 0) <= 0:
        return ""
    query = state.get("current_query") or ""
    error = (state.get("query_result") or {}).get("error") or ""
    if not query and not error:
        return ""
    return (
        "\nPrevious query failed:\n"
        f"{query}\n"
        f"Error: {error}\n"
        "Rewrite the query to fix the error, using only the columns listed above"
        " for the metadata table you query.\n"
    )


def format_metadata(table: str, metadata: dict[str, Any] | None) -> str:
    """Render a human-readable column listing for the main table and metadata tables."""
    if not metadata:
        return "Available columns by table: (none)"
    lines = [f"Available columns for {table}:"]
    sections = [("", table)] + [
        (suffix, f"{table}.{suffix}")
        for suffix in ("files", "partitions", "history", "snapshots")
    ]
    for suffix, label in sections:
        source = metadata.get(suffix) if suffix else metadata
        cols = source.get("columns") if isinstance(source, dict) else metadata.get("columns")
        if not cols:
            lines.append(f"- {label}: (no columns available)")
            continue
        names = [c.get("name") for c in cols if c.get("name")]
        lines.append(f"- {label}: {', '.join(names) if names else '(none)'}")
    return "\n".join(lines)
