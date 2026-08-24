"""Knowledge indexing keeps one database location and ignores README inventories."""

from __future__ import annotations

from pathlib import Path

from scripts import init_investigation_db as indexer
from scripts.knowledge_retrieval import list_knowledge_paths
from scripts.knowledge_retrieval_sqlite import list_knowledge_paths as sqlite_list_knowledge_paths
from src.database import InvestigationDb, KnowledgeStore, investigation_db_path, resolve_investigation_db_path
from src.investigator.knowledge import KnowledgeRetriever


def _write_knowledge(repo_root: Path) -> None:
    iceberg = repo_root / "knowledge" / "iceberg"
    iceberg.mkdir(parents=True)
    (iceberg / "file-sizing.md").write_text("# File sizing\n\nUse 128 MB files.\n")
    (iceberg / "README.md").write_text("# Stale inventory\n\nMissing topic directory.\n")


def test_index_and_retrieval_use_data_database_and_skip_readmes(tmp_path):
    _write_knowledge(tmp_path)
    db_path = investigation_db_path(tmp_path)
    db_path.parent.mkdir()
    InvestigationDb(db_path)

    entries = indexer.scan_knowledge_entries(tmp_path)
    assert [(entry["source"], entry["topic_path"]) for entry in entries] == [("iceberg", "file-sizing")]
    indexer.seed_knowledge_index(db_path, entries)

    for retrieve in (list_knowledge_paths, sqlite_list_knowledge_paths):
        result = retrieve(tmp_path, "iceberg")
        assert result["results"] == [{"path": "file-sizing", "description": "File sizing"}]

    store = KnowledgeStore(db_path, repo_root=tmp_path)
    assert store.fetch("iceberg", "README") == {}
    assert [entry["topic_path"] for entry in store.list("iceberg")] == ["file-sizing"]


def test_file_fallback_does_not_retrieve_readme_inventory(tmp_path):
    _write_knowledge(tmp_path)

    assert KnowledgeRetriever(repo_root=tmp_path).search("missing topic directory") == []


def test_database_path_defaults_to_data_and_allows_explicit_test_override(tmp_path):
    assert investigation_db_path(tmp_path) == tmp_path / "data" / "investigation.db"
    assert resolve_investigation_db_path(tmp_path) == tmp_path / "data" / "investigation.db"
    assert resolve_investigation_db_path(tmp_path, "data/test.db") == tmp_path / "data" / "test.db"
    assert resolve_investigation_db_path(tmp_path, tmp_path / "custom.db") == tmp_path / "custom.db"
