"""End-to-end test for the full investigation CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv

load_dotenv(repo_root / ".env", override=True)

from src.database import InvestigationDb
from src.validation import ClaimValidator


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="End-to-end investigation test")
    parser.add_argument(
        "--table",
        default="eds_it_dev.elh_comn.usdm_asst_cust_fact_prod_to_dev",
        help="Target IOMETE table",
    )
    parser.add_argument("--max-checks", type=int, default=3, help="Maximum checks")
    parser.add_argument("--db", default="data/investigation.db", help="SQLite database path")
    return parser.parse_args()


def _run_investigation(table: str, max_checks: int) -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        "scripts/run_investigation.py",
        "--table",
        table,
        "--max-checks",
        str(max_checks),
    ]
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, result.stdout, result.stderr


def _find_report_path(stdout: str) -> Path | None:
    match = re.search(r"Report written to:\s*(.+)", stdout)
    if match:
        return repo_root / match.group(1).strip()
    return None


def _get_latest_json_report() -> Path | None:
    reports_dir = repo_root / "reports"
    if not reports_dir.exists():
        return None
    json_files = sorted(reports_dir.glob("investigation_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return json_files[0] if json_files else None


def _load_report(report_path: Path) -> dict:
    with report_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    args = _parse_args()

    print(f"Running end-to-end investigation on {args.table} (max_checks={args.max_checks})...")
    exit_code, stdout, stderr = _run_investigation(args.table, args.max_checks)

    if exit_code != 0:
        print("CLI failed")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        return 1

    report_path = _find_report_path(stdout)
    json_path = None
    if report_path is not None:
        json_path = report_path.with_suffix(".json")
    if json_path is None or not json_path.exists():
        json_path = _get_latest_json_report()
    if json_path is None:
        print("No JSON report file found")
        return 1

    if not json_path.exists() or json_path.stat().st_size == 0:
        print(f"JSON report file is missing or empty: {json_path}")
        return 1

    report = _load_report(json_path)
    summary = report.get("summary", {})
    investigation_id = report["investigation_id"]

    print(f"Loaded report for investigation {investigation_id} from {json_path}")
    print(f"Total findings: {summary.get('total_findings')}")
    print(f"Validated findings: {summary.get('validated_findings')}")
    print(f"Hook violations: {summary.get('hook_violations')}")
    print(f"Total queries: {summary.get('total_queries')}")

    if summary.get("validated_findings", 0) < 1:
        print("Expected at least one validated finding")
        return 1

    db = InvestigationDb(repo_root / args.db)
    validator = ClaimValidator(db)
    findings = db.list_findings(investigation_id)
    all_valid = True
    for finding in findings:
        result = validator.validate(investigation_id, finding)
        if not result.valid:
            print(f"Finding {finding.check_num} has invalid evidence: {result.errors}")
            all_valid = False

    if not all_valid:
        print("Evidence validation failed")
        return 1

    max_allowed_violations = 2
    if summary.get("hook_violations", 0) > max_allowed_violations:
        print(f"Too many hook violations: {summary['hook_violations']} (max allowed: {max_allowed_violations})")
        return 1

    print("\nEnd-to-end test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
