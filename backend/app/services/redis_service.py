"""
Redis service module for managing Redis connections and stream operations.

This module provides async Redis connection management with consumer groups
for reliable message delivery and proper error handling.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional

import redis.asyncio as redis
from app.core.config import settings
from redis.asyncio import Redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

REDIS_URL = settings.redis_url
REDIS_STREAM_NAME = settings.redis_stream_name
CONSUMER_GROUP = "fastapi_radiology_group"

print(f"[Config] Redis URL: {REDIS_URL}, Stream: {REDIS_STREAM_NAME}")

redis_client: Optional[Redis] = None


async def init_redis() -> Redis:
    """
    Initialize Redis connection pool with proper configuration.

    Returns:
        Redis client instance

    Raises:
        redis.ConnectionError: If connection fails
    """
    global redis_client

    try:
        redis_client = await redis.from_url(
            REDIS_URL,
            decode_responses=True,
            max_connections=10,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        # Test connection
        await redis_client.ping()
        logger.info("[Redis] Connection established successfully")

        # Initialize consumer group for reliable message delivery
        await _init_consumer_group()

    except Exception as e:
        logger.error(f"[Redis] Failed to initialize: {e}")
        raise

    return redis_client


async def _init_consumer_group():
    """Initialize consumer group if it doesn't exist"""
    try:
        await redis_client.xgroup_create(
            REDIS_STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True
        )
        logger.info(f"[Redis] Created consumer group: {CONSUMER_GROUP}")
    except ResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.info(f"[Redis] Consumer group already exists: {CONSUMER_GROUP}")
        else:
            logger.error(f"[Redis] Error creating consumer group: {e}")
            raise


async def close_redis():
    """Close Redis connection pool gracefully"""
    global redis_client
    if redis_client:
        try:
            await redis_client.close()
            await redis_client.connection_pool.disconnect()
            logger.info("[Redis] Connection closed successfully")
        except Exception as e:
            logger.error(f"[Redis] Error during shutdown: {e}")
        finally:
            redis_client = None


def get_redis() -> Redis:
    """
    Get Redis client instance.

    Returns:
        Redis client

    Raises:
        RuntimeError: If Redis is not initialized
    """
    if not redis_client:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client


async def add_to_stream(event_type: str, data: dict) -> str:
    """
    Add message to Redis Stream.

    Args:
        event_type: Type of event to emit
        data: Event data dictionary

    Returns:
        Message ID from Redis

    Raises:
        RuntimeError: If Redis is not initialized
        redis.RedisError: If write operation fails
    """
    client = get_redis()

    try:
        message_id = await client.xadd(
            REDIS_STREAM_NAME,
            {"event": event_type, **data},
            maxlen=10000,  # Prevent unbounded growth
            approximate=True,
        )
        logger.debug(f"[Redis] Added event: {event_type} (ID: {message_id})")
        return message_id
    except Exception as e:
        logger.error(f"[Redis] Failed to add event {event_type}: {e}")
        raise


async def read_stream(
    redis_pool: Redis,
    stream_name: str = None,
    consumer_group: str = None,
    consumer_name: str = None,
    block: int = 5000,
    count: int = 10,
) -> AsyncGenerator[tuple[str, dict], None]:
    """
    Read from Redis Stream using consumer groups for reliable delivery.

    Args:
        redis_pool: Redis client instance
        stream_name: Name of the Redis stream (defaults to REDIS_STREAM_NAME)
        consumer_group: Consumer group name (defaults to CONSUMER_GROUP)
        consumer_name: Consumer name for this connection
        block: Block time in milliseconds (default 5000)
        count: Maximum messages to fetch per read (default 10)

    Yields:
        Tuple of (message_id, data_dict)

    Note:
        This function runs indefinitely until cancelled. Handle cancellation
        appropriately in the calling code.
    """
    # Use defaults if not provided
    stream_name = stream_name or REDIS_STREAM_NAME
    consumer_group = consumer_group or CONSUMER_GROUP

    if not consumer_name:
        raise ValueError("consumer_name is required for read_stream")

    logger.info(
        f"[Redis] Starting stream reader (group: {consumer_group}, "
        f"consumer: {consumer_name}, stream: {stream_name})"
    )

    # Track consecutive errors for backoff
    error_count = 0
    max_errors = 5

    # Ensure consumer group exists for this stream
    try:
        await redis_pool.xgroup_create(
            stream_name, consumer_group, id="0", mkstream=True
        )
        logger.info(f"[Redis] Created consumer group: {consumer_group}")
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            logger.error(f"[Redis] Error creating consumer group: {e}")
            raise

    while True:
        try:
            # Read new messages for this consumer
            messages = await redis_pool.xreadgroup(
                groupname=consumer_group,
                consumername=consumer_name,
                streams={stream_name: ">"},
                count=count,
                block=block,
            )

            # Reset error count on successful read
            error_count = 0

            if messages:
                for _, stream_messages in messages:
                    for msg_id, fields in stream_messages:
                        try:
                            yield msg_id, fields
                            # Acknowledge message after successful processing
                            await redis_pool.xack(stream_name, consumer_group, msg_id)
                            logger.debug(
                                f"[Redis] Processed and acknowledged message: {msg_id}"
                            )
                        except Exception as e:
                            logger.error(
                                f"[Redis] Error processing message {msg_id}: {e}"
                            )
                            # Don't acknowledge failed messages - they'll be redelivered
            else:
                # No messages, yield None to allow keep-alive
                yield None, None

        except asyncio.CancelledError:
            logger.info(
                f"[Redis] Stream reader cancelled for consumer: {consumer_name}"
            )
            break

        except ResponseError as e:
            error_count += 1
            logger.error(
                f"[Redis] Response error reading stream (attempt {error_count}): {e}"
            )

            if error_count >= max_errors:
                logger.critical(
                    f"[Redis] Too many consecutive errors ({max_errors}), stopping reader"
                )
                break

            await asyncio.sleep(min(error_count * 2, 30))

        except Exception as e:
            error_count += 1
            logger.error(
                f"[Redis] Unexpected error reading stream (attempt {error_count}): {e}"
            )

            if error_count >= max_errors:
                logger.critical(
                    f"[Redis] Too many consecutive errors ({max_errors}), stopping reader"
                )
                break

            await asyncio.sleep(min(error_count * 2, 30))


