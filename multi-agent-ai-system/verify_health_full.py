import sys
import os
import requests
import sqlite3
# import pandas as pd # Removed

from datetime import datetime

# Path setup
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from backend.app.config import settings

print(f"=== HEALTH CHECK ===")
print(f"Time: {datetime.now()}")
print(f"Config DB URL: {settings.DATABASE_URL}")

# 1. API Check
try:
    r = requests.get("http://127.0.0.1:8000/health", timeout=2)
    print(f"API Health: {r.status_code} - {r.json()}")
except Exception as e:
    print(f"API Health: FAILED - {e}")

# 2. DB Inspection
db_path = settings.DATABASE_URL.replace("sqlite:///", "")
print(f"Inspecting DB: {db_path}")

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        # Check recent runs
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, created_at, started_at, completed_at FROM workflow_runs ORDER BY created_at DESC LIMIT 5")
        rows = cursor.fetchall()
        print("\nRecent Workflow Runs:")
        for row in rows:
            print(row)
        conn.close()
    except Exception as e:
        print(f"DB Inspection Failed: {e}")
else:
    print(f"DB File {db_path} does not exist!")

# 3. Check Backend DB (Alternative)
backend_db = os.path.join(os.getcwd(), "app.db")
print(f"\nInspecting Backend DB (CWD): {backend_db}")
if os.path.exists(backend_db):
    try:
        conn = sqlite3.connect(backend_db)
        cursor = conn.cursor()
        # Search by partial ID
        cursor.execute("SELECT id, status, input_data, created_at FROM workflow_runs WHERE id LIKE 'e02d%'")
        found_runs = cursor.fetchall()
        print(f"Found User Runs: {found_runs}")
        
        if found_runs:
            run_id = found_runs[0][0]
            last_run = found_runs[0]
            print(f"Checking Logs for Run {run_id}...")
            # Check logs table (assuming 'logs' table with 'run_id', 'level', 'message', 'error')
            # First checking schema of logs
            cursor.execute("PRAGMA table_info(logs)")
            print(f"Logs Schema: {cursor.fetchall()}")
            
            cursor.execute(f"SELECT level, message FROM logs WHERE run_id='{run_id}'")
            logs = cursor.fetchall()
            print("Logs:")
            for log in logs:
                print(log)
        conn.close()
    except Exception as e:
        print(f"Backend DB Inspection Failed: {e}")
else:
    print("Backend DB File does not exist!")

# 4. Enqueue Test Workflow Task
print("\nEnqueuing Test Workflow Task...")
try:
    # Ensure backend dir is in path to import 'app' directly
    backend_path = os.path.join(os.getcwd(), 'backend')
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    
    # Import exactly as worker does (app.tasks...)
    from app.tasks.huey_tasks import execute_workflow_task
    import uuid
    
    test_run_id = str(uuid.uuid4())
    print(f"Test Run ID: {test_run_id}")
    
    # Needs to be in DB first? The worker fetches it?
    # Worker: run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    # So we need to insert it into DB first.
    # We can use the connection we already have to backend_db.
    
    conn = sqlite3.connect(backend_db)
    cursor = conn.cursor()
    # Insert dummy run
    cursor.execute(f"INSERT INTO workflow_runs (id, workflow_id, status, input_data, created_at, updated_at, started_at) VALUES ('{test_run_id}', 'default', 'pending', '{{}}', '{datetime.now()}', '{datetime.now()}', '{datetime.now()}')")
    conn.commit()
    conn.close()
    
    # Enqueue
    task = execute_workflow_task(
        run_id=test_run_id,
        workflow_id="default",
        workflow_config={},
        input_data={"request": "Test Potato Recipe"}
    )
    print(f"Task Enqueued: {task.id}")
except Exception as e:
    print(f"Enqueue Failed: {e}")
    import traceback
    traceback.print_exc()
