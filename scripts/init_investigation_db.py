"""Initialize investigation database, run migrations, and seed knowledge index.

Usage:
    python scripts/init_investigation_db.py [--db data/investigation.db]
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import InvestigationDb


def compute_version(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def extract_description(content: str, topic_path: str) -> str:
    for line in content.split("\n"):
        if line.startswith("# "):
            desc = line.lstrip("# ").strip()
            return desc[:80] if len(desc) > 80 else desc
    return f"Knowledge entry: {topic_path}"


def scan_knowledge_entries(repo_root: Path) -> list[dict[str, str]]:
    entries = []
    knowledge_dir = repo_root / "knowledge"
    for source_dir in ["iceberg", "iomete", "runbooks"]:
        source_path = knowledge_dir / source_dir
        if not source_path.exists():
            continue
        for md_file in source_path.glob("*.md"):
            topic_path = md_file.stem
            content = md_file.read_text(encoding="utf-8")
            content_path = md_file.relative_to(repo_root).as_posix()
            entries.append(
                {
                    "source": source_dir,
                    "topic_path": topic_path,
                    "version": compute_version(content),
                    "description": extract_description(content, topic_path),
                    "content_path": content_path,
                    "content_hash": compute_content_hash(content),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    return entries


def seed_knowledge_index(db_path: Path, entries: list[dict[str, str]]) -> int:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM knowledge_index")
        for entry in entries:
            conn.execute(
                """
                INSERT INTO knowledge_index
                (source, topic_path, version, description, content_path, content_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, topic_path) DO UPDATE SET
                    version = excluded.version,
                    description = excluded.description,
                    content_path = excluded.content_path,
                    content_hash = excluded.content_hash,
                    updated_at = excluded.updated_at
                """,
                (
                    entry["source"],
                    entry["topic_path"],
                    entry["version"],
                    entry["description"],
                    entry["content_path"],
                    entry["content_hash"],
                    entry["updated_at"],
                ),
            )
        conn.commit()
        return len(entries)


def print_summary(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        print("\nDatabase tables:")
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        for row in cursor.fetchall():
            print(f"  - {row[0]}")

        print("\nKnowledge index by source:")
        cursor = conn.execute(
            "SELECT source, COUNT(*) FROM knowledge_index GROUP BY source"
        )
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]} entries")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/investigation.db")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    db_path = repo_root / args.db
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Initializing investigation database: {db_path}")
    InvestigationDb(db_path)

    print("Seeding knowledge index...")
    entries = scan_knowledge_entries(repo_root)
    if not entries:
        print("Warning: no knowledge entries found")
        return

    count = seed_knowledge_index(db_path, entries)
    print(f"Seeded {count} knowledge entries")
    print_summary(db_path)


if __name__ == "__main__":
    if sys.platform == "win32":
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    main()
