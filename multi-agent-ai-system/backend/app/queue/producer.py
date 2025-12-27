import json
import aio_pika
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Global connection object
_connection = None

async def get_connection():
    global _connection
    if _connection is None or _connection.is_closed:
        logger.info("Establishing new RabbitMQ connection...")
        _connection = await aio_pika.connect_robust(settings.BROKER_URL)
    return _connection

async def close_connection():
    global _connection
    if _connection and not _connection.is_closed:
        logger.info("Closing RabbitMQ connection.")
        await _connection.close()
        _connection = None

async def publish_message(message: dict, routing_key: str = "tasks.workflow_execution"):
    """
    Publish a message to RabbitMQ using a persistent connection.
    """
    try:
        connection = await get_connection()
        # Open a channel (channels are lightweight and can be opened per request)
        async with connection.channel() as channel:
            
            # Declare queue to ensure it exists
            await channel.declare_queue(
                routing_key, 
                durable=True,
                arguments={'x-queue-type': 'classic'}
            )
            
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=routing_key
            )
            logger.info(f"Published message to {routing_key}: {message.get('task_id')}")
    except Exception as e:
        logger.warning(f"Failed to connect/publish to RabbitMQ: {e}. Falling back to LOCAL IN-PROCESS execution.")
        
        try:
            # Fallback: Execute directly in this process (for dev/demo without RabbitMQ)
            # Late import to avoid circular dependency
            from app.queue.worker import process_task
            
            # Re-serialize as bytes to match worker expectation
            message_body = json.dumps(message).encode()
            
            # Run the task in background to avoid blocking the API response
            # Run the task in background to avoid blocking the API response
            import asyncio
            
            async def safe_process(body):
                try:
                    # Give the API request time to complete and release DB locks
                    await asyncio.sleep(2.0)
                    logger.info("Starting delayed background execution...")
                    
                    # Set a timeout for the entire workflow execution (e.g. 5 minutes)
                    await asyncio.wait_for(process_task(body), timeout=300.0)
                except asyncio.TimeoutError:
                    logger.error("Workflow execution TIMED OUT locally after 300s.")
                    # In a real system, we should mark the run as FAILED in DB here.
                except Exception as ex:
                    logger.error(f"Background task CRASHED: {ex}")
                    import traceback
                    traceback.print_exc()

            asyncio.create_task(safe_process(message_body))
            logger.info(f"Scheduled task {message.get('task_id')} for local execution.")
            
        except Exception as local_e:
            logger.error(f"Local execution also failed: {local_e}")
            raise local_e

