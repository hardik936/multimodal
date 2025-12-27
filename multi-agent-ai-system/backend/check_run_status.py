from app.database import SessionLocal
from app.models.run import WorkflowRun
from datetime import datetime, timezone

def check_runs():
    db = SessionLocal()
    try:
        print("Checking for RUNNING tasks:")
        running = db.query(WorkflowRun).filter(WorkflowRun.status == "running").all()
        for r in running:
            print(f"RUNNING: {r.id} | Started: {r.started_at}")
            
        print("\nRecent 10 tasks:")
        runs = db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(10).all()
        print(f"{'ID':<40} | {'Status':<10} | {'Created At (UTC)':<25} | {'Error'}")
        print("-" * 120)
        for r in runs:
            print(f"{r.id:<40} | {r.status:<10} | {str(r.created_at):<25} | {r.error_message}")
    finally:
        db.close()

if __name__ == "__main__":
    check_runs()
