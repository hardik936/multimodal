import sys
import os
import asyncio
import yaml

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.database import init_db, SessionLocal
from app.eval.runner import run_evalset
from app.eval.store import EvaluationRun, EvaluationResult

def create_dummy_evalset():
    data = {
        "name": "Smoke Test",
        "workflow": "default",
        "cases": [
            {
                "id": "case_smoke_1",
                "input": {"input": "Say hello", "mode": "execution", "language": "python"},
                "expected": "hello", # Simple contains match expected?
                "matcher": "contains"
            }
        ]
    }
    with open("smoke_test_evalset.yaml", "w") as f:
        yaml.dump(data, f)
    return "smoke_test_evalset.yaml"

async def main():
    print("Initializing DB...")
    init_db()
    
    print("Creating evalset...")
    path = create_dummy_evalset()
    
    print("Running evalset...")
    try:
        run_id = await run_evalset(path)
        print(f"Run ID: {run_id}")
    except Exception as e:
        print(f"Run failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Check DB
    db = SessionLocal()
    run = db.query(EvaluationRun).get(run_id)
    print(f"Run Status: Passed={run.passed}, Score={run.aggregated_score}")
    
    results = db.query(EvaluationResult).filter(EvaluationResult.run_id == run_id).all()
    for r in results:
        print(f"Case {r.case_id}: Score={r.score} ({r.reason})")
        print(f"Metrics: {r.metrics}")

    if run.passed is not None:
        print("SUCCESS: Evaluation checked run complete.")
    else:
        print("FAILURE: Run did not complete properly.")

if __name__ == "__main__":
    asyncio.run(main())
