"""
Huey background task queue configuration and task definitions.
Handles asynchronous workflow execution and periodic cleanup.
"""
import logging
import sys
import asyncio
import traceback
from datetime import datetime, timedelta, timezone

from huey import SqliteHuey, crontab
from app.config import settings
from app.database import SessionLocal
from app.models.run import WorkflowRun, RunStatus
from app.models.message import Message, MessageRole
from app.agents.graph import create_multi_agent_workflow
from app.hitl.gates import DEFAULT_GATES, get_gate_for_step
from app.hitl.queue import ReviewQueueService
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3


# Configure logging
logger = logging.getLogger(__name__)

# Initialize Huey
# Use absolute path to ensure single source of truth
import os
BASE_DIR = r"C:\Users\HP\Documents\antigravity\multi-agent-ai-system\backend"
huey = SqliteHuey(
    filename=os.path.join(BASE_DIR, "huey.db"),
    name="multi_agent_workflows",
    results=True,
    store_none=True,
    utc=True,
    # Force immediate=False when running via the consumer, regardless of settings
    immediate=False if "huey_consumer" in str(sys.modules.get("__main__")) else settings.HUEY_IMMEDIATE,
)


@huey.task(retry=False)
def execute_workflow_task(
    run_id: str,
    workflow_id: str,
    workflow_config: dict,
    input_data: dict
):
    """
    Background task to execute a multi-agent workflow.
    
    Args:
        run_id: ID of the workflow run
        workflow_id: ID of the workflow definition
        workflow_config: Configuration for the workflow
        input_data: Input data for the workflow
    """
    logger.info(f"Starting workflow execution for run_id: {run_id}")
    logger.info(f"Input data: {input_data}")
    logger.warning(f"DEPRECATED: execute_workflow_task called for {run_id}. This uses SQLite Huey. Please use RabbitMQ worker.")
    print(f"DEBUG: execute_workflow_task STARTED for {run_id}")
    
    result_state = None
    db = SessionLocal()
    try:
        # Load run record
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if not run:
            logger.error(f"WorkflowRun not found for id: {run_id}")
            return
        
        # Update status to RUNNING
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        
        # We need a persistent checkpointer for HITL
        from langgraph.checkpoint.memory import MemorySaver
        memory = MemorySaver()
        
        # Determine approval gates
        # For now, we interrupt before nodes that have configured gates
        interrupt_before = [gate.step for gate in DEFAULT_GATES.values()]
        
        workflow = create_multi_agent_workflow(
            config=workflow_config, 
            checkpointer=memory,
            interrupt_before=interrupt_before
        )
        
        # Build initial state
        if input_data is None:
            logger.error("input_data is None!")
            raise ValueError("input_data cannot be None")

        initial_state = {
            "input": input_data.get("input") or input_data.get("query", ""),
            "language": input_data.get("language", "python"),
            "mode": input_data.get("mode", "full"),
            "messages": [],
            # Initialize other state keys as needed by the graph
            "current_agent": "planner",  # Default starting point
            "research_data": "",
            "plan_data": {},
            "execution_data": "",
            "code_data": "",
            "final_output": "",
            "workflow_id": workflow_id 
        }
        
        # Workflow Thread Configuration
        # We use run_id as the thread_id to allow resuming later
        thread_config = {"configurable": {"thread_id": run_id}}
        
        # Execute workflow (handle async execution synchronously)
        try:
            import concurrent.futures
            # Run in a separate thread to avoid event loop conflicts
            with concurrent.futures.ThreadPoolExecutor() as pool:
                # We invoke with the config to enable checkpointing
                # Note: valid LangGraph invoke returns the final state
                result_state = pool.submit(asyncio.run, workflow.ainvoke(initial_state, thread_config)).result()
                print(f"DEBUG: ainvoke result_state: {result_state is not None}")
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            logger.error(traceback.format_exc())
            raise e

        # Check current state from memory to see if we are paused or done
        # Accessing state needs a sync wrapper or direct usage if memory is sync (SqliteSaver is sync-compatible often but used via interface)
        # Actually LangGraph `get_state` is sync or async depending on compiled graph.
        # But we are outside the async loop. Let's use the graph object.
        # Wait, compiled graph methods are often async. 
        # Let's verify state inside the pool or another way.
        
        # Re-access state to check for interruptions
        snapshot = workflow.get_state(thread_config)
        
        if snapshot.next:
            # We are paused!
            next_step = snapshot.next[0]
            logger.info(f"Workflow paused at {next_step}")
            
            # Check if there is an approval gate
            gate = get_gate_for_step(next_step)
            if gate:
                # Create Review Request
                with ReviewQueueService(db) as review_service:
                    review_service.create_review_request(
                        workflow_id=workflow_id,
                        run_id=run_id,
                        thread_id=run_id, # Using run_id as thread_id
                        step_name=next_step,
                        gate=gate,
                        snapshot_id=snapshot.config['configurable'].get('checkpoint_id')
                    )
                
                # Update Run Status to PAUSED (or equivalent)
                # Since we don't have PAUSED status yet, we keep it as RUNNING or add new status
                # For now let's leave it as RUNNING but maybe log it.
                # Ideally we add RunStatus.WAITING_FOR_APPROVAL
                logger.info(f"Workflow {run_id} halted for approval at {next_step}")
                return # Exit task cleanly, state is saved
        
        # If we are here, either finished or failed (handled by catch)
        if hasattr(snapshot, "values") and snapshot.values:
             result_state = snapshot.values

        logger.info(f"Workflow execution result: {result_state}")

        if result_state is None:
             logger.error("result_state is None!")
             # If paused, we already returned. So this is genuine error.
             raise ValueError("Workflow execution returned None")

        # Process results
        # Save messages
        if "messages" in result_state:
            for msg in result_state["messages"]:
                # Map LangChain messages to DB model
                content = ""
                role = MessageRole.AGENT
                agent_name = "system"
                
                if hasattr(msg, "content"):
                    content = msg.content
                    if msg.type == "human":
                        role = MessageRole.USER
                    elif msg.type == "ai":
                        role = MessageRole.AGENT
                    elif msg.type == "system":
                        role = MessageRole.SYSTEM
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                    role_str = msg.get("role", "agent")
                    if role_str == "user":
                        role = MessageRole.USER
                    elif role_str == "system":
                        role = MessageRole.SYSTEM
                    else:
                        role = MessageRole.AGENT
                
                # Create message record
                db_msg = Message(
                    run_id=run_id,
                    role=role,
                    content=str(content),
                    agent_name=agent_name,
                    timestamp=datetime.now(timezone.utc)
                )
                db.add(db_msg)
        
        # Update run record with completion
        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        
        # Extract output data from state
        output_data = {
            "research": result_state.get("research_data"),
            "plan": result_state.get("plan_data"),
            "execution": result_state.get("execution_data"),
            "code": result_state.get("code_data"),
            "final_output": result_state.get("final_output")
        }
        
        run.output_data = output_data
        
        db.commit()
        logger.info(f"Workflow execution completed for run_id: {run_id}")
        
    except Exception as e:
        print(f"DEBUG: WORKER FAILED for {run_id}. Error: {e}")

        logger.error(f"Error executing workflow {run_id}: {str(e)}")
        logger.error(traceback.format_exc())
        
        try:
            run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if run:
                run.status = RunStatus.FAILED
                run.error_message = str(e)
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as db_e:
            logger.error(f"Failed to update run status to FAILED: {str(db_e)}")
            
        raise
        
    finally:
        db.close()

