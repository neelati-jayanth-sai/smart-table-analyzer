from __future__ import annotations

import re
from pathlib import Path

FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def build_chunks(
    relative_path: str,
    text: str,
    suffix: str,
    max_lines: int = 150,
) -> list[dict[str, object]]:
    lines = text.splitlines()
    sections = _markdown_sections(lines) if suffix in {".md", ".mdx"} else [_plain_section(lines)]
    chunks = []
    for section in sections:
        heading_path = list(section["heading_path"])
        title = heading_path[-1] if heading_path else relative_path
        for chunk_index, bounds in enumerate(_chunk_ranges(section["lines"], max_lines), start=1):
            start, end = bounds
            chunk_lines = section["lines"][start:end]
            line_start = int(section["line_start"]) + start
            line_end = line_start + len(chunk_lines) - 1
            chunks.append(
                {
                    "title": title,
                    "heading_path": heading_path,
                    "heading_path_text": " > ".join(heading_path) if heading_path else "Overview",
                    "line_start": line_start,
                    "line_end": line_end,
                    "chunk_index": chunk_index,
                    "lines": chunk_lines,
                }
            )
    if chunks:
        return chunks
    return [
        {
            "title": relative_path,
            "heading_path": [],
            "heading_path_text": "Overview",
            "line_start": 1,
            "line_end": 0,
            "chunk_index": 1,
            "lines": [],
        }
    ]


def _plain_section(lines: list[str]) -> dict[str, object]:
    return {"heading_path": [], "line_start": 1, "lines": lines}


def _markdown_sections(lines: list[str]) -> list[dict[str, object]]:
    sections = []
    current_lines = []
    current_path: list[str] = []
    current_start = 1
    heading_stack: list[str] = []
    in_fence = False
    frontmatter_end = _frontmatter_end(lines)
    for line_number, line in enumerate(lines, start=1):
        if line_number <= frontmatter_end:
            current_lines.append(line)
            continue
        if _is_fence(line):
            in_fence = not in_fence
            current_lines.append(line)
            continue
        heading = _heading(line)
        if heading and not in_fence:
            sections.extend(_close_section(current_lines, current_path, current_start, line_number - 1))
            level, heading_text = heading
            heading_stack = heading_stack[: level - 1] + [heading_text]
            current_path = list(heading_stack)
            current_lines = [line]
            current_start = line_number
            continue
        current_lines.append(line)
    sections.extend(_close_section(current_lines, current_path, current_start, len(lines)))
    return sections or [_plain_section(lines)]


def _frontmatter_end(lines: list[str]) -> int:
    if not lines or lines[0].strip() != "---":
        return 0
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return index
    return 0


def _close_section(
    lines: list[str],
    heading_path: list[str],
    line_start: int,
    line_end: int,
) -> list[dict[str, object]]:
    if not lines or not any(part.strip() for part in lines):
        return []
    return [{"heading_path": list(heading_path), "line_start": line_start, "lines": list(lines)}]


def _chunk_ranges(lines: list[str], max_lines: int) -> list[tuple[int, int]]:
    if not lines:
        return [(0, 0)]
    ranges = []
    start = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        split = _last_blank(lines, start, end)
        if split and split > start + (max_lines // 2):
            end = split
        ranges.append((start, end))
        start = end
    return ranges


def _last_blank(lines: list[str], start: int, end: int) -> int | None:
    for index in range(end - 1, start, -1):
        if not lines[index].strip():
            return index + 1
    return None


def _heading(line: str) -> tuple[int, str] | None:
    match = HEADING_PATTERN.match(line)
    if not match:
        return None
    text = match.group(2).strip()
    if not text:
        return None
    return len(match.group(1)), text


def _is_fence(line: str) -> bool:
    return bool(FENCE_PATTERN.match(line))


def entry_slug(relative_path: str) -> Path:
    path = Path(relative_path)
    parents = [_safe_part(part) for part in path.parts[:-1]]
    name = path.name.lstrip(".") or "root"
    stem = Path(name).stem or "root"
    suffix = path.suffix.lstrip(".") or "txt"
    leaf = f"{_safe_part(stem)}--{_safe_part(suffix)}"
    return Path(*parents, leaf) if parents else Path(leaf)


def _safe_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return cleaned or "item"
