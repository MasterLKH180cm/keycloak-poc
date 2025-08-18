import json
import logging
from typing import Any, Optional

import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None

    async def init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test the connection
            await self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close_redis(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

    async def set_session(self, key: str, value: dict, expire_seconds: int = 1800):
        """Store user session data with expiration"""
        try:
            await self.redis_client.setex(
                f"session:{key}", expire_seconds, json.dumps(value, default=str)
            )
        except Exception as e:
            logger.error(f"Failed to set session {key}: {e}")
            raise

    async def get_session(self, key: str) -> Optional[dict]:
        """Retrieve user session data"""
        try:
            data = await self.redis_client.get(f"session:{key}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get session {key}: {e}")
            return None

    async def delete_session(self, key: str):
        """Delete user session"""
        try:
            await self.redis_client.delete(f"session:{key}")
        except Exception as e:
            logger.error(f"Failed to delete session {key}: {e}")

    async def set_cache(self, key: str, value: Any, expire_seconds: int = 300):
        """Set cache with expiration"""
        try:
            await self.redis_client.setex(
                f"cache:{key}", expire_seconds, json.dumps(value, default=str)
            )
        except Exception as e:
            logger.error(f"Failed to set cache {key}: {e}")

    async def get_cache(self, key: str) -> Optional[Any]:
        """Get cached data"""
        try:
            data = await self.redis_client.get(f"cache:{key}")
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get cache {key}: {e}")
            return None


# Global Redis manager instance
redis_manager = RedisManager()


async def get_redis():
    """Dependency for getting Redis client"""
    return redis_manager
