import asyncio
import uuid
import sys
import os
from datetime import datetime, timezone

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Mock environment variables for testing
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite:///backend/app.db"
os.environ["HUEY_IMMEDIATE"] = "True"

from app.database import init_db, SessionLocal
from app.models.run import WorkflowRun, RunStatus
from app.models.workflow import Workflow
from app.tasks.huey_tasks import execute_workflow_task

def setup_test_data():
    print("Setting up test data...")
    init_db()
    db = SessionLocal()
    
    # 1. Ensure a workflow exists
    wf_id = "default"
    wf = db.query(Workflow).filter(Workflow.id == wf_id).first()
    if not wf:
        wf = Workflow(
            id=wf_id,
            name="Default Workflow",
            graph_definition={},
            agents_config={},
            user_id="test_user"
        )
        db.add(wf)
        db.commit()
        print(f"Created workflow: {wf_id}")
    
    # 2. Create a Run
    run_id = str(uuid.uuid4())
    run = WorkflowRun(
        id=run_id,
        workflow_id=wf_id,
        status=RunStatus.PENDING,
        input_data={"input": "find me potato recipe", "mode": "full"},
        started_at=datetime.now(timezone.utc)
    )
    db.add(run)
    db.commit()
    print(f"Created run: {run_id}")
    return run_id, wf_id

def run_reproduction():
    run_id, wf_id = setup_test_data()
    
    print(f"\nExecuting Huey task for run {run_id}...")
    try:
        # Call the task function directly (not via huey.task proxy logic)
        execute_workflow_task(
            run_id=run_id,
            workflow_id=wf_id,
            workflow_config={},
            input_data={"input": "find me potato recipe", "mode": "full"}
        )
        print("\nTask call finished.")
    except Exception as e:
        print(f"\nCaught top-level exception: {e}")

if __name__ == "__main__":
    run_reproduction()
