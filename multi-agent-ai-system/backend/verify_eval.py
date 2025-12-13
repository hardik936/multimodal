import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.eval.runner import run_evalset
from app.eval.reporting import generate_report
from app.database import SessionLocal, engine
from app.models.base import Base
from app.eval.store import EvaluationRun, EvaluationResult

def verify_eval():
    print("🚀 Starting Evaluation Harness Verification...")
    
    # 1. Ensure DB tables exist
    # In a real migration setup, this is handled by alembic, but for smoke test we force it
    # to ensure the new models are present if migration wasn't run.
    # Note: This might be redundant if user ran docker-compose up which runs migrations,
    # but safe for local script execution.
    from app.eval.store import Base as EvalBase
    EvalBase.metadata.create_all(bind=engine)
    
    # 2. Run EvalSet
    evalset_path = "examples/evalsets/general_agent/smoke.yaml"
    if not os.path.exists(evalset_path):
        print(f"❌ Error: {evalset_path} not found.")
        sys.exit(1)
        
    print(f"Running evalset: {evalset_path}")
    try:
        run_id = asyncio.run(run_evalset(evalset_path, workflow_version="smoke_test_v1"))
        print(f"✅ Run completed. Run ID: {run_id}")
    except Exception as e:
        print(f"❌ Run failed: {e}")
        # Print stack trace
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    # 3. Verify DB Records
    db = SessionLocal()
    run = db.query(EvaluationRun).get(run_id)
    if not run:
        print("❌ Error: EvaluationRun record not found in DB.")
        sys.exit(1)
        
    results = db.query(EvaluationResult).filter(EvaluationResult.run_id == run_id).all()
    print(f"Found {len(results)} results in DB.")
    
    if len(results) == 0:
        print("❌ Error: No results saved.")
        sys.exit(1)
        
    print(f"Run Score: {run.aggregated_score}")
    print(f"Run Cost: ${run.total_cost_usd}")
    
    # 4. Generate Report
    summary, md = generate_report(run_id)
    print("\nReport Summary:")
    print(summary)
    
    if summary["cases_passed"] > 0:
        print("\n✅ Verification Passed: System is recording runs and results.")
    else:
        print("\n⚠️  Verification Warning: Runs recorded but cases might have failed matching (expected if 'Paris' not found).")

    db.close()

if __name__ == "__main__":
    verify_eval()
