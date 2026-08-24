from __future__ import annotations

from pathlib import Path

CATALOG_PAGE_SIZE = 140
TOPIC_PAGE_SIZE = 120


def write_topic_tree(
    curated_root: Path,
    source_name: str,
    metadata: dict[str, object],
    bundles: list[dict[str, object]],
    topics: dict[str, dict[str, object]],
) -> dict[str, object]:
    topics_root = curated_root / "topics"
    topics_root.mkdir(parents=True, exist_ok=True)
    summaries = [_topic_summary(slug, topic) for slug, topic in sorted(topics.items())]
    catalog_pages = _write_catalog_pages(topics_root, source_name, summaries)
    generated_files = 1 + len(catalog_pages)
    topic_pages = 0
    for summary in summaries:
        pages = _write_topic(summary, topics_root, source_name)
        summary["pages"] = pages
        topic_pages += len(pages)
        generated_files += 1 + len(pages)
    _write_topics_readme(topics_root, source_name, metadata, bundles, summaries, catalog_pages)
    return {
        "name": source_name,
        "bundle_count": len(bundles),
        "chunk_count": sum(len(bundle["chunks"]) for bundle in bundles),
        "topic_count": len(summaries),
        "catalog_pages": len(catalog_pages),
        "topic_pages": topic_pages,
        "generated_files": generated_files,
    }


def _topic_summary(slug: str, topic: dict[str, object]) -> dict[str, object]:
    docs = []
    chunk_total = 0
    line_total = 0
    for raw_path, record in sorted(topic["docs"].items()):
        chunks = sorted(record["chunks"].values(), key=lambda item: (item["line_start"], item["chunk_path"]))
        chunk_count = len(chunks)
        line_count = sum(max(0, chunk["line_end"] - chunk["line_start"] + 1) for chunk in chunks)
        chunk_total += chunk_count
        line_total += line_count
        docs.append(
            {
                "raw_path": raw_path,
                "bundle_path": record["bundle_path"],
                "chunk_count": chunk_count,
                "line_count": line_count,
                "chunks": chunks,
            }
        )
    return {
        "slug": slug,
        "label": _best_label(topic["labels"]),
        "variants": sorted(topic["labels"], key=lambda item: (len(item.split()), len(item), item.lower())),
        "kinds": sorted(topic["kinds"]),
        "doc_count": len(docs),
        "chunk_count": chunk_total,
        "line_count": line_total,
        "docs": docs,
    }


def _write_catalog_pages(topics_root: Path, source_name: str, summaries: list[dict[str, object]]) -> list[str]:
    page_paths = []
    for page_number, start in enumerate(range(0, len(summaries), CATALOG_PAGE_SIZE), start=1):
        page_name = f"page-{page_number:03}.md"
        lines = [f"# {source_name} topic catalog page {page_number}", "", "Browse normalized topics.", ""]
        for summary in summaries[start : start + CATALOG_PAGE_SIZE]:
            lines.append(
                f"- {summary['label']} -> `{summary['slug']}/README.md` ({summary['doc_count']} docs, {summary['chunk_count']} chunks, {summary['line_count']} lines)"
            )
        (topics_root / page_name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        page_paths.append(page_name)
    return page_paths


def _write_topic(summary: dict[str, object], topics_root: Path, source_name: str) -> list[str]:
    topic_dir = topics_root / str(summary["slug"])
    topic_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for doc in summary["docs"]:
        for chunk in doc["chunks"]:
            items.append(
                f"- raw `{doc['raw_path']}`; bundle `{doc['bundle_path']}`; chunk `{chunk['chunk_path']}`; heading {chunk['heading_path_text']}; lines `{chunk['line_start']}-{chunk['line_end']}`"
            )
    pages = []
    for page_number, start in enumerate(range(0, len(items), TOPIC_PAGE_SIZE), start=1):
        page_name = f"page-{page_number:03}.md"
        lines = [f"# {summary['label']} topic page {page_number}", "", f"- source: `{source_name}`", ""]
        lines.extend(items[start : start + TOPIC_PAGE_SIZE])
        (topic_dir / page_name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        pages.append(page_name)
    _write_topic_readme(topic_dir, source_name, summary, pages)
    return pages


def _write_topic_readme(
    topic_dir: Path,
    source_name: str,
    summary: dict[str, object],
    pages: list[str],
) -> None:
    lines = [
        f"# {summary['label']}",
        "",
        f"- slug: `{summary['slug']}`",
        f"- source: `{source_name}`",
        f"- bundles: {summary['doc_count']}",
        f"- chunks: {summary['chunk_count']}",
        f"- lines: {summary['line_count']}",
        f"- evidence: `{', '.join(summary['kinds'])}`",
        "",
        "## Variants",
        "",
    ]
    lines.extend(f"- {variant}" for variant in summary["variants"][:20])
    lines.extend(["", "## Pages", ""])
    lines.extend(f"- `{page_name}`" for page_name in pages)
    (topic_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_topics_readme(
    topics_root: Path,
    source_name: str,
    metadata: dict[str, object],
    bundles: list[dict[str, object]],
    summaries: list[dict[str, object]],
    catalog_pages: list[str],
) -> None:
    lines = [
        f"# {source_name} topics",
        "",
        "Generated by `python scripts/build_topic_knowledge.py` from curated bundles.",
        "",
        f"- repo: `{metadata['repo_url']}`",
        f"- commit: `{metadata['commit']}`",
        f"- bundles indexed: {len(bundles)}",
        f"- bundle chunks indexed: {sum(len(bundle['chunks']) for bundle in bundles)}",
        f"- normalized topics: {len(summaries)}",
        "",
        "## Browse",
        "",
        "- Catalog pages list normalized topics for list-then-fetch retrieval.",
        "- Topic pages list raw paths, bundle readmes, chunk files, and line spans.",
        "",
        "## Catalog pages",
        "",
    ]
    lines.extend(f"- `{page_name}`" for page_name in catalog_pages)
    (topics_root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _best_label(labels: set[str]) -> str:
    return min(labels, key=lambda item: ("-" in item or "_" in item, len(item.split()), len(item), item.lower()))
