"""SQLite-backed knowledge retrieval for Investigation Harness.

Implements list and fetch operations over knowledge index stored in investigation.db
per Architecture.md §5 requirements. Maintains backward compatibility with existing CLI.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import investigation_db_path


def list_knowledge_paths(
    repo_root: Path,
    source_name: str,
    prefix: str | None = None,
    limit: int | None = None,
    refresh: bool = False,
) -> dict[str, object]:
    """List knowledge paths from SQLite index.
    
    Args:
        repo_root: Repository root directory
        source_name: Knowledge source (iceberg, iomete, runbooks)
        prefix: Optional path prefix filter
        limit: Optional result limit
        refresh: Ignored (kept for backward compatibility)
    
    Returns:
        Dict with source, matched count, and list of paths with descriptions
    """
    db_path = investigation_db_path(repo_root)
    if not db_path.exists():
        raise ValueError(f"Knowledge database not found: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query
    query = """
        SELECT topic_path, description
        FROM knowledge_index
        WHERE source = ?
    """
    params: list[str] = [source_name]
    
    if prefix:
        query += " AND topic_path LIKE ?"
        params.append(f"{prefix}%")
    
    query += " ORDER BY topic_path"
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Count total matches without limit
    count_query = """
        SELECT COUNT(*) FROM knowledge_index WHERE source = ?
    """
    count_params: list[str] = [source_name]
    if prefix:
        count_query += " AND topic_path LIKE ?"
        count_params.append(f"{prefix}%")
    
    cursor.execute(count_query, count_params)
    total_matched = cursor.fetchone()[0]
    
    conn.close()
    
    results = [{"path": row["topic_path"], "description": row["description"]} for row in rows]
    
    return {
        "source": source_name,
        "prefix": prefix,
        "limit": limit,
        "matched": total_matched,
        "returned": len(results),
        "results": results,
    }


def fetch_knowledge_path(
    repo_root: Path,
    source_name: str,
    path: str,
    refresh: bool = False,
) -> dict[str, object]:
    """Fetch full knowledge entry from SQLite index.
    
    Args:
        repo_root: Repository root directory
        source_name: Knowledge source (iceberg, iomete, runbooks)
        path: Topic path to fetch
        refresh: Ignored (kept for backward compatibility)
    
    Returns:
        Dict with source, path, description, version, and full text
    """
    db_path = investigation_db_path(repo_root)
    if not db_path.exists():
        raise ValueError(f"Knowledge database not found: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT topic_path, description, content_path, version, content_hash, updated_at
        FROM knowledge_index
        WHERE source = ? AND topic_path = ?
        """,
        (source_name, path),
    )
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise ValueError(f"No knowledge path matched '{path}' in source '{source_name}'")
    
    # Read content from file
    content_file = repo_root / row["content_path"]
    if not content_file.exists():
        raise ValueError(f"Knowledge content file missing: {content_file}")
    
    text = content_file.read_text(encoding="utf-8")
    
    return {
        "source": source_name,
        "path": row["topic_path"],
        "description": row["description"],
        "version": {
            "content_version": row["version"],
            "content_sha256": row["content_hash"],
            "updated_at_utc": row["updated_at"],
            "file": row["content_path"],
        },
        "text": text,
    }
