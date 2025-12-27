import sys
sys.path.append('.')

from app.database import SessionLocal
from app.models.workflow import Workflow
from app.models.run import WorkflowRun

db = SessionLocal()

try:
    # Test query
    workflow = db.query(Workflow).first()
    if workflow:
        print(f"Workflow ID: {workflow.id}")
        print(f"Workflow Name: {workflow.name}")
        print("Attempting to access runs...")
        runs = workflow.runs
        print(f"Runs count: {len(runs)}")
        print("SUCCESS!")
    else:
        print("No workflows found")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
