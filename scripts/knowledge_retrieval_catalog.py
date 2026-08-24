from __future__ import annotations

from pathlib import Path

from knowledge_tree import build_tree_catalog, load_tree_catalog


def load_retrieval_catalog(
    repo_root: Path,
    source_name: str,
    refresh: bool = False,
) -> dict[str, object]:
    return load_tree_catalog(repo_root, source_name, refresh)



def build_retrieval_catalog(repo_root: Path, source_name: str) -> dict[str, object]:
    return build_tree_catalog(repo_root, source_name)
