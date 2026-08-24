from __future__ import annotations

import argparse
import json
from pathlib import Path

from curated_knowledge_bootstrap import bootstrap_curated_knowledge


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    selected_sources = set(args.source or []) or None
    results = bootstrap_curated_knowledge(repo_root, selected_sources)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
