import asyncio
import uuid
import time
import yaml
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import func
from opentelemetry import trace

from app.database import SessionLocal
from app.agents.graph import create_graph
from app.eval.formats import EvalCase, EvalSet
from app.eval.store import EvaluationRun, EvaluationResult
from app.eval.matchers import run_matcher
from app.costs.models import CostRecord

# Get tracer
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

async def run_evalcase(
    case: EvalCase, 
    workflow_version: str, 
    run_id: str = None  # The parent EvaluationRun ID (DB ID)
) -> EvaluationResult:
    """
    Executes a single evaluation case against the workflow.
    """
    case_run_id = str(uuid.uuid4()) # Unique ID for this specific execution trace
    start_time = time.time()
    
    # Start Span
    with tracer.start_as_current_span(
        "evaluation.case",
        attributes={
            "case.id": case.id,
            "case.matcher": case.matcher,
            "workflow.version": workflow_version,
            "evaluation.run_id": str(run_id)
        }
    ) as span:
        
        # Prepare Input
        # We assume case.input contains keys that map to AgentState
        # e.g. {"input": "Make a game", "mode": "execution"}
        initial_state = case.input.copy()
        initial_state["workflow_id"] = case_run_id
        
        # Override metadata or config if needed based on `workflow_version`
        # For now, we assume the codebase running IS the version we want to test.
        # In a real deployed environment, we might hit an API endpoint instead.
        # But per requirements ("student-friendly"), we run in-process code.
        
        graph = create_graph()
        
        try:
            # Execute Workflow
            # We use ainvoke to run the graph
            result_state = await graph.ainvoke(initial_state)
            
            final_output = result_state.get("final_output", "")
            if not final_output and result_state.get("messages"):
                # Fallback to last message if final_output empty
                final_output = result_state["messages"][-1].content
                
        except Exception as e:
            logger.error(f"Error running case {case.id}: {e}")
            final_output = ""
            span.record_exception(e)
            
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        # Calculate Cost
        # We perform a DB lookup for all costs associated with this `case_run_id`
        # This assumes `record_llm_usage` was called during execution with this workflow_id/run_id.
        # The graph (AgentState) has `workflow_id`, which `tracker.py` uses.
        cost_usd = 0.0
        db = SessionLocal()
        try:
            total_cost = db.query(func.sum(CostRecord.cost_usd)).filter(
                CostRecord.workflow_id == case_run_id
            ).scalar()
            cost_usd = total_cost or 0.0
        finally:
            db.close()
            
        # Match
        score = run_matcher(case.matcher, case.expected, final_output)
        passed = score >= 1.0 if case.matcher in ["exact", "json_key"] else score >= 0.8 # arbitrary threshold for semantic
        
        # Prepare Result
        metrics = {
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "output_length": len(str(final_output))
        }
        
        eval_result = EvaluationResult(
            run_id=run_id,
            case_id=case.id,
            score=score,
            reason=f"Matcher: {case.matcher}",
            metrics=metrics,
            trace_id=case_run_id
        )
        
        # Update span
        span.set_attribute("evaluation.score", score)
        span.set_attribute("evaluation.cost_usd", cost_usd)
        span.set_attribute("evaluation.passed", passed)
        
        return eval_result

async def run_evalset(
    evalset_path: str,
    workflow_version: str = "custom",
    concurrency: int = 4
) -> int:
    """
    Runs a full evaluation suite. Returns the EvaluationRun DB ID.
    """
    # Load EvalSet
    with open(evalset_path, "r") as f:
        data = yaml.safe_load(f)
    
    # Parse into objects
    # Handle single file containing generic structure
    cases_data = data.get("cases", [])
    cases = [EvalCase(**c) for c in cases_data]
    evalset_name = data.get("name", "unknown")
    workflow_name = data.get("workflow", "unknown")
    
    # Create DB Record
    db = SessionLocal()
    eval_run = EvaluationRun(
        workflow_id=workflow_name,
        candidate_version=workflow_version,
        start_ts=datetime.utcnow()
    )
    db.add(eval_run)
    db.commit()
    db.refresh(eval_run)
    run_id = eval_run.id
    db.close()
    
    # Run Cases Parallel
    # Limit concurrency
    semaphore = asyncio.Semaphore(concurrency)
    
    async def run_with_sem(case):
        async with semaphore:
            return await run_evalcase(case, workflow_version, run_id)

    with tracer.start_as_current_span(
        "evaluation.run",
        attributes={
            "evalset": evalset_name,
            "workflow": workflow_name,
            "version": workflow_version,
            "run_id": str(run_id)
        }
    ):
        results = await asyncio.gather(*[run_with_sem(c) for c in cases])
    
    # Aggregate Rules
    total_score = sum(r.score for r in results)
    avg_score = total_score / len(results) if results else 0.0
    total_cost = sum(r.metrics.get("cost_usd", 0.0) for r in results)
    
    # Pass/Fail (Simple: avg > 0.8)
    # Could be configurable
    passed = avg_score >= 0.85 
    
    # Persist Results
    db = SessionLocal()
    try:
        # Re-fetch run to avoid detached instance issues if needed, or link by ID
        run_record = db.query(EvaluationRun).get(run_id)
        if run_record:
            run_record.end_ts = datetime.utcnow()
            run_record.aggregated_score = avg_score
            run_record.passed = passed
            run_record.total_cost_usd = total_cost
            
            # Save all results
            # We created objects but didn't add them to a session yet
            for r in results:
                # EvaluationResult(run_id=..., ...)
                # Note: r is already an EvaluationResult object instance, but detached
                db.add(r)
                
            db.commit()
            return run_id
    finally:
        db.close()
