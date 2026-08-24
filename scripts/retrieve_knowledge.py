from __future__ import annotations

import argparse
import json
from pathlib import Path

from knowledge_retrieval import fetch_knowledge_path, list_knowledge_paths
from knowledge_manifest import fetch_manifest, list_manifests



def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_group = list_parser.add_mutually_exclusive_group(required=True)
    list_group.add_argument("--tree", "--source", dest="tree")
    list_group.add_argument("--manifest")
    list_parser.add_argument("--prefix")
    list_parser.add_argument("--limit", type=int)
    list_parser.add_argument("--refresh", action="store_true")

    fetch_parser = subparsers.add_parser("fetch")
    fetch_group = fetch_parser.add_mutually_exclusive_group(required=True)
    fetch_group.add_argument("--tree", "--source", dest="tree")
    fetch_group.add_argument("--manifest")
    fetch_parser.add_argument("--path", required=True)
    fetch_parser.add_argument("--refresh", action="store_true")

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    
    if args.command == "list":
        if args.manifest:
            result = list_manifests(
                repo_root,
                args.manifest,
                prefix=args.prefix,
                limit=args.limit,
            )
        else:
            result = list_knowledge_paths(
                repo_root,
                args.tree,
                prefix=args.prefix,
                limit=args.limit,
                refresh=args.refresh,
            )
    else:
        if args.manifest:
            result = fetch_manifest(
                repo_root,
                args.manifest,
                args.path,
            )
        else:
            result = fetch_knowledge_path(
                repo_root,
                args.tree,
                path=args.path,
                refresh=args.refresh,
            )
    
    print(json.dumps(result, indent=2))



if __name__ == "__main__":
    main()
