import asyncio
import json
import logging
import time
from typing import Optional, Dict
from datetime import datetime, timezone
import random

from app.config import settings
from app.observability.events import EventType

logger = logging.getLogger(__name__)

class ShadowAgentService:
    """
    Passive observer that monitors active workflows for stalls/friction.
    If a stall is detected, it generates a hint using a 'Helper LLM'.
    """
    
    def __init__(self):
        self.running = False
        # run_id -> last_event_timestamp (float)
        self.last_activity: Dict[str, float] = {}
        # run_id -> boolean (has_warned) to prevent spam
        self.warned_runs: Dict[str, bool] = {}
        
        # Config
        self.STALL_THRESHOLD = 120.0 # Seconds (2 mins as per spec)
        self.CHECK_INTERVAL = 10.0
        
    async def start(self):
        self.running = True
        logger.info("Shadow Agent Service started.")
        asyncio.create_task(self._monitor_loop())
        asyncio.create_task(self._event_listener())
        
    async def stop(self):
        self.running = False
        logger.info("Shadow Agent Service stopped.")

    async def _event_listener(self):
        """Listen to ALL workflow events to update activity timestamps."""
        try:
            from app.ratelimit.limiter import get_redis_client
            redis = get_redis_client()
            if not redis:
                logger.warning("Redis not available. Shadow Agent disabled.")
                return

            pubsub = redis.pubsub()
            # Subscribe to pattern for all workflow events
            pubsub.psubscribe("workflow:events:*")
            
            logger.info("Shadow Agent listening to Redis events...")
            
            while self.running:
                try:
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message:
                        channel = message['channel'].decode('utf-8')
                        # Extract run_id from "workflow:events:{run_id}"
                        run_id = channel.split(":")[-1]
                        
                        data = json.loads(message['data'])
                        event_type = data.get("event_type")
                        
                        # Update activity
                        self.last_activity[run_id] = time.time()
                        
                        # If workflow finished, remove tracking
                        if event_type in [EventType.WORKFLOW_COMPLETED, EventType.WORKFLOW_FAILED]:
                            if run_id in self.last_activity:
                                del self.last_activity[run_id]
                            if run_id in self.warned_runs:
                                del self.warned_runs[run_id]
                                
                    await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"Shadow Agent listener error: {e}")
                    await asyncio.sleep(5)
                    
        except Exception as e:
            logger.error(f"Shadow Agent setup failed: {e}")

    async def _monitor_loop(self):
        """Periodic check for stalled runs."""
        while self.running:
            try:
                now = time.time()
                stalled_runs = []
                
                for run_id, last_time in list(self.last_activity.items()):
                    if now - last_time > self.STALL_THRESHOLD:
                        if not self.warned_runs.get(run_id):
                            stalled_runs.append(run_id)
                
                for run_id in stalled_runs:
                    await self.trigger_hint(run_id)
                    self.warned_runs[run_id] = True
                    
            except Exception as e:
                logger.error(f"Shadow Agent monitor error: {e}")
            
            await asyncio.sleep(self.CHECK_INTERVAL)

    async def trigger_hint(self, run_id: str):
        """Generate and publish a hint for a stalled run."""
        logger.info(f"Stall detected for run {run_id}. Generating hint...")
        
        try:
            # 1. Get minimal context (e.g., last few DB messages)
            # For efficiency/privacy, we might just look at the last known agent state if we had it.
            # Here we'll generate a generic or semi-contextual hint.
            
            hint_text = await self._generate_llm_hint(run_id)
            
            # 2. Publish 'shadow.hint' event
            from app.observability.events import emit_workflow_event
            # We define a custom event type string since it's not in the Enum yet (or update Enum)
            # Using raw emit via imported emitter or just leveraging the event bus directly.
            
            # Re-using the router's connection manager broadcast would be ideal but that's in-process.
            # We must publish to Redis so the API/WS process picks it up.
            
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
                "event_type": "shadow.hint",
                "payload": {
                    "message": hint_text,
                    "suggestion_type": "stall_recovery"
                }
            }
            
            # Publish to Redis
            from app.ratelimit.limiter import get_redis_client
            redis = get_redis_client()
            if redis:
                channel = f"workflow:events:{run_id}"
                redis.publish(channel, json.dumps(event))
                logger.info(f"Published shadow hint for {run_id}")
                
        except Exception as e:
            logger.error(f"Failed to generate/publish hint: {e}")

    async def _generate_llm_hint(self, run_id: str) -> str:
        """
        Call LLM in read-only mode to suggest a fix.
        Mocked for this implementation to avoid cost/complexity without actual keys configured in env for a 'Helper'.
        In prod, use a cheaper model (e.g. Haiku or Llama-3-8B).
        """
        # In a real implementation: fetch last state/messages from DB
        # prompt = f"User is stuck. Last agent: {last_agent}. Last output: {last_output}. Suggest 1 sentence fix."
        
        suggestions = [
            "It looks like the workflow is waiting. Check if approval is needed?",
            "Execution seems stuck. You might want to retry the last step.",
            "The researcher is taking a while. Try simplifying the query.",
            "Shadow Agent: I noticed a delay. Recommend checking the logs."
        ]
        return random.choice(suggestions)

# Singleton
shadow_agent = ShadowAgentService()
