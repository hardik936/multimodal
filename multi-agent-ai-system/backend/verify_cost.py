import logging
import uuid
from app.costs.tracker import record_llm_usage, get_cost_summary_by_workflow
from app.database import SessionLocal, init_db
from app.costs.models import CostRecord

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_cost")

def verify_cost_tracking():
    # Ensure DB is init
    init_db()
    
    workflow_id = f"test-wf-{uuid.uuid4()}"
    agent_id = "test-agent"
    
    logger.info(f"Testing cost tracking for workflow: {workflow_id}")
    
    # 1. Simulate recording usage
    record_llm_usage(
        workflow_id=workflow_id,
        agent_id=agent_id,
        provider="groq",
        model="groq/mixtral-8x7b-32768",
        tokens_prompt=1000,
        tokens_completion=500
    )
    
    # 2. Verify DB record
    db = SessionLocal()
    record = db.query(CostRecord).filter(CostRecord.workflow_id == workflow_id).first()
    db.close()
    
    if record:
        logger.info(f"PASS: Record found. Cost: ${record.cost_usd:.6f} Tokens: {record.tokens_total}")
    else:
        logger.error("FAIL: No record found in DB.")
        return

    # 3. Verify Aggregation
    summary = get_cost_summary_by_workflow(workflow_id)
    if summary["total_tokens"] == 1500:
        logger.info(f"PASS: Aggregation correct. Total Cost: ${summary['total_cost']:.6f}")
    else:
        logger.error(f"FAIL: Aggregation mismatch. Got {summary}")

if __name__ == "__main__":
    verify_cost_tracking()
