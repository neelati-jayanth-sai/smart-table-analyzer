"""List all investigations in the database."""
import sqlite3
import sys

conn = sqlite3.connect("data/investigation.db")
conn.row_factory = sqlite3.Row

print("=== Recent Investigations ===\n")
rows = conn.execute(
    "SELECT investigation_id, table_name, status, started_at, completed_at FROM investigations ORDER BY investigation_id DESC LIMIT 20"
).fetchall()
for r in rows:
    print(f"ID: {r['investigation_id']}, Table: {r['table_name']}, Status: {r['status']}, Started: {r['started_at']}, Completed: {r['completed_at']}")

print("\n=== Finding Counts ===\n")
counts = conn.execute(
    "SELECT investigation_id, COUNT(*) as cnt FROM investigation_findings GROUP BY investigation_id"
).fetchall()
for c in counts:
    print(f"Investigation {c['investigation_id']}: {c['cnt']} findings")
