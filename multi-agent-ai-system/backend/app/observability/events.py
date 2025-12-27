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


import asyncio
from typing import List, Set

import threading
import collections

class ThreadSafeEventBus:
    """
    Thread-safe in-memory event bus using simple lists and locks.
    Works reliably across async/sync boundaries (unlike asyncio.Queue).
    """
    def __init__(self):
        # run_id -> list of events
        self._events: Dict[str, List[dict]] = {}
        self._lock = threading.Lock()
    
    def publish(self, run_id: str, event: dict):
        with self._lock:
            if run_id not in self._events:
                self._events[run_id] = []
            self._events[run_id].append(event)
            
    def pop_events(self, run_id: str) -> List[dict]:
        """Get and clear all pending events for a run."""
        with self._lock:
            if run_id in self._events and self._events[run_id]:
                events = self._events[run_id][:] # Copy
                self._events[run_id].clear()     # Clear
                return events
            return []

# Global thread-safe bus
_memory_bus = ThreadSafeEventBus()

def get_memory_event_bus() -> ThreadSafeEventBus:
    return _memory_bus


class WorkflowEventEmitter:
    """
    Emits workflow events to Redis pub/sub.
    Falls back to ThreadSafeEventBus if Redis is unavailable.
    """
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self._redis_available = False
        
        if redis_client is None:
            try:
                from app.ratelimit.limiter import get_redis_client
                self.redis_client = get_redis_client()
                if self.redis_client:
                    self._redis_available = True
            except Exception as e:
                logger.warning(f"Redis not available for event streaming: {e}")
                self._redis_available = False
        else:
            self._redis_available = True
            
        if not self._redis_available:
            logger.info("Using ThreadSafeEventBus for event streaming (Redis unavailable)")
    
    def emit(
        self,
        run_id: str,
        event_type: EventType,
        payload: Optional[Dict[str, Any]] = None,
        agent_name: Optional[str] = None,
        progress: Optional[float] = None,
        cost_so_far: Optional[float] = None,
    ):
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
        
        # 1. Try Redis first
        if self._redis_available and self.redis_client:
            try:
                channel = f"workflow:events:{run_id}"
                self.redis_client.publish(channel, json.dumps(event))
            except Exception as e:
                logger.error(f"Failed to publish event to Redis: {e}")
        
        # 2. ALWAYS publish to Memory Bus as fallback/mirror
        # This is safe to call from ANY thread (sync or async)
        _memory_bus.publish(run_id, event)



# Global emitter singleton
_global_emitter = None

def get_event_emitter():
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = WorkflowEventEmitter()
    return _global_emitter

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
