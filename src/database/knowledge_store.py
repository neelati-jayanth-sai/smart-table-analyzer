"""Read access to the curated knowledge tree via its SQLite index.

The index holds topic path -> version + content_path; the markdown itself stays
on disk under `knowledge/<source>/`. No embeddings, no vector store — the
knowledge tree is small and hand-curated.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class KnowledgeStore:
    """List and fetch curated knowledge entries."""

    def __init__(self, db_path: Path | str, repo_root: Path | str | None = None):
        self.db_path = Path(db_path)
        self.repo_root = Path(repo_root) if repo_root else self.db_path.parent.parent

    def _query(self, sql: str, params: tuple) -> list[sqlite3.Row]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def list(self, source: str, prefix: str | None = None) -> list[dict[str, Any]]:
        """Return index entries for a source, optionally filtered by path prefix."""
        sql = (
            "SELECT source, topic_path, version, description, content_path"
            " FROM knowledge_index WHERE source = ?"
        )
        params: tuple = (source,)
        if prefix:
            sql += " AND topic_path LIKE ?"
            params = (source, f"{prefix}%")
        sql += " ORDER BY topic_path"
        try:
            return [dict(row) for row in self._query(sql, params)]
        except sqlite3.Error:
            return []

    def fetch(self, source: str, topic_path: str) -> dict[str, Any]:
        """Return one entry with its full markdown content.

        Returns an empty dict when the entry or its file is missing, so callers
        can skip it rather than fail the investigation.
        """
        rows = self._query(
            "SELECT source, topic_path, version, description, content_path"
            " FROM knowledge_index WHERE source = ? AND topic_path = ?",
            (source, topic_path),
        )
        if not rows:
            return {}
        entry = dict(rows[0])
        content_file = self.repo_root / entry["content_path"]
        if not content_file.exists():
            return {}
        entry["content"] = content_file.read_text(encoding="utf-8")
        return entry
