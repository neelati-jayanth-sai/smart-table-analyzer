"""Deterministic keyword-based knowledge retrieval fallback."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from src.database.knowledge_store import KnowledgeStore

from src.models.state import KnowledgeReference


KEYWORD_MAP = {
    "file_size": ["file", "size", "target", "sizing", "files"],
    "partitioning": ["partition", "partitioning", "partitioned", "partition_key"],
    "skew": ["skew", "skewed", "distribution", "imbalance"],
    "sort": ["sort", "sorting", "sort_order", "sorted", "order"],
    "delete": ["delete", "deletion", "orphan", "expired", "snapshot", "retention"],
    "snapshot": ["snapshot", "time travel", "history", "version"],
    "metadata": ["metadata", "manifest", "schema", "table", "column"],
    "maintenance": ["maintenance", "compaction", "optimize", "compact", "cleanup"],
}


class KnowledgeRetriever:
    def __init__(self, knowledge_store: KnowledgeStore | None = None, repo_root: Path | str | None = None):
        self._store = knowledge_store
        self._repo_root = Path(repo_root) if repo_root else None
        if not self._repo_root and knowledge_store:
            self._repo_root = getattr(knowledge_store, "repo_root", None) or knowledge_store.db_path.parent.parent

    def search(self, question: str, check_type: str | None = None, top_k: int = 3) -> list[KnowledgeReference]:
        keywords = _extract_keywords(question, check_type)
        candidates = self._index_candidates(keywords, top_k * 2)
        if not candidates and self._repo_root:
            candidates = self._file_candidates(keywords, top_k * 2)
        return self._score(candidates, keywords)[:top_k]

    def _index_candidates(self, keywords: set[str], limit: int) -> list[tuple[str, str, None]]:
        if not self._store:
            return []
        matches: list[tuple[str, str, None]] = []
        for source in ("iceberg", "iomete", "runbooks"):
            for entry in self._store.list(source):
                text = f"{entry['topic_path']} {entry.get('description', '')}".lower()
                if any(k in text for k in keywords):
                    matches.append((source, entry["topic_path"], None))
                    if len(matches) >= limit:
                        return matches
        return matches

    def _file_candidates(self, keywords: set[str], limit: int) -> list[tuple[str, str, str]]:
        if not self._repo_root:
            return []
        matches: list[tuple[str, str, str]] = []
        for path in self._repo_root.glob("knowledge/**/*.md"):
            if path.name.casefold() in ("readme.md", ".gitkeep"):
                continue
            content = path.read_text(encoding="utf-8")
            content_lower = content.lower()
            if any(k in content_lower for k in keywords):
                source = _source_from_path(path, self._repo_root)
                matches.append((source, path.stem, content))
                if len(matches) >= limit:
                    break
        return matches

    def _score(self, candidates: list[tuple[str, str, str | None]], keywords: set[str]) -> list[KnowledgeReference]:
        results: list[KnowledgeReference] = []
        for source, topic_path, content in candidates:
            if content is None:
                try:
                    entry = self._store.fetch(source, topic_path)
                    content = entry.get("content", "")
                    version = entry.get("version", "")
                except Exception:
                    continue
            else:
                version = _compute_version(content)
            if not content:
                continue
            content_lower = content.lower()
            score = sum(content_lower.count(k) for k in keywords)
            results.append(
                {
                    "source": source,
                    "topic_path": topic_path,
                    "version": version,
                    "content": content,
                    "_score": score,
                }
            )
        results.sort(key=lambda r: r["_score"], reverse=True)
        for r in results:
            del r["_score"]
        return results


def _extract_keywords(question: str, check_type: str | None) -> set[str]:
    text = (question or "").lower()
    if check_type:
        text += " " + check_type.lower().replace("_", " ")
    words = set(re.findall(r"[a-z0-9_]+", text))
    normalized = text.replace("_", " ")
    for term, expansions in KEYWORD_MAP.items():
        if term.replace("_", " ") in normalized or term in text:
            words.update(expansions)
    return words


def _source_from_path(path: Path, repo_root: Path) -> str:
    rel = path.relative_to(repo_root / "knowledge")
    return rel.parts[0] if rel.parts else "iceberg"


def _compute_version(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
