# /app/dependencies.py
"""
Application-wide dependencies for dependency injection.

This module contains reusable dependencies that can be injected
into FastAPI route handlers.
"""

import logging

from app.services.redis_service import redis_service
from fastapi import HTTPException, status
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


async def get_redis_client() -> Redis:
    """
    Dependency to inject Redis client into endpoints.

    Returns:
        Redis client instance

    Raises:
        HTTPException: If Redis is not available

    Example:
        @app.get("/example")
        async def example(redis: Redis = Depends(get_redis_client)):
            await redis.set("key", "value")
    """
    try:
        logger.debug("Acquiring Redis client")
        return redis_service.get_client()
    except RuntimeError as e:
        logger.error(f"Redis not available: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable",
        )
