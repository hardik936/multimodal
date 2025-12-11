import logging
import json
from sqlalchemy import func, desc
from app.database import SessionLocal
from app.costs.models import CostRecord
from app.costs.pricing import estimate_cost_usd
from app.observability.tracing import get_tracer, add_span_attributes, trace_span
from app.config import settings

logger = logging.getLogger(__name__)

# Check for config flag
COST_TRACKING_ENABLED = getattr(settings, "COST_TRACKING_ENABLED", True)

def record_llm_usage(
    workflow_id: str = None,
    run_id: str = None,
    agent_id: str = None,
    tool_name: str = None,
    provider: str = "groq",
    model: str = "unknown",
    tokens_prompt: int = 0,
    tokens_completion: int = 0,
    metadata: dict = None
):
    """
    Record LLM usage and cost to the database and current trace span.
    """
    if not COST_TRACKING_ENABLED:
        return

    tokens_total = tokens_prompt + tokens_completion
    cost_usd = estimate_cost_usd(model, tokens_prompt, tokens_completion, provider)
    
    # Add to tracing immediately
    # We assume we are inside a span if this is called during execution
    try:
         # Standard semantic conventions or custom
        add_span_attributes(None, { # None uses current span
            "llm.tokens.prompt": tokens_prompt,
            "llm.tokens.completion": tokens_completion,
            "llm.tokens.total": tokens_total,
            "llm.cost.usd": cost_usd,
            "llm.model": model,
            "llm.provider": provider
        })
    except Exception:
        pass # Tracing might fail or not be active

    # Persist to DB
    try:
        db = SessionLocal()
        record = CostRecord(
            workflow_id=workflow_id,
            run_id=run_id,
            agent_id=agent_id,
            tool_name=tool_name,
            provider=provider,
            model=model,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            tokens_total=tokens_total,
            cost_usd=cost_usd,
            metadata_json=json.dumps(metadata) if metadata else None
        )
        db.add(record)
        db.commit()
        db.close()
        
        logger.info(f"Recorded LLM Cost: ${cost_usd:.6f} (Tokens: {tokens_total}) for {agent_id or 'unknown'}")
        
    except Exception as e:
        logger.error(f"Failed to record LLM cost: {e}")


def get_cost_summary_by_workflow(workflow_id: str):
    db = SessionLocal()
    try:
        query = db.query(
            func.sum(CostRecord.cost_usd).label("total_cost"),
            func.sum(CostRecord.tokens_total).label("total_tokens")
        ).filter(CostRecord.workflow_id == workflow_id)
        
        result = query.first()
        return {
            "workflow_id": workflow_id,
            "total_cost": result.total_cost or 0.0,
            "total_tokens": result.total_tokens or 0
        }
    finally:
        db.close()

def get_cost_summary_by_agent(agent_id: str):
    db = SessionLocal()
    try:
        query = db.query(
            func.sum(CostRecord.cost_usd).label("total_cost"),
            func.sum(CostRecord.tokens_total).label("total_tokens")
        ).filter(CostRecord.agent_id == agent_id)
        
        result = query.first()
        return {
            "agent_id": agent_id,
            "total_cost": result.total_cost or 0.0,
            "total_tokens": result.total_tokens or 0
        }
    finally:
        db.close()

def get_top_expensive_workflows(limit: int = 10):
    db = SessionLocal()
    try:
        # Group by workflow_id
        current_costs = db.query(
            CostRecord.workflow_id,
            func.sum(CostRecord.cost_usd).label("total_cost")
        ).group_by(CostRecord.workflow_id).order_by(desc("total_cost")).limit(limit).all()
        
        return [{"workflow_id": r.workflow_id, "total_cost": r.total_cost} for r in current_costs]
    finally:
        db.close()
