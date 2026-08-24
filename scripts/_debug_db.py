"""Debug: read all findings and trail queries for a given investigation."""
import sqlite3
import json
import sys

inv_id = int(sys.argv[1]) if len(sys.argv) > 1 else 65
conn = sqlite3.connect("data/investigation.db")
conn.row_factory = sqlite3.Row

print(f"=== Investigation {inv_id} findings ===\n")
findings = conn.execute(
    "SELECT check_num, check_type, verdict, exact_result, rationale, recommendation "
    "FROM investigation_findings WHERE investigation_id=? ORDER BY check_num", (inv_id,)
).fetchall()
for f in findings:
    print(f"Check {f['check_num']} ({f['check_type']}) — {f['verdict']}")
    print(f"  exact_result: {str(f['exact_result'])[:300]}")
    print(f"  rationale: {f['rationale']}")
    print(f"  recommendation: {str(f['recommendation'])[:200]}")
    print()

print("\n=== Trail queries ===\n")
trail = conn.execute(
    "SELECT check_num, node_name, query_text, execution_status, execution_time_ms "
    "FROM investigation_trail WHERE investigation_id=? ORDER BY trail_id", (inv_id,)
).fetchall()
for t in trail:
    print(f"Check {t['check_num']} [{t['node_name']}] status={t['execution_status']} "
          f"time={t['execution_time_ms']}ms")
    if t['query_text']:
        print(f"  SQL: {t['query_text'][:200]}")
