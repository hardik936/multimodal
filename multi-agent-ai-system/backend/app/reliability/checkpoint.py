import sqlite3
import json
import time
import logging
from typing import Any, Dict, Optional
from app.config import settings
from app.observability.tracing import get_tracer, trace_span

logger = logging.getLogger(__name__)
tracer = get_tracer("reliability.checkpoint")

DB_PATH = "checkpoints.db"

def init_checkpoint_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            step TEXT NOT NULL,
            state TEXT NOT NULL, -- JSON serialized state
            timestamp REAL NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflow_id ON checkpoints (workflow_id)")
    conn.commit()
    conn.close()

# Initialize on module load (or call explicitly)
try:
    init_checkpoint_db()
except Exception as e:
    logger.error(f"Failed to init checkpoint db: {e}")

def save_checkpoint(workflow_id: str, step: str, state: Dict[str, Any]):
    """
    Save specific state checkpoint for a workflow step.
    """
    try:
        # Basic serialization - user should ensure state is serializable
        serialized_state = json.dumps(state, default=str)
        
        with trace_span(tracer, "checkpoint.save", attributes={"workflow.id": workflow_id, "checkpoint.step": step}):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            timestamp = time.time()
            cursor.execute(
                "INSERT INTO checkpoints (workflow_id, step, state, timestamp) VALUES (?, ?, ?, ?)",
                (workflow_id, step, serialized_state, timestamp)
            )
            conn.commit()
            conn.close()
            logger.debug(f"Saved checkpoint for {workflow_id} at {step}")
            
    except Exception as e:
        logger.error(f"Failed to save checkpoint for {workflow_id}: {e}")
        # We generally don't want checkpointing to crash the workflow
        pass

def load_last_checkpoint(workflow_id: str) -> Optional[Dict[str, Any]]:
    """
    Load the most recent checkpoint for a workflow.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT step, state, timestamp FROM checkpoints WHERE workflow_id = ? ORDER BY timestamp DESC LIMIT 1",
            (workflow_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            step, state_str, timestamp = row
            return {
                "step": step,
                "state": json.loads(state_str),
                "timestamp": timestamp
            }
        return None
        
    except Exception as e:
        logger.error(f"Failed to load checkpoint for {workflow_id}: {e}")
        return None
