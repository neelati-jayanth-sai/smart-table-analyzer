from __future__ import annotations

import hashlib
import re
from pathlib import Path

from knowledge_tree_consolidator import consolidate_chunks

CHUNK_PATTERNS = {
    "raw_path": re.compile(r"^- raw path: `(.+)`$"),
    "heading_path": re.compile(r"^- heading path: `(.+)`$"),
    "lines": re.compile(r"^- lines: `(\d+)-(\d+)`$"),
}
MANUAL_PATTERNS = {
    "path": re.compile(r"^- path: `(.+)`$"),
    "description": re.compile(r"^- description: `(.+)`$"),
    "version": re.compile(r"^- version: `(.+)`$"),
}
FENCE_START = "``````text"
FENCE_END = "``````"


def build_generated_items(
    entries_root: Path,
    tree_root: Path,
    source_name: str,
    metadata: dict[str, object],
) -> list[dict[str, object]]:
    items = []
    seen_paths: set[str] = set()
    source_root = tree_root.parent
    for bundle_dir in sorted(path.parent for path in entries_root.rglob("README.md")):
        raw_chunks = [_chunk_record(chunk_path, source_root) for chunk_path in sorted(bundle_dir.glob("chunk-*.md"))]
        chunks = consolidate_chunks(raw_chunks)
        totals = _heading_totals(chunks)
        positions: dict[str, int] = {}
        for chunk in chunks:
            key = str(chunk["heading_path"])
            positions[key] = positions.get(key, 0) + 1
            path = entry_path(str(chunk["raw_path"]), key, positions[key], totals[key])
            if path in seen_paths:
                path = f"{path}/entry-{version_token(key, [str(chunk['line_start']), str(chunk['line_end'])])[:8]}"
            seen_paths.add(path)
            version = version_token(path, chunk["extract"])
            write_entry(tree_root, path, source_name, metadata, chunk, version)
            items.append(
                {
                    "path": path,
                    "description": description(chunk),
                    "version": version,
                    "raw_path": chunk["raw_path"],
                    "heading_path": key,
                    "line_span": f"{chunk['line_start']}-{chunk['line_end']}",
                    "bundle_path": bundle_dir.relative_to(tree_root.parent).as_posix() + "/README.md",
                    "chunk_path": chunk["chunk_path"],
                    "repo_url": metadata.get("repo_url"),
                    "commit": metadata.get("commit"),
                }
            )
    return items


def manual_items(tree_root: Path) -> list[dict[str, object]]:
    if not tree_root.exists():
        return []
    items = []
    for readme_path in sorted(tree_root.rglob("README.md")):
        if readme_path.parent == tree_root:
            continue
        values = read_values(readme_path, MANUAL_PATTERNS)
        items.append({"path": values["path"], "description": values["description"], "version": values["version"]})
    return items


def read_values(readme_path: Path, patterns: dict[str, re.Pattern[str]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        for key, pattern in patterns.items():
            match = pattern.match(line)
            if match:
                values[key] = match.group(1)
    missing = [key for key in patterns if key not in values]
    if missing:
        raise ValueError(f"Missing {', '.join(missing)} in {readme_path}")
    return values


def write_tree_readme(tree_root: Path, source_name: str, metadata: dict[str, object], entry_count: int) -> None:
    origin = "Generated from curated chunk bundles." if metadata else "Manual tree for team-authored knowledge."
    lines = [
        f"# {source_name} tree",
        "",
        origin,
        "",
        f"- entries: {entry_count}",
        f"- repo: `{metadata.get('repo_url', '')}`",
        f"- commit: `{metadata.get('commit', '')}`",
        "",
        "Use `python scripts/retrieve_knowledge.py list --tree ...` to browse exact paths.",
        "",
    ]
    (tree_root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _chunk_record(chunk_path: Path, source_root: Path) -> dict[str, object]:
    values: dict[str, object] = {"chunk_path": chunk_path.relative_to(source_root).as_posix()}
    extract = []
    in_extract = False
    for line in chunk_path.read_text(encoding="utf-8").splitlines():
        if line == FENCE_START:
            in_extract = True
            continue
        if line == FENCE_END and in_extract:
            break
        if in_extract:
            extract.append(line)
            continue
        for key, pattern in CHUNK_PATTERNS.items():
            match = pattern.match(line)
            if not match:
                continue
            if key == "lines":
                values["line_start"] = int(match.group(1))
                values["line_end"] = int(match.group(2))
            else:
                values[key] = match.group(1)
    missing = [key for key in ("raw_path", "heading_path", "line_start", "line_end") if key not in values]
    if missing:
        raise ValueError(f"Missing {', '.join(missing)} in {chunk_path}")
    values["extract"] = extract
    return values


def _heading_totals(chunks: list[dict[str, object]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for chunk in chunks:
        key = str(chunk["heading_path"])
        totals[key] = totals.get(key, 0) + 1
    return totals


def entry_path(raw_path: str, heading_path: str, ordinal: int, total: int) -> str:
    raw = Path(raw_path)
    parents = [safe_part(part) for part in raw.parts[:-1]]
    leaf = safe_part(f"{raw.stem or 'root'}--{raw.suffix.lstrip('.') or 'txt'}")
    headings = [safe_part(part) for part in heading_path.split(" > ") if part.strip()] or ["overview"]
    if total > 1:
        headings.append(f"part-{ordinal:03}")
    return "/".join([*parents, leaf, *headings])


def safe_part(value: str, limit: int = 18) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "item"
    if len(slug) <= limit:
        return slug
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
    return f"{slug[: limit - 9]}-{digest}".strip("-")


def version_token(path: str, extract: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(path.encode("utf-8"))
    digest.update(b"\0")
    digest.update("\n".join(extract).encode("utf-8"))
    return digest.hexdigest()


def description(chunk: dict[str, object]) -> str:
    return f"{chunk['heading_path']} from {chunk['raw_path']} lines {chunk['line_start']}-{chunk['line_end']}"


def write_entry(
    tree_root: Path,
    path: str,
    source_name: str,
    metadata: dict[str, object],
    chunk: dict[str, object],
    version: str,
) -> None:
    entry_dir = tree_root / Path(path)
    entry_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {chunk['heading_path']}",
        "",
        f"- source: `{source_name}`",
        f"- path: `{path}`",
        f"- description: `{description(chunk)}`",
        f"- version: `{version}`",
        f"- raw path: `{chunk['raw_path']}`",
        f"- heading path: `{chunk['heading_path']}`",
        f"- line span: `{chunk['line_start']}-{chunk['line_end']}`",
        f"- chunk: `{chunk['chunk_path']}`",
        f"- repo: `{metadata.get('repo_url', '')}`",
        f"- commit: `{metadata.get('commit', '')}`",
        "",
        "## Extract",
        "",
        FENCE_START,
        *chunk["extract"],
        FENCE_END,
        "",
    ]
    (entry_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
