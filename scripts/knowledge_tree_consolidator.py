from __future__ import annotations


MIN_EXTRACT_LINES = 15
MAX_MERGE_LINES = 800


def consolidate_chunks(chunks: list[dict[str, object]]) -> list[dict[str, object]]:
    """Merge adjacent chunks with same heading and filter very short chunks."""
    if not chunks:
        return []
    
    grouped = _group_by_heading_and_raw_path(chunks)
    consolidated = []
    
    for group in grouped:
        merged = _merge_group(group)
        if _is_substantial(merged):
            consolidated.append(merged)
    
    return consolidated


def _group_by_heading_and_raw_path(chunks: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    """Group chunks by heading path and raw path, preserving order."""
    groups: list[list[dict[str, object]]] = []
    current_group: list[dict[str, object]] = []
    current_key: tuple[str, str] | None = None
    
    for chunk in chunks:
        key = (str(chunk["heading_path"]), str(chunk["raw_path"]))
        
        if key != current_key:
            if current_group:
                groups.append(current_group)
            current_group = [chunk]
            current_key = key
        else:
            current_group.append(chunk)
    
    if current_group:
        groups.append(current_group)
    
    return groups


def _merge_group(chunks: list[dict[str, object]]) -> dict[str, object]:
    """Merge a group of chunks with the same heading and raw path."""
    if len(chunks) == 1:
        return chunks[0]
    
    first = chunks[0]
    last = chunks[-1]
    
    all_extracts = []
    total_lines = 0
    
    for chunk in chunks:
        extract = chunk["extract"]
        all_extracts.extend(extract)
        total_lines += len(extract)
        
        if total_lines >= MAX_MERGE_LINES:
            break
    
    merged_chunk_paths = [str(chunk["chunk_path"]) for chunk in chunks[:len(all_extracts) // len(chunks[0]["extract"]) + 1]]
    
    return {
        "raw_path": first["raw_path"],
        "heading_path": first["heading_path"],
        "line_start": first["line_start"],
        "line_end": last["line_end"],
        "extract": all_extracts[:MAX_MERGE_LINES] if total_lines > MAX_MERGE_LINES else all_extracts,
        "chunk_path": merged_chunk_paths[0] if len(merged_chunk_paths) == 1 else f"{merged_chunk_paths[0]} (+ {len(merged_chunk_paths) - 1} more)",
    }


def _is_substantial(chunk: dict[str, object]) -> bool:
    """Check if chunk has enough content to be useful."""
    extract = chunk["extract"]
    
    non_empty_lines = [line for line in extract if line.strip()]
    
    if len(non_empty_lines) < MIN_EXTRACT_LINES:
        return False
    
    total_chars = sum(len(line.strip()) for line in non_empty_lines)
    if total_chars < 220:
        return False
    
    return True