async def claim_pending_messages(
    stream_name: str = None,
    consumer_group: str = None,
    consumer_name: str = None,
    min_idle_time: int = 60000,
) -> int:
    """
    Claim and reprocess pending messages that haven't been acknowledged.

    Args:
        stream_name: Name of the Redis stream (defaults to REDIS_STREAM_NAME)
        consumer_group: Consumer group name (defaults to CONSUMER_GROUP)
        consumer_name: Consumer name to claim messages for
        min_idle_time: Minimum idle time in milliseconds before claiming (default 60s)

    Returns:
        Number of messages claimed
    """
    client = get_redis()
    stream_name = stream_name or REDIS_STREAM_NAME
    consumer_group = consumer_group or CONSUMER_GROUP

    if not consumer_name:
        raise ValueError("consumer_name is required for claiming messages")

    try:
        # Get pending messages
        pending = await client.xpending_range(
            stream_name, consumer_group, min="-", max="+", count=100
        )

        if not pending:
            return 0

        claimed_count = 0
        for message in pending:
            msg_id = message["message_id"]
            idle_time = message["time_since_delivered"]

            if idle_time >= min_idle_time:
                # Claim the message
                claimed = await client.xclaim(
                    stream_name,
                    consumer_group,
                    consumer_name,
                    min_idle_time,
                    [msg_id],
                )
                if claimed:
                    claimed_count += 1
                    logger.info(f"[Redis] Claimed pending message: {msg_id}")

        return claimed_count

    except Exception as e:
        logger.error(f"[Redis] Error claiming pending messages: {e}")
        return 0


async def get_stream_info(stream_name: str = None) -> dict:
    """
    Get information about the stream for monitoring.

    Args:
        stream_name: Name of the Redis stream (defaults to REDIS_STREAM_NAME)

    Returns:
        Dictionary with stream information
    """
    client = get_redis()
    stream_name = stream_name or REDIS_STREAM_NAME

    try:
        info = await client.xinfo_stream(stream_name)

        # Get consumer group info
        try:
            groups = await client.xinfo_groups(stream_name)
            info["groups"] = groups
        except ResponseError:
            info["groups"] = []

        return info
    except ResponseError:
        return {"error": "Stream does not exist"}
    except Exception as e:
        logger.error(f"[Redis] Error getting stream info: {e}")
        return {"error": str(e)}


async def trim_stream(stream_name: str = None, max_len: int = 10000):
    """
    Trim stream to prevent unbounded growth.

    Args:
        stream_name: Name of the Redis stream (defaults to REDIS_STREAM_NAME)
        max_len: Maximum number of messages to keep
    """
    client = get_redis()
    stream_name = stream_name or REDIS_STREAM_NAME

    try:
        trimmed = await client.xtrim(stream_name, maxlen=max_len, approximate=True)
        logger.info(f"[Redis] Trimmed stream {stream_name}, removed {trimmed} messages")
    except Exception as e:
        logger.error(f"[Redis] Error trimming stream: {e}")
