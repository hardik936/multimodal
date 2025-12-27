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
    init_db()
    db = SessionLocal()
    
    wf_id = "default"
    wf = db.query(Workflow).filter(Workflow.id == wf_id).first()
    if not wf:
        wf = Workflow(id=wf_id, name="Default", graph_definition={}, agents_config={}, user_id="test")
        db.add(wf)
        db.commit()
    
    run_id = str(uuid.uuid4())
    run = WorkflowRun(
        id=run_id,
        workflow_id=wf_id,
        status=RunStatus.PENDING,
        input_data={"input": "tell me a short joke about coffee", "mode": "full"},
        created_at=datetime.now(timezone.utc)
    )
    db.add(run)
    db.commit()
    return run_id, wf_id

async def run_test():
    run_id, wf_id = setup_test_data()
    print(f"Executing task for run {run_id}...")
    
    # Call the task function directly
    execute_workflow_task(
        run_id=run_id,
        workflow_id=wf_id,
        workflow_config={},
        input_data={"input": "tell me a short joke about coffee", "mode": "full"}
    )
    
    # Verify result in DB
    db = SessionLocal()
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    print(f"Final Status: {run.status}")
    if run.status == RunStatus.COMPLETED:
        print("SUCCESS: Workflow completed!")
    else:
        print(f"FAILURE: Workflow status is {run.status}. Error: {run.error_message}")
    db.close()

if __name__ == "__main__":
    asyncio.run(run_test())
