"""Summarize investigation state down to what a prompt can afford.

Raw query results and full metadata stay in Spark and SQLite; only these
condensed forms reach the LLM.
"""
from __future__ import annotations

from typing import Any

_MIN_COLS_FLOOR = 10
_SECTION_SUFFIXES = ("files", "partitions", "history", "snapshots")


def summarize_findings(findings: list, max_items: int = 3) -> list[dict]:
    if max_items <= 0:
        return []
    results: list[dict] = []
    for finding in findings[-max_items:]:
        results.append(
            {
                "check_num": finding.get("check_num"),
                "question": finding.get("question"),
                "verdict": finding.get("verdict"),
                "rationale": _one_line(finding.get("rationale", "")),
                "exact_result": _one_line(finding.get("exact_result", "")),
            }
        )
    return results


def _one_line(text: str) -> str:
    return " ".join(text.split())[:120]


def summarize_query_result(query_result: dict[str, Any] | None, max_rows: int = 3) -> dict:
    if not query_result:
        return {"row_count": 0, "schema": [], "rows": []}
    rows = query_result.get("rows") or []
    schema = query_result.get("schema") or []
    columns = [c.get("name", "") for c in schema]
    return {
        "row_count": query_result.get("row_count", len(rows)),
        "schema": columns,
        "rows": rows[:max_rows],
    }


def prepare_knowledge_context(knowledge_consulted: list, max_chars: int = 2000) -> str:
    if max_chars <= 0:
        return ""
    parts: list[str] = []
    total = 0
    for ref in knowledge_consulted:
        content = ref.get("content", "") or ""
        if not content:
            continue
        header = f"[{ref.get('source')}/{ref.get('topic_path')}]\n"
        if len(content) > 500:
            content = content[:500] + "..."
        needed = len(header) + len(content) + 2
        if total + needed > max_chars and parts:
            break
        parts.append(header + content)
        total += needed
    return "\n\n".join(parts)


def _allocate_budgets(sizes: list[int], total: int) -> list[int]:
    n = len(sizes)
    if n == 0:
        return []
    if total <= 0:
        return [0] * n
    base = total // n
    floor = min(_MIN_COLS_FLOOR, base)
    budgets = [min(size, floor) for size in sizes]
    remaining = total - sum(budgets)
    while remaining > 0:
        active = [(i, sizes[i] - budgets[i]) for i in range(n) if budgets[i] < sizes[i]]
        if not active:
            break
        active.sort(key=lambda x: x[1], reverse=True)
        share = max(1, remaining // len(active))
        for i, capacity in active:
            if remaining <= 0:
                break
            add = min(capacity, share, remaining)
            budgets[i] += add
            remaining -= add
    return budgets


def summarize_metadata(metadata: dict[str, Any] | None, max_total_cols: int | None = None) -> dict[str, Any]:
    if not metadata:
        return {}
    summary: dict[str, Any] = {"table_name": metadata.get("table_name", "")}
    sections = [("", metadata.get("columns") or [])] + [
        (suffix, (metadata.get(suffix) or {}).get("columns") or []) for suffix in _SECTION_SUFFIXES
    ]
    sizes = [len(cols) for _, cols in sections]
    budgets = _allocate_budgets(sizes, max_total_cols) if max_total_cols is not None and max_total_cols > 0 else sizes
    for (suffix, cols), budget in zip(sections, budgets):
        kept: list[dict[str, Any]] = []
        if budget > 0:
            partition_item: dict[str, Any] | None = None
            remaining: list[dict[str, Any]] = []
            for c in cols:
                item = {"name": c.get("name"), "type": c.get("type")}
                name = (c.get("name") or "").lower()
                if suffix == "partitions" and name == "partition":
                    partition_item = item
                else:
                    remaining.append(item)
            if partition_item:
                kept.append(partition_item)
                budget -= 1
            kept.extend(remaining[:budget])
        if suffix:
            summary[suffix] = {"columns": kept}
        else:
            summary["columns"] = kept
    return summary
