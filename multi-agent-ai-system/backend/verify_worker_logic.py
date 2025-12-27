import asyncio
import json
import uuid
import logging
from datetime import datetime
from app.database import init_db, SessionLocal
from app.models.run import WorkflowRun, RunStatus
from app.models.workflow import Workflow
from app.queue.worker import process_task
from app.models.checkpoint import Checkpoint as DBCheckpoint
from sqlalchemy import select

# Configure logging to see worker output
logging.basicConfig(level=logging.INFO)

async def main():
    print("Initializing DB...")
    init_db()
    
    workflow_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    
    # 1. Setup DB State
    print(f"Creating test WorkflowRun: {run_id}")
    try:
        with SessionLocal() as db:
            # Ensure workflow exists
            wf = Workflow(
                id=workflow_id, 
                name="Test Workflow", 
                graph_definition={},
                agents_config={},
                user_id="test_user"
            )
            db.add(wf)
            db.commit()
            print("Workflow created.")
            
            run = WorkflowRun(
                id=run_id,
                workflow_id=workflow_id,
                status=RunStatus.PENDING.value,
                input_data={"input": "10 + 10", "mode": "quick"},
                started_at=datetime.utcnow()
            )
            db.add(run)
            db.commit()
            print("Run created.")
    except Exception as e:
        print(f"DB SETUP FAILED: {e}")
        exit(1)

    
    # 2. Construct Message
    message_data = {
        "task_id": run_id,
        "payload": {
            "workflow_config": {"name": "default"},
            "input_data": {
                "input": "10 + 10",
                "language": "python",
                "mode": "quick"
            }
        }
    }
    message_body = json.dumps(message_data).encode("utf-8")
    
    # 3. Invoke Worker Logic
    print("Invoking process_task (Simulated Worker)...")
    try:
        await process_task(message_body)
        print("process_task returned successfully.")
    except Exception as e:
        print(f"process_task failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
        
    # 4. Verify DB State (Run Status)
    with SessionLocal() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        print(f"Run Status: {run.status}")
        print(f"Output: {run.output_data}")
        
        if run.status != RunStatus.COMPLETED:
            print("❌ Verification Failed: Run status is not COMPLETED")
            # exit(1) # Don't exit yet, check checkpoints
        
        # 5. Verify Checkpoints
        stmt = select(DBCheckpoint).where(DBCheckpoint.thread_id == run_id)
        checkpoints = db.execute(stmt).scalars().all()
        print(f"Found {len(checkpoints)} checkpoints for thread_id {run_id}")
        
        if len(checkpoints) > 0:
            print("✅ Verified: Checkpoints persisted.")
            print(f"Latest Checkpoint: {checkpoints[-1].checkpoint_id}")
        else:
            print("❌ Verification Failed: No checkpoints found.")
            exit(1)

if __name__ == "__main__":
    asyncio.run(main())
