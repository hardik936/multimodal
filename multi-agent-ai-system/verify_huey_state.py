import sqlite3
import os

db_path = r"C:\Users\HP\Documents\antigravity\multi-agent-ai-system\backend\huey.db"
print(f"Inspecting Huey DB: {db_path}")

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # List tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        
        # Check task count (assuming 'tasks' table or similar, depends on Huey schema)
        # SqliteHuey usually uses: 'schedule', 'task', 'kv'
        try:
            cursor.execute("SELECT count(*) FROM task")
            count = cursor.fetchone()[0]
            print(f"Pending Tasks in Queue: {count}")
            
            if count > 0:
                 cursor.execute("SELECT * FROM task LIMIT 5")
                 print("Sample Tasks:", cursor.fetchall())
        except Exception as e:
            print(f"Could not read 'task' table: {e}")

        conn.close()
    except Exception as e:
        print(f"Inspection Error: {e}")
else:
    print("Huey DB does not exist")
