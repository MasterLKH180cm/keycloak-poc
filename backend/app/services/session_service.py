"""
Session management service for user sessions.

Handles user session state, study tracking, and connection management
using Redis as the backend store.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.session_models import SessionState

logger = logging.getLogger(__name__)


class SessionService:
    """Service for managing user sessions with Redis backend."""

    def __init__(self, redis_pool=None):
        """Initialize session service."""
        self.session_prefix = "session:"
        self.session_expire_seconds = settings.access_token_expire_minutes * 60
        self.redis_pool = redis_pool

    def _get_session_key(self, user_id: str) -> str:
        """
        Generate Redis key for user session.

        Args:
            user_id: User identifier

        Returns:
            str: Redis key for session
        """
        return f"{self.session_prefix}{user_id}"

    async def get_session(self, user_id: str) -> SessionState:
        """
        Retrieve user session state from Redis.

        Args:
            user_id: User identifier

        Returns:
            SessionState: Current session state

        Raises:
            RuntimeError: If Redis is not initialized
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            session_key = self._get_session_key(user_id)
            session_data = await self.redis_pool.hgetall(session_key)

            if not session_data:
                # Return default empty session
                logger.debug(f"No session found for user {user_id}, returning default")
                return SessionState(
                    user_id=user_id,
                    opened_viewer_studyid=None,
                    opened_viewer_datetime=None,
                    active_connections=[],
                    last_activity=datetime.now(timezone.utc).isoformat(),
                )

            # Parse session data
            return SessionState(
                user_id=user_id,
                opened_viewer_studyid=session_data.get("opened_viewer_studyid"),
                opened_viewer_datetime=session_data.get("opened_viewer_datetime"),
                active_connections=json.loads(
                    session_data.get("active_connections", "[]")
                ),
                last_activity=session_data.get(
                    "last_activity", datetime.now(timezone.utc).isoformat()
                ),
                metadata=json.loads(session_data.get("metadata", "{}")),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse session data for user {user_id}: {e}")
            # Return default session on parse error
            return SessionState(
                user_id=user_id,
                opened_viewer_studyid=None,
                opened_viewer_datetime=None,
                active_connections=[],
                last_activity=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.exception(f"Error retrieving session for user {user_id}: {e}")
            raise

    async def update_session(
        self,
        user_id: str,
        opened_viewer_studyid: Optional[str] = None,
        opened_viewer_datetime: Optional[datetime] = None,
        active_connections: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SessionState:
        """
        Update user session state in Redis.

        Args:
            user_id: User identifier
            opened_viewer_studyid: Study ID opened in viewer (None to clear)
            opened_viewer_datetime: Datetime when study was opened
            active_connections: List of active connection IDs
            metadata: Additional session metadata
            **kwargs: Additional fields to update

        Returns:
            SessionState: Updated session state

        Raises:
            RuntimeError: If Redis is not initialized
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            session_key = self._get_session_key(user_id)

            # Prepare update data
            update_data = {
                "user_id": user_id,
                "last_activity": datetime.now(timezone.utc).isoformat(),
            }

            # Update viewer study info
            if opened_viewer_studyid is not None:
                update_data["opened_viewer_studyid"] = opened_viewer_studyid
            if opened_viewer_datetime is not None:
                update_data["opened_viewer_datetime"] = opened_viewer_datetime

            # Update connections
            if active_connections is not None:
                update_data["active_connections"] = json.dumps(active_connections)

            # Update metadata
            if metadata is not None:
                update_data["metadata"] = json.dumps(metadata)

            # Add any additional kwargs
            for key, value in kwargs.items():
                if value is not None:
                    if isinstance(value, (dict, list)):
                        update_data[key] = json.dumps(value)
                    elif isinstance(value, datetime):
                        update_data[key] = value
                    else:
                        update_data[key] = str(value)

            # Update Redis hash
            await self.redis_pool.hset(session_key, mapping=update_data)

            # Set expiration
            await self.redis_pool.expire(session_key, self.session_expire_seconds)

            logger.debug(f"Updated session for user {user_id}")

            # Return updated session state
            return await self.get_session(user_id)

        except Exception as e:
            logger.exception(f"Error updating session for user {user_id}: {e}")
            raise

    async def clear_session(self, user_id: str) -> int:
        """
        Clear user session from Redis.

        Args:
            user_id: User identifier

        Returns:
            int: Number of sessions cleared (0 or 1)

        Raises:
            RuntimeError: If Redis is not initialized
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            session_key = self._get_session_key(user_id)
            result = await self.redis_pool.delete(session_key)

            logger.info(f"Cleared session for user {user_id}")
            return result

        except Exception as e:
            logger.exception(f"Error clearing session for user {user_id}: {e}")
            raise

    async def add_active_connection(
        self, user_id: str, connection_id: str, app_type: str
    ) -> SessionState:
        """
        Add active connection to user session.

        Args:
            user_id: User identifier
            connection_id: Socket.IO connection ID
            app_type: Application type (dictation/viewer)

        Returns:
            SessionState: Updated session state
        """
        try:
            session = await self.get_session(user_id)

            # Add connection info
            connection_info = {
                "connection_id": connection_id,
                "app_type": app_type,
                "connected_at": datetime.now(timezone.utc).isoformat(),
            }

            active_connections = session.active_connections or []
            active_connections.append(connection_info)

            # Update session
            return await self.update_session(
                user_id, active_connections=active_connections
            )

        except Exception as e:
            logger.exception(
                f"Error adding connection {connection_id} for user {user_id}: {e}"
            )
            raise

    async def remove_active_connection(
        self, user_id: str, connection_id: str
    ) -> SessionState:
        """
        Remove active connection from user session.

        Args:
            user_id: User identifier
            connection_id: Socket.IO connection ID

        Returns:
            SessionState: Updated session state
        """
        try:
            session = await self.get_session(user_id)

            # Remove connection
            active_connections = [
                conn
                for conn in (session.active_connections or [])
                if conn.get("connection_id") != connection_id
            ]

            # Update session
            return await self.update_session(
                user_id, active_connections=active_connections
            )

        except Exception as e:
            logger.exception(
                f"Error removing connection {connection_id} for user {user_id}: {e}"
            )
            raise

    async def get_all_active_users(self) -> List[str]:
        """
        Get all users with active sessions.

        Returns:
            List[str]: List of user IDs with active sessions
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            # Scan for all session keys
            cursor = 0
            user_ids = []

            while True:
                cursor, keys = await self.redis_pool.scan(
                    cursor, match=f"{self.session_prefix}*", count=100
                )

                for key in keys:
                    # Extract user_id from key
                    user_id = key.replace(self.session_prefix, "")
                    user_ids.append(user_id)

                if cursor == 0:
                    break

            return user_ids

        except Exception as e:
            logger.exception(f"Error retrieving active users: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of session service.

        Returns:
            Dict containing health status
        """
        try:
            if not self.redis_pool:
                return {
                    "status": "unhealthy",
                    "error": "Redis not initialized",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Test Redis connection with ping
            await self.redis_pool.ping()

            # Get count of active sessions
            active_users = await self.get_all_active_users()

            return {
                "status": "healthy",
                "redis_connected": True,
                "active_sessions": len(active_users),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Session service health check failed: {e}")
            return {
                "status": "unhealthy",
                "redis_connected": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
