import sqlite3
import sys
import json

inv_id = 71
conn = sqlite3.connect("data/investigation.db")

print("=== Knowledge fetched for Check 2 (partition_suggestions) ===")
rows = conn.execute(
    "SELECT source, topic_path FROM knowledge_references WHERE investigation_id=? AND check_num=2",
    (inv_id,)
).fetchall()

if not rows:
    print("No knowledge referenced directly by check_num=2.")
    print("Let's check all knowledge fetched in inv 71:")
    rows = conn.execute(
        "SELECT check_num, source, topic_path FROM knowledge_references WHERE investigation_id=?",
        (inv_id,)
    ).fetchall()
    
for r in rows:
    print(r)
