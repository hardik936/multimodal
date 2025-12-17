"""
WebSocket Router for Real-Time Workflow Streaming

Provides WebSocket endpoint for clients to receive live workflow execution events.
"""

import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.database import SessionLocal
from app.models.run import WorkflowRun

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections per run_id."""
    
    def __init__(self):
        # Map of run_id -> set of active websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, run_id: str):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        async with self._lock:
            if run_id not in self.active_connections:
                self.active_connections[run_id] = set()
            self.active_connections[run_id].add(websocket)
        
        logger.info(f"WebSocket connected for run {run_id[:8]}... (total: {len(self.active_connections[run_id])})")
    
    async def disconnect(self, websocket: WebSocket, run_id: str):
        """Unregister a WebSocket connection."""
        async with self._lock:
            if run_id in self.active_connections:
                self.active_connections[run_id].discard(websocket)
                if not self.active_connections[run_id]:
                    del self.active_connections[run_id]
        
        logger.info(f"WebSocket disconnected for run {run_id[:8]}...")
    
    async def broadcast(self, run_id: str, message: dict):
        """Broadcast a message to all clients connected to this run_id."""
        if run_id not in self.active_connections:
            return
        
        disconnected = []
        message_json = json.dumps(message)
        
        for websocket in self.active_connections[run_id]:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message_json)
                else:
                    disconnected.append(websocket)
            except Exception as e:
                logger.error(f"Error broadcasting to websocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for ws in disconnected:
            await self.disconnect(ws, run_id)


# Global connection manager
manager = ConnectionManager()


async def listen_to_redis(run_id: str):
    """
    Listen to Redis pub/sub channel for this run_id and broadcast events.
    Runs in background task.
    """
    try:
        from app.ratelimit.limiter import get_redis_client
        redis_client = get_redis_client()
        
        if redis_client is None:
            logger.warning(f"Redis not available, WebSocket for run {run_id[:8]}... will not receive events")
            return
        
        pubsub = redis_client.pubsub()
        channel = f"workflow:events:{run_id}"
        pubsub.subscribe(channel)
        
        logger.info(f"Listening to Redis channel: {channel}")
        
        # Listen for messages
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    event_data = json.loads(message['data'])
                    await manager.broadcast(run_id, event_data)
                except Exception as e:
                    logger.error(f"Error processing Redis message: {e}")
            
            # Check if there are still active connections
            if run_id not in manager.active_connections:
                logger.info(f"No more active connections for run {run_id[:8]}..., stopping Redis listener")
                break
        
        pubsub.unsubscribe(channel)
        pubsub.close()
        
    except Exception as e:
        logger.error(f"Redis listener error for run {run_id[:8]}...: {e}")


@router.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time workflow execution updates.
    
    Clients connect to /ws/{run_id} and receive JSON events as the workflow executes.
    """
    await manager.connect(websocket, run_id)
    
    # Start Redis listener in background
    redis_task = asyncio.create_task(listen_to_redis(run_id))
    
    try:
        # Send initial state
        db = SessionLocal()
        try:
            run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if run:
                initial_state = {
                    "event_type": "connection.established",
                    "run_id": run_id,
                    "current_status": run.status.value,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                }
                await websocket.send_json(initial_state)
            else:
                await websocket.send_json({
                    "event_type": "error",
                    "message": f"Run {run_id} not found"
                })
        finally:
            db.close()
        
        # Keep connection alive with heartbeat
        while True:
            try:
                # Wait for ping from client (timeout after 30 seconds)
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping to client
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"event_type": "ping"})
                else:
                    break
            except WebSocketDisconnect:
                break
    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from run {run_id[:8]}...")
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id[:8]}...: {e}")
    finally:
        await manager.disconnect(websocket, run_id)
        # Cancel Redis listener
        redis_task.cancel()
        try:
            await redis_task
        except asyncio.CancelledError:
            pass
