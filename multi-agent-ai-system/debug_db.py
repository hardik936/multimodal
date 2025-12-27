import sqlite3
import json
import os

DB_PATH = "backend/app.db"

def inspect_run(partial_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print(f"Searching for run with ID starting with: {partial_id}")
        cursor.execute("SELECT * FROM workflow_runs WHERE id LIKE ?", (f"{partial_id}%",))
        runs = cursor.fetchall()
        
        if not runs:
            print("No run found.")
            return

        for run in runs:
            print(f"\nExample Run ID: {run['id']}")
            print(f"Status: {run['status']}")
            print(f"Created At: {run['created_at']}")
            print(f"Started At: {run['started_at']}")
            print(f"Completed At: {run['completed_at']}")
            
            # Check for events associated with this run?
            # Assuming there is an events table or logs table.
            # Let's check tables first.
            
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("\nTables:", [t['name'] for t in tables])

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_run("d529a43d")
