import sqlite3
import os

# Root DB path
root_db = r"C:\Users\HP\Documents\antigravity\multi-agent-ai-system\app.db"
print(f"Inspecting Root DB: {root_db}")

if os.path.exists(root_db):
    try:
        conn = sqlite3.connect(root_db)
        cursor = conn.cursor()
        
        # Check for e02d...
        # Since I don't honestly know the full ID, I'll list recent runs.
        cursor.execute("SELECT id, status, created_at FROM workflow_runs ORDER BY created_at DESC LIMIT 5")
        rows = cursor.fetchall()
        print("Root DB Recent Runs:")
        for row in rows:
            print(row)
        conn.close()
    except Exception as e:
        print(f"Root DB Check Failed: {e}")
else:
    print("Root DB Exists: False")
