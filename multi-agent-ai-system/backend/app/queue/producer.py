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
        logger.error(f"Failed to publish message: {e}")
        # In a real app, you might want to retry or fallback
        raise
