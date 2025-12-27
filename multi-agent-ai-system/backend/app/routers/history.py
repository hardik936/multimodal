from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
import uuid
import sqlite3
import json
import logging
from datetime import datetime

from app.database import get_db
from app.models.run import WorkflowRun, RunStatus
from app.models.workflow import Workflow
from app.auth import deps, models
from typing import Annotated
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

DB_PATH = "checkpoints.db"

class CheckpointMetadata(BaseModel):
    step: str
    run_id: str
    created_at: Optional[str] = None

class CheckpointResponse(BaseModel):
    id: str
    thread_id: str
    parent_id: Optional[str] = None
    metadata: Optional[Dict] = None
    created_at: Optional[str] = None

class StateResponse(BaseModel):
    checkpoint_id: str
    state_data: Dict[str, Any]

class ForkRequest(BaseModel):
    checkpoint_id: str
    
class ForkResponse(BaseModel):
    original_run_id: str
    new_run_id: str
    forked_from_checkpoint_id: str

@router.get("/runs/{run_id}/history", response_model=List[CheckpointResponse])
async def list_history(
    run_id: str,
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)]
):
    """
    List all checkpoints for a workflow run.
    Uses direct SQLite access to 'checkpoints.db' (managed by SqliteSaver).
    """
    checkpoints = []
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table exists (SqliteSaver might not have created it yet if no runs)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'")
        if not cursor.fetchone():
            return []
            
        # SqliteSaver (langgraph) schema usually:
        # thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata
        cursor.execute(
            "SELECT checkpoint_id, thread_id, parent_checkpoint_id, metadata FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_id DESC",
            (run_id,)
        )
        rows = cursor.fetchall()
        
        for row in rows:
            # Parse metadata if it's a blob/string
            # Parse metadata if it's a blob/string
            meta = {}
            if row["metadata"]:
                try:
                    # Try to parse as JSON first (common for custom checkpoints or simple serializers)
                    raw_meta = row["metadata"]
                    if isinstance(raw_meta, bytes):
                        # Try UTF-8 decode
                        try:
                            meta = json.loads(raw_meta.decode("utf-8"))
                        except:
                            # If not UTF-8 JSON, might be msgpack or pickle.
                            # For safety/simplicity, we skip complex binary decoding for now
                            # unless we explicitly add msgpack support.
                            # But we can try to return as string representation if small
                            pass
                    elif isinstance(raw_meta, str):
                        meta = json.loads(raw_meta)
                    elif isinstance(raw_meta, dict):
                        meta = raw_meta
                except Exception as e:
                    logger.warning(f"Failed to parse checkpoint metadata: {e}")

            
            checkpoints.append(CheckpointResponse(
                id=row["checkpoint_id"],
                thread_id=row["thread_id"],
                parent_id=row["parent_checkpoint_id"],
                metadata=meta # Placeholder
            ))
            
        conn.close()
    except Exception as e:
        logger.error(f"Error listing history: {e}")
        # Don't crash if DB issue, just return empty
        return []
        
    return checkpoints

@router.post("/runs/{run_id}/fork", response_model=ForkResponse)
async def fork_run(
    run_id: str,
    fork_request: ForkRequest,
    db: Session = Depends(get_db),
    current_user: Annotated[models.User, Depends(deps.get_current_active_user)] = None
):
    """
    Fork a run from a specific checkpoint.
    Creates a new run and copies the checkpoint state to the new thread ID.
    """
    # 1. Verify original run exists
    original_run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not original_run:
        raise HTTPException(status_code=404, detail="Original run not found")
        
    # 2. Verify Workflow exists
    workflow = db.query(Workflow).filter(Workflow.id == original_run.workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # 3. Create NEW Run
    new_run_id = str(uuid.uuid4())
    new_run = WorkflowRun(
        id=new_run_id,
        workflow_id=original_run.workflow_id,
        status="pending", # Will be picked up by worker
        input_data=original_run.input_data, # Re-use input
        started_at=datetime.utcnow()
    )
    db.add(new_run)
    db.commit()
    
    # 4. Copy Checkpoint in SQLite
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        
        # Get source checkpoint (Raw BLOBs)
        cursor.execute(
            "SELECT checkpoint, metadata FROM checkpoints WHERE thread_id = ? AND checkpoint_id = ?",
            (run_id, fork_request.checkpoint_id)
        )
        row = cursor.fetchone()
        if not row:
            db.delete(new_run)
            db.commit()
            raise HTTPException(status_code=404, detail="Checkpoint not found")
            
        checkpoint_blob, metadata_blob = row
        
        # Insert into new thread
        # Set parent_checkpoint_id to NULL to make it a root for this new thread
        # We reuse the SAME checkpoint_id or generate new? 
        # Using same checkpoint_id is fine as (thread_id, checkpoint_id) is PK usually.
        cursor.execute(
            """
            INSERT INTO checkpoints (thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (new_run_id, fork_request.checkpoint_id, None, checkpoint_blob, metadata_blob)
        )
        conn.commit()
        conn.close()
        
    except Exception as e:
        db.delete(new_run)
        db.commit()
        logger.error(f"Failed to copy checkpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fork checkpoint: {str(e)}")
        
    # 5. Trigger Resume Task (The Worker logic for 'resume' handles 'start from checkpoint')
    # We use 'resume_workflow_task' but that expects a PAUSED run.
    # Actually, we can use `execute_workflow_task` but we need to ensure it uses the checkpoint.
    # `execute_workflow_task` -> `workflow.ainvoke(initial_state, thread_config)`.
    # If `thread_config` points to `new_run_id`, LangGraph checks DB.
    # It finds the checkpoint.
    # If `initial_state` is provided, LangGraph might OVERWRITE or START FRESH?
    # Standard LangGraph: `graph.invoke(input, config)`. 
    # If config has thread_id with state, and input is not None, it treats input as NEW input to current state.
    # If input is None, it resumes?
    
    # We want to resume from that state.
    # So we should call `resume_workflow_task` (or similar logic) passing None as input?
    # But `resume_workflow_task` logic is simpler.
    
    # Let's use `resume_workflow_task` for this new run!
    # Because "Resuming" just means "Load state from DB and continue".
    # And we just seeded the DB.
    
    from app.tasks.huey_tasks import resume_workflow_task
    resume_workflow_task(new_run_id) 
    
    return ForkResponse(
        original_run_id=run_id,
        new_run_id=new_run_id,
        forked_from_checkpoint_id=fork_request.checkpoint_id
    )
