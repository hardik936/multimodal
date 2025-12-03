"""
Huey background task queue configuration and task definitions.
Handles asynchronous workflow execution and periodic cleanup.
"""
import logging
import asyncio
import traceback
from datetime import datetime, timedelta, timezone

from huey import SqliteHuey, crontab
from app.config import settings
from app.database import SessionLocal
from app.models.run import WorkflowRun, RunStatus
from app.models.message import Message, MessageRole
from app.agents.graph import create_multi_agent_workflow

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Huey
# Use a SQLite file in the backend working directory
huey = SqliteHuey(
    filename="huey.db",
    name="multi_agent_workflows",
    results=True,
    store_none=True,
    utc=True,
    immediate=settings.HUEY_IMMEDIATE,
)


@huey.task(retry=True, retry_delay=60, retries=3)
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
        
        # Create workflow graph
        workflow = create_multi_agent_workflow(workflow_config)
        
        # Build initial state
        if input_data is None:
            logger.error("input_data is None!")
            raise ValueError("input_data cannot be None")

        initial_state = {
            "input": input_data.get("query", ""),
            "messages": [],
            # Initialize other state keys as needed by the graph
            "current_agent": "planner",  # Default starting point
            "research_data": {},
            "plan_data": {},
            "execution_data": {},
            "code_data": {},
            "final_output": ""
        }
        
        # Execute workflow (handle async execution synchronously)
        # Since Huey tasks are sync, we need to run the async workflow in an event loop
        try:
            import concurrent.futures
            # Run in a separate thread to avoid event loop conflicts
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result_state = pool.submit(asyncio.run, workflow.ainvoke(initial_state)).result()
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise
            
        logger.info(f"Workflow execution result: {result_state}")

        if result_state is None:
             logger.error("result_state is None!")
             raise ValueError("Workflow execution returned None")

        # Process results
        # Save messages
        if "messages" in result_state:
            for msg in result_state["messages"]:
                # Map LangChain messages to DB model
                # This depends on the exact structure of messages in result_state
                # Assuming standard LangChain BaseMessage objects or dicts
                
                content = ""
                role = MessageRole.AGENT
                agent_name = "system"
                
                if hasattr(msg, "content"):
                    content = msg.content
                    # Map role based on type
                    if msg.type == "human":
                        role = MessageRole.USER
                    elif msg.type == "ai":
                        role = MessageRole.AGENT
                    elif msg.type == "system":
                        role = MessageRole.SYSTEM
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                    role_str = msg.get("role", "agent")
                    # Map string role to enum
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
                    agent_name=agent_name, # Ideally this comes from the message metadata
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
        # Assuming output_data field exists and handles JSON serialization (e.g. JSON type)
        # If it's a string field, we might need to json.dumps it
        # Checking models/run.py would confirm, but assuming JSON compatible for now
        run.output_data = output_data
        
        db.commit()
        logger.info(f"Workflow execution completed for run_id: {run_id}")
        
    except Exception as e:
        logger.error(f"Error executing workflow {run_id}: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Update run status to FAILED
        try:
            # Re-query to ensure we have a valid session/object
            run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if run:
                run.status = RunStatus.FAILED
                run.error_message = str(e)
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as db_e:
            logger.error(f"Failed to update run status to FAILED: {str(db_e)}")
            
        # Re-raise to trigger Huey retry
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