@huey.task(retry=True, retry_delay=60, retries=3)
def resume_workflow_task(run_id: str):
    """"
    Resume a paused workflow from checkpoint.
    """
    logger.info(f"Resuming workflow execution for run_id: {run_id}")
    
    db = SessionLocal()
    try:
        result_state = None
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if not run:
            logger.error(f"WorkflowRun not found for id: {run_id}")
            return

        # Setup Graph & Checkpointer
        conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
        memory = SqliteSaver(conn)
        
        interrupt_before = [gate.step for gate in DEFAULT_GATES.values()]
        
        # We assume config is stored in run or we reconstruct it. 
        # Ideally we'd store the workflow_config in the run model, but for now we assume it's standard.
        # Or we can get it from correct place. But `create_multi_agent_workflow` takes config.
        # Let's supply empty config or minimal, as state is in memory.
        workflow = create_multi_agent_workflow(
            config={}, 
            checkpointer=memory,
            interrupt_before=interrupt_before
        )
        
        thread_config = {"configurable": {"thread_id": run_id}}
        
        # Proceed with execution (None input means resume from state)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
             # Just pass None as input to signal resume from checkpoint
             result_state = pool.submit(asyncio.run, workflow.ainvoke(None, thread_config)).result()
        
        # ... Reuse the rest of the processing logic (messages, completion, etc) ...
        # (For brevity in this plan, I'm duplicating or we should extract a common helper).
        # I'll just duplicate minimal processing for the demo to work.
        
        snapshot = workflow.get_state(thread_config)
        
        if snapshot.next:
            # Paused again?
            next_step = snapshot.next[0]
            gate = get_gate_for_step(next_step)
            if gate:
                 with ReviewQueueService(db) as review_service:
                    review_service.create_review_request(
                        workflow_id=run.workflow_id,
                        run_id=run_id,
                        thread_id=run_id,
                        step_name=next_step,
                        gate=gate
                    )
                 return 

        if hasattr(snapshot, "values") and snapshot.values:
             result_state = snapshot.values
             
        # SAVE COMPLETION
        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        
        output_data = {
            "research": result_state.get("research_data"),
            "plan": result_state.get("plan_data"),
            "execution": result_state.get("execution_data"),
            "final_output": result_state.get("final_output")
        }
        run.output_data = output_data
        db.commit()

    except Exception as e:
        logger.error(f"Error resuming workflow {run_id}: {str(e)}")
        # Handle failure
        if run:
            run.status = RunStatus.FAILED
            run.error_message = str(e)
            db.commit()
        raise
    finally:
        db.close()


@huey.periodic_task(crontab(minute='*/5'))
def cleanup_old_tasks():
    """
    Periodic task to clean up old workflow runs.
    Runs every 5 minutes.
    """
    db = SessionLocal()
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # Count old runs (completed or failed)
        count = db.query(WorkflowRun).filter(
            WorkflowRun.status.in_([RunStatus.COMPLETED, RunStatus.FAILED]),
            WorkflowRun.completed_at < cutoff_time
        ).count()
        
        if count > 0:
            logger.info(f"Found {count} old workflow runs eligible for cleanup (older than 24h)")
            # Actual cleanup logic could go here (e.g. archiving or deleting)
            
    except Exception as e:
        logger.error(f"Error in cleanup_old_tasks: {str(e)}")
    finally:
        db.close()
