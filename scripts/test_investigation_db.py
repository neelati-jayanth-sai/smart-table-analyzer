"""Smoke test for investigation database operations."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import Finding, InvestigationDb


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = repo_root / "data" / "investigation_test.db"
    db_path.unlink(missing_ok=True)

    db = InvestigationDb(db_path)

    inv_id = db.create_investigation(
        run_id=str(uuid.uuid4()),
        table_name="eds_it_dev.elh_comn.test_table",
        catalog_name="eds_it_dev",
        schema_name="elh_comn",
        max_checks=50,
        snapshot_id="1234567890",
    )
    print(f"Created investigation: {inv_id}")

    db.record_baseline_score(
        inv_id,
        overall_score=42.0,
        dimensions={
            "file_size": 30.0,
            "scan_efficiency": 60.0,
            "delete_overhead": 50.0,
            "manifest_organization": 40.0,
            "partition_aware": 45.0,
            "sort_order": 35.0,
        },
    )
    print("Recorded baseline score")

    db.record_knowledge_fetch(inv_id, 1, "iceberg", "file-sizing-best-practices", "a3f8e91c")
    db.record_knowledge_fetch(inv_id, 1, "runbooks", "daily-maintenance-schedule", "7b2d4e9a")
    print("Recorded knowledge fetches")

    trail_id = db.record_query(
        inv_id,
        check_num=1,
        node_name="execute_query",
        query_text="SELECT * FROM table",
        rewritten_query="SELECT * FROM table.snapshot_1234567890",
        query_result={"rows": [{"col": "value"}], "row_count": 1},
        execution_status="success",
        execution_time_ms=1234,
        error_message=None,
    )
    print(f"Recorded query trail: {trail_id}")

    finding = Finding(
        check_num=1,
        question="Are files correctly sized?",
        exact_result="50% of files are below 128 MB.",
        verdict="found",
        rationale="Many small files cause manifest bloat.",
        evidence_ids=["trail:1", "knowledge:iceberg/file-sizing-best-practices@a3f8e91c"],
        recommendation="Run data file rewrite with 256 MB target.",
        alternatives=["Do nothing", "Use 512 MB target"],
        validated=True,
    )
    finding_id = db.record_finding(inv_id, finding)
    print(f"Recorded finding: {finding_id}")

    db.record_hook_violation(inv_id, 2, "DROP TABLE test", "ReadOnlyHook", "DROP not allowed")
    print("Recorded hook violation")

    db.complete_investigation(inv_id, status="completed")
    print("Marked investigation completed")

    investigation = db.get_investigation(inv_id)
    assert investigation is not None
    assert investigation.status == "completed"
    assert investigation.baseline_score is not None
    assert investigation.baseline_score["overall"] == 42.0
    print(f"Retrieved investigation: {investigation.run_id}")

    findings = db.list_findings(inv_id)
    assert len(findings) == 1
    assert findings[0].evidence_ids == finding.evidence_ids
    print(f"Retrieved {len(findings)} finding(s)")

    print("\n✅ All database operations verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
