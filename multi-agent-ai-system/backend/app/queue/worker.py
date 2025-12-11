import asyncio
import json
import logging
import traceback
import aio_pika
from datetime import datetime, timezone
import functools

from app.config import settings
from app.database import SessionLocal
# Import all models to ensure relationships are properly initialized
# Import order matters: Log and Message before WorkflowRun
from app.models import Workflow, Log, Message, WorkflowRun
from app.models.run import RunStatus
from app.models.message import MessageRole
from app.agents.graph import create_multi_agent_workflow
from app.observability.tracing import configure_tracing, get_tracer, trace_span, add_span_attributes, set_span_error

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure tracing
configure_tracing()
tracer = get_tracer("workflow.worker")

def run_sync(func):
    """Helper to run sync DB operations in a thread pool"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper

def get_db_run(run_id: str):
    db = SessionLocal()
    try:
        return db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    finally:
        db.close()

def update_run_status_sync(run_id: str, status: RunStatus, started_at=None, completed_at=None, output_data=None, error_message=None):
    db = SessionLocal()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
        if run:
            run.status = status
            if started_at:
                run.started_at = started_at
            if completed_at:
                run.completed_at = completed_at
            if output_data:
                run.output_data = output_data
            if error_message:
                run.error_message = error_message
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update run status: {e}")
    finally:
        db.close()

def save_messages_sync(run_id: str, result_state: dict):
    db = SessionLocal()
    try:
        if "messages" in result_state:
            for msg in result_state["messages"]:
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
                
                db_msg = Message(
                    run_id=run_id,
                    role=role,
                    content=str(content),
                    msg_metadata={"agent_name": agent_name}
                )
                db.add(db_msg)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to save messages: {e}")
    finally:
        db.close()

async def process_task(message_body: bytes):
    try:
        data = json.loads(message_body)
        run_id = data.get("task_id")
        task_payload = data.get("payload", {})
        
        workflow_config = task_payload.get("workflow_config", {})
        input_data = task_payload.get("input_data")
        
        logger.info(f"Processing task: {run_id}")
        
        # 1. Idempotency Check & Status Update
        # We run this in executor to avoid blocking
        loop = asyncio.get_running_loop()
        run = await loop.run_in_executor(None, get_db_run, run_id)
        
        if not run:
            logger.error(f"Run {run_id} not found in DB")
            return
            
        if run.status == RunStatus.COMPLETED:
            logger.info(f"Run {run_id} already completed. Skipping.")
            return

        await loop.run_in_executor(None, update_run_status_sync, 
            run_id, RunStatus.RUNNING, datetime.now(timezone.utc), None, None, None
        )

        # 2. Execution with workflow.run tracing
        workflow = create_multi_agent_workflow(workflow_config)
        
        initial_state = {
            "input": input_data.get("input") or input_data.get("query", ""),
            "language": input_data.get("language", "python"),
            "mode": input_data.get("mode", "full"),
            "messages": [],
            "current_agent": "planner",
            "query_complexity": "SIMPLE",  # Will be set by researcher
            "research_data": "",
            "plan_data": {},
            "execution_data": "",
            "code_data": "",
            "final_output": "",  # Will be populated by finalizer
            "run_id": run_id,  # Add run_id for tracing
        }
        
        # Create root workflow.run span
        with trace_span(
            tracer,
            "workflow.run",
            attributes={
                "workflow.id": run.workflow_id,
                "workflow.run_id": run_id,
                "workflow.name": "multi-agent-workflow",
                "workflow.mode": initial_state["mode"],
            }
        ) as workflow_span:
            # This is where we run the actual AI workflow
            result_state = await workflow.ainvoke(initial_state)
            
            if result_state is None:
                raise ValueError("Workflow execution returned None")
            
            # Add workflow result attributes
            add_span_attributes(workflow_span, {
                "workflow.query_complexity": result_state.get("query_complexity", "UNKNOWN"),
                "workflow.status": "completed",
            })

            # --- SHADOW MODE INTEGRATION ---
            try:
                from app.versioning.registry import get_shadow_deployment
                from app.versioning.comparator import record_comparison
                import random

                shadow_deployment = await loop.run_in_executor(None, get_shadow_deployment, run.workflow_id)
                
                if shadow_deployment and shadow_deployment.is_shadow:
                    if random.random() < (shadow_deployment.sample_rate or 0.05):
                        logger.info(f"Spawning SHADOW run for {run_id} (Deployment {shadow_deployment.id})")
                        
                        async def run_shadow():
                            try:
                                shadow_state = initial_state.copy()
                                shadow_state["shadow_mode"] = True
                                shadow_state["deployment_id"] = shadow_deployment.id
                                
                                # In shadow mode, we might want to use a different snapshot/code version
                                # For V1, we assume the code is same but running with "shadow" context
                                # To support actual different code, we'd need to load a different graph
                                # Here we simulate it by running the same graph but allowing different branches if logic supports it
                                
                                shadow_result = await workflow.ainvoke(shadow_state)
                                
                                # Compare
                                # Extract simple outputs for comparison
                                baseline_out = {
                                    "final_output": result_state.get("final_output"),
                                    "plan": result_state.get("plan_data")
                                }
                                candidate_out = {
                                    "final_output": shadow_result.get("final_output"),
                                    "plan": shadow_result.get("plan_data")
                                }
                                
                                await loop.run_in_executor(None, lambda: record_comparison(
                                    workflow_id=run.workflow_id,
                                    baseline_run_id=run_id,
                                    candidate_run_id=f"shadow-{run_id}",
                                    baseline_snapshot_id="current", # Todo: get from active deployment
                                    candidate_snapshot_id=shadow_deployment.snapshot_id,
                                    baseline_output=baseline_out,
                                    candidate_output=candidate_out
                                ))
                                logger.info(f"Shadow run finished and compared for {run_id}")
                                
                                # Check monitors
                                from app.versioning.monitor import check_divergence
                                await loop.run_in_executor(None, check_divergence, run.workflow_id)
                                
                            except Exception as e:
                                logger.error(f"Shadow run failed: {e}")

                        # Fire and forget shadow task
                        asyncio.create_task(run_shadow())
            except Exception as e:
                logger.error(f"Shadow integration error: {e}")
            # -------------------------------

        # 3. Save Results
        output_data = {
            "research": result_state.get("research_data"),
            "plan": result_state.get("plan_data"),
            "execution": result_state.get("execution_data"),
            "code": result_state.get("code_data"),
            "final_output": result_state.get("final_output")  # Now always populated
        }
        
        await loop.run_in_executor(None, save_messages_sync, run_id, result_state)
        
        await loop.run_in_executor(None, update_run_status_sync, 
            run_id, RunStatus.COMPLETED, None, datetime.now(timezone.utc), output_data, None
        )
        
        logger.info(f"Task {run_id} completed successfully")

    except Exception as e:
        logger.error(f"Task failed: {e}")
        logger.error(traceback.format_exc())
        
        if 'run_id' in locals():
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, update_run_status_sync, 
                run_id, RunStatus.FAILED, None, datetime.now(timezone.utc), None, str(e)
            )
        raise

async def main():
    # Initialize database models to ensure all relationships are configured
    from app.database import init_db
    from sqlalchemy.orm import configure_mappers
    
    init_db()
    
    # Force mapper configuration after all models are imported
    try:
        configure_mappers()
        logger.info("SQLAlchemy mappers configured successfully")
    except Exception as e:
        logger.error(f"Mapper configuration failed: {e}")
        # Continue anyway - the error might be non-fatal
    
    logger.info("Starting Worker...")
    while True:
        try:
            connection = await aio_pika.connect_robust(settings.BROKER_URL)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=1)
                
                # Declare queue
                queue = await channel.declare_queue(
                    "tasks.generic", 
                    durable=True,
                    arguments={'x-queue-type': 'classic'}
                )
                
                logger.info("Waiting for messages...")
                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        async with message.process():
                            await process_task(message.body)
        except Exception as e:
            logger.error(f"Connection error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
