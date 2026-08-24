"""Verify knowledge tool loop and deterministic fallback for the current LLM_MODEL."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "scripts"))

from dotenv import load_dotenv

load_dotenv(repo_root / ".env")

import init_investigation_db as init_db
from src.connectors import DellAIAAdapter
from src.database import InvestigationDb
from src.database.knowledge_store import KnowledgeStore
from src.investigator.knowledge import KnowledgeRetriever
from src.investigator.knowledge import KnowledgeToolRunner


def main() -> int:
    db_path = repo_root / "data" / "knowledge_retrieval_test.db"
    db_path.unlink(missing_ok=True)

    db = InvestigationDb(db_path)
    entries = init_db.scan_knowledge_entries(repo_root)
    if entries:
        init_db.seed_knowledge_index(db_path, entries)

    knowledge = KnowledgeStore(db_path, repo_root=repo_root)
    llm = DellAIAAdapter.from_env()

    inv_id = db.create_investigation(
        run_id=str(uuid.uuid4()),
        table_name="eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev",
        catalog_name="eds_it_dev",
        schema_name="elh_comn",
        max_checks=1,
    )

    state = {
        "investigation_id": inv_id,
        "check_count": 0,
        "current_question": "Are data files correctly sized?",
        "current_check_type": "file_size",
    }

    print(f"Testing model: {llm._model}")

    runner = KnowledgeToolRunner(llm, knowledge, db)
    refs = runner.run(state)
    print(f"Tool loop returned {len(refs)} references")
    for ref in refs:
        print(f"  - {ref['source']}/{ref['topic_path']}@{ref['version']}")

    retriever = KnowledgeRetriever(knowledge, repo_root)
    fallback = retriever.search(state["current_question"], state["current_check_type"])
    print(f"Fallback returned {len(fallback)} references")
    for ref in fallback:
        print(f"  - {ref['source']}/{ref['topic_path']}@{ref['version']}")

    if not refs and not fallback:
        print("No knowledge references found")
        return 1

    stored = db.get_knowledge_references(inv_id)
    print(f"Stored knowledge references: {len(stored)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
