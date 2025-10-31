"""
Redis service module for managing Redis connections, streams, and cache operations.

This module provides async Redis connection management with consumer groups
for reliable message delivery, caching, and session management.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Optional

import redis.asyncio as redis
from app.core.config import settings
from redis.asyncio import Redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = settings.redis_url
REDIS_PASSWORD = settings.redis_password
REDIS_STREAM_NAME = settings.redis_stream_name
logger.info(f"[Redis] URL: {REDIS_URL}")
logger.info(f"[Redis] Password: {REDIS_PASSWORD}")
logger.info(f"[Redis] Stream Name: {REDIS_STREAM_NAME}")
DEFAULT_CONSUMER_GROUP = "fastapi_radiology_group"

# Global Redis client
_redis_client: Optional[Redis] = None


class RedisService:
    """Centralized Redis service for all Redis operations."""

    def __init__(self):
        self.client: Optional[Redis] = None

    async def init_redis(self) -> Redis:
        """
        Initialize Redis connection pool with proper configuration.

        Returns:
            Redis client instance

        Raises:
            redis.ConnectionError: If connection fails
        """
        global _redis_client

        if _redis_client:
            logger.info("[Redis] Using existing connection")
            self.client = _redis_client
            return self.client

        try:
            logger.info(f"[Redis] Connecting to Redis at {REDIS_URL}")

            self.client = await redis.from_url(
                REDIS_URL,
                password=REDIS_PASSWORD,
                decode_responses=True,
                max_connections=10,
                socket_keepalive=True,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )

            # Test connection
            await self.client.ping()
            logger.info("[Redis] Connection established successfully")

            # Store globally
            _redis_client = self.client

        except Exception as e:
            logger.error(f"[Redis] Failed to initialize: {e}")
            raise

        return self.client

    async def close_redis(self):
        """Close Redis connection pool gracefully"""
        global _redis_client

        if self.client:
            try:
                await self.client.close()
                await self.client.connection_pool.disconnect()
                logger.info("[Redis] Connection closed successfully")
            except Exception as e:
                logger.error(f"[Redis] Error during shutdown: {e}")
            finally:
                self.client = None
                _redis_client = None

    def get_client(self) -> Redis:
        """
        Get Redis client instance.

        Returns:
            Redis client

        Raises:
            RuntimeError: If Redis is not initialized
        """
        if not self.client:
            raise RuntimeError("Redis not initialized. Call init_redis() first.")
        return self.client

    async def ping(self) -> bool:
        """
        Health check for Redis connection.

        Returns:
            True if Redis is reachable
        """
        try:
            await self.get_client().ping()
            return True
        except Exception as e:
            logger.error(f"[Redis] Ping failed: {e}")
            return False

    # ===== Session Management =====

    async def set_session(self, key: str, value: dict, expire_seconds: int = 1800):
        """
        Store user session data with expiration.

        Args:
            key: Session key
            value: Session data dictionary
            expire_seconds: Expiration time in seconds (default 30 minutes)
        """
        try:
            await self.get_client().setex(
                f"session:{key}",
                expire_seconds,
                json.dumps(value, default=str),
            )
            logger.debug(f"[Redis] Set session: {key}")
        except Exception as e:
            logger.error(f"[Redis] Failed to set session {key}: {e}")
            raise

    async def get_session(self, key: str) -> Optional[dict]:
        """
        Retrieve user session data.

        Args:
            key: Session key

        Returns:
            Session data dictionary or None
        """
        try:
            data = await self.get_client().get(f"session:{key}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"[Redis] Failed to get session {key}: {e}")
            return None

    async def delete_session(self, key: str):
        """
        Delete user session.

        Args:
            key: Session key
        """
        try:
            await self.get_client().delete(f"session:{key}")
            logger.debug(f"[Redis] Deleted session: {key}")
        except Exception as e:
            logger.error(f"[Redis] Failed to delete session {key}: {e}")

    # ===== Cache Management =====

    async def set_cache(self, key: str, value: Any, expire_seconds: int = 300):
        """
        Set cache with expiration.

        Args:
            key: Cache key
            value: Value to cache
            expire_seconds: Expiration time in seconds (default 5 minutes)
        """
        try:
            await self.get_client().setex(
                f"cache:{key}",
                expire_seconds,
                json.dumps(value, default=str),
            )
            logger.debug(f"[Redis] Set cache: {key}")
        except Exception as e:
            logger.error(f"[Redis] Failed to set cache {key}: {e}")

    async def get_cache(self, key: str) -> Optional[Any]:
        """
        Get cached data.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        try:
            data = await self.get_client().get(f"cache:{key}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"[Redis] Failed to get cache {key}: {e}")
            return None

    async def delete_cache(self, key: str):
        """
        Delete cached data.

        Args:
            key: Cache key
        """
        try:
            await self.get_client().delete(f"cache:{key}")
            logger.debug(f"[Redis] Deleted cache: {key}")
        except Exception as e:
            logger.error(f"[Redis] Failed to delete cache {key}: {e}")

    # ===== Stream Management =====

    async def init_consumer_group(
        self, stream_name: str = None, group_name: str = None
    ):
        """
        Initialize consumer group if it doesn't exist.

        Args:
            stream_name: Stream name (defaults to REDIS_STREAM_NAME)
            group_name: Consumer group name (defaults to DEFAULT_CONSUMER_GROUP)
        """
        stream_name = stream_name or REDIS_STREAM_NAME
        group_name = group_name or DEFAULT_CONSUMER_GROUP

        try:
            await self.get_client().xgroup_create(
                stream_name, group_name, id="0", mkstream=True
            )
            logger.info(
                f"[Redis] Created consumer group: {group_name} on {stream_name}"
            )
        except ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"[Redis] Consumer group already exists: {group_name}")
            else:
                logger.error(f"[Redis] Error creating consumer group: {e}")
                raise

    async def add_to_stream(
        self, stream_name: str, event_type: str, data: dict, max_len: int = 10000
    ) -> str:
        """
        Add message to Redis Stream.

        Args:
            stream_name: Stream name
            event_type: Type of event to emit
            data: Event data dictionary
            max_len: Maximum stream length (prevents unbounded growth)

        Returns:
            Message ID from Redis

        Raises:
            RuntimeError: If Redis is not initialized
            redis.RedisError: If write operation fails
        """
        try:
            message_id = await self.get_client().xadd(
                stream_name,
                {"event": event_type, **data},
                maxlen=max_len,
                approximate=True,
            )
            logger.debug(
                f"[Redis] Added event to {stream_name}: {event_type} (ID: {message_id})"
            )
            return message_id
        except Exception as e:
            logger.error(
                f"[Redis] Failed to add event {event_type} to {stream_name}: {e}"
            )
            raise

    async def read_stream(
        self,
        stream_name: str = None,
        consumer_group: str = None,
        consumer_name: str = None,
        block: int = 5000,
        count: int = 10,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        """
        Read from Redis Stream using consumer groups for reliable delivery.

        Args:
            stream_name: Name of the Redis stream (defaults to REDIS_STREAM_NAME)
            consumer_group: Consumer group name (defaults to DEFAULT_CONSUMER_GROUP)
            consumer_name: Consumer name for this connection
            block: Block time in milliseconds (default 5000)
            count: Maximum messages to fetch per read (default 10)

        Yields:
            Tuple of (message_id, data_dict)
        """
        stream_name = stream_name or REDIS_STREAM_NAME
        consumer_group = consumer_group or DEFAULT_CONSUMER_GROUP

        if not consumer_name:
            raise ValueError("consumer_name is required for read_stream")

        logger.info(
            f"[Redis] Starting stream reader (group: {consumer_group}, "
            f"consumer: {consumer_name}, stream: {stream_name})"
        )

        # Ensure consumer group exists
        await self.init_consumer_group(stream_name, consumer_group)

        error_count = 0
        max_errors = 5

        while True:
            try:
                messages = await self.get_client().xreadgroup(
                    groupname=consumer_group,
                    consumername=consumer_name,
                    streams={stream_name: ">"},
                    count=count,
                    block=block,
                )

                error_count = 0

                if messages:
                    for _, stream_messages in messages:
                        for msg_id, fields in stream_messages:
                            try:
                                yield msg_id, fields
                                await self.get_client().xack(
                                    stream_name, consumer_group, msg_id
                                )
                                logger.debug(f"[Redis] Processed message: {msg_id}")
                            except Exception as e:
                                logger.error(
                                    f"[Redis] Error processing message {msg_id}: {e}"
                                )
                else:
                    yield None, None

            except asyncio.CancelledError:
                logger.info(f"[Redis] Stream reader cancelled: {consumer_name}")
                break

            except Exception as e:
                error_count += 1
                logger.error(
                    f"[Redis] Error reading stream (attempt {error_count}): {e}"
                )

                if error_count >= max_errors:
                    logger.critical("[Redis] Too many errors, stopping reader")
                    break

                await asyncio.sleep(min(error_count * 2, 30))

    async def get_stream_info(self, stream_name: str = None) -> dict:
        """
        Get information about the stream for monitoring.

        Args:
            stream_name: Name of the Redis stream (defaults to REDIS_STREAM_NAME)

        Returns:
            Dictionary with stream information
        """
        stream_name = stream_name or REDIS_STREAM_NAME

        try:
            info = await self.get_client().xinfo_stream(stream_name)

            try:
                groups = await self.get_client().xinfo_groups(stream_name)
                info["groups"] = groups
            except ResponseError:
                info["groups"] = []

            return info
        except ResponseError:
            return {"error": "Stream does not exist"}
        except Exception as e:
            logger.error(f"[Redis] Error getting stream info: {e}")
            return {"error": str(e)}


# Global Redis service instance
redis_service = RedisService()


# Convenience functions for backward compatibility
async def init_redis() -> Redis:
    """Initialize Redis connection."""
    return await redis_service.init_redis()


async def close_redis():
    """Close Redis connection."""
    await redis_service.close_redis()


def get_redis() -> Redis:
    """Get Redis client instance."""
    return redis_service.get_client()
