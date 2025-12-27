import sqlite3
import datetime

DB_PATH = "backend/app.db"

def inspect_recent_runs():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("--- Recent Workflow Runs ---")
        cursor.execute("SELECT id, status, started_at, completed_at FROM workflow_runs ORDER BY created_at DESC LIMIT 5")
        runs = cursor.fetchall()
        
        if not runs:
            print("No runs found.")
        else:
            for run in runs:
                print(f"ID: {run['id']}, Status: {run['status']}, Started: {run['started_at']}")
        
        print("\n--- Worker Logs (Last 5) ---")
        # Assuming there is a logs table
        try:
            cursor.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 5")
            logs = cursor.fetchall()
            for log in logs:
                print(f"{log['timestamp']} - {log['level']}: {log['message']}")
        except:
            print("No logs table or query failed.")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_recent_runs()
