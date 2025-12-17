"""
Workflow Event System

Centralized event emitter for workflow lifecycle events.
Publishes events to Redis pub/sub for real-time streaming via WebSocket.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Workflow event types"""
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_AGENT_STARTED = "workflow.agent.started"
    WORKFLOW_AGENT_COMPLETED = "workflow.agent.completed"
    WORKFLOW_PROGRESS = "workflow.progress"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_COST_UPDATE = "workflow.cost.update"


class WorkflowEventEmitter:
    """
    Emits workflow events to Redis pub/sub for real-time streaming.
    Gracefully handles Redis unavailability.
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize event emitter.
        
        Args:
            redis_client: Optional Redis client. If None, will attempt to get from config.
        """
        self.redis_client = redis_client
        self._redis_available = False
        
        if redis_client is None:
            try:
                from app.ratelimit.limiter import get_redis_client
                self.redis_client = get_redis_client()
                self._redis_available = True
            except Exception as e:
                logger.warning(f"Redis not available for event streaming: {e}")
                self._redis_available = False
        else:
            self._redis_available = True
    
    def emit(
        self,
        run_id: str,
        event_type: EventType,
        payload: Optional[Dict[str, Any]] = None,
        agent_name: Optional[str] = None,
        progress: Optional[float] = None,
        cost_so_far: Optional[float] = None,
    ):
        """
        Emit a workflow event.
        
        Args:
            run_id: Workflow run ID
            event_type: Type of event
            payload: Optional additional event data
            agent_name: Optional agent name (for agent-specific events)
            progress: Optional progress percentage (0-100)
            cost_so_far: Optional accumulated cost in USD
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "event_type": event_type.value,
            "agent_name": agent_name,
            "progress": progress,
            "cost_so_far": cost_so_far,
            "payload": payload or {}
        }
        
        # Log event for debugging
        logger.info(f"Event: {event_type.value} for run {run_id[:8]}... (agent: {agent_name}, progress: {progress}%)")
        
        # Publish to Redis if available
        if self._redis_available and self.redis_client:
            try:
                channel = f"workflow:events:{run_id}"
                self.redis_client.publish(channel, json.dumps(event))
            except Exception as e:
                logger.error(f"Failed to publish event to Redis: {e}")
                # Don't crash - event streaming is not critical for workflow execution
        else:
            logger.debug(f"Redis not available, event not published: {event_type.value}")


# Global emitter instance
_emitter: Optional[WorkflowEventEmitter] = None


def get_event_emitter() -> WorkflowEventEmitter:
    """Get or create the global event emitter instance."""
    global _emitter
    if _emitter is None:
        _emitter = WorkflowEventEmitter()
    return _emitter


def emit_workflow_event(
    run_id: str,
    event_type: EventType,
    payload: Optional[Dict[str, Any]] = None,
    agent_name: Optional[str] = None,
    progress: Optional[float] = None,
    cost_so_far: Optional[float] = None,
):
    """
    Convenience function to emit a workflow event.
    
    Args:
        run_id: Workflow run ID
        event_type: Type of event
        payload: Optional additional event data
        agent_name: Optional agent name
        progress: Optional progress percentage (0-100)
        cost_so_far: Optional accumulated cost
    """
    emitter = get_event_emitter()
    emitter.emit(
        run_id=run_id,
        event_type=event_type,
        payload=payload,
        agent_name=agent_name,
        progress=progress,
        cost_so_far=cost_so_far,
    )
