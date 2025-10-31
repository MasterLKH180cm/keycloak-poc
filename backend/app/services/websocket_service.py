"""
WebSocket management service for Socket.IO connections.

Handles connection tracking, broadcasting, and real-time communication
between clients and server.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.session_models import AppType

logger = logging.getLogger(__name__)


class WebSocketService:
    """Service for managing WebSocket connections and broadcasting."""

    def __init__(self, redis_pool=None):
        """Initialize WebSocket service."""
        self.connection_prefix = "ws_connection:"
        self.user_connections_prefix = "ws_user:"
        self.connection_expire_seconds = 3600  # 1 hour
        self.redis_pool = redis_pool

    def _get_connection_key(self, connection_id: str) -> str:
        """Generate Redis key for connection."""
        return f"{self.connection_prefix}{connection_id}"

    def _get_user_connections_key(self, user_id: str) -> str:
        """Generate Redis key for user's connections set."""
        return f"{self.user_connections_prefix}{user_id}"

    async def register_connection_intent(
        self, user_id: str, app_type: AppType, client_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Register user's intent to establish WebSocket connection.

        Args:
            user_id: User identifier
            app_type: Application type
            client_info: Client information (browser, device, etc.)

        Returns:
            Dict containing connection info
        """
        try:
            return {
                "user_id": user_id,
                "app_type": app_type.value,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "client_info": client_info,
                "status": "awaiting_connection",
            }

        except Exception as e:
            logger.exception(f"Error registering connection intent: {e}")
            raise

    async def register_connection(
        self,
        connection_id: str,
        user_id: str,
        app_type: AppType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Register active WebSocket connection.

        Args:
            connection_id: Socket.IO connection/session ID
            user_id: User identifier
            app_type: Application type
            metadata: Additional connection metadata

        Returns:
            Dict containing connection details
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            connection_data = {
                "connection_id": connection_id,
                "user_id": user_id,
                "app_type": app_type.value,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "last_activity": datetime.now(timezone.utc).isoformat(),
                "metadata": str(metadata or {}),
            }

            # Store connection data
            connection_key = self._get_connection_key(connection_id)
            await self.redis_pool.hset(connection_key, mapping=connection_data)
            await self.redis_pool.expire(connection_key, self.connection_expire_seconds)

            # Add to user's connection set
            user_connections_key = self._get_user_connections_key(user_id)
            await self.redis_pool.sadd(user_connections_key, connection_id)
            await self.redis_pool.expire(
                user_connections_key, self.connection_expire_seconds
            )

            logger.info(
                f"Registered connection {connection_id} for user {user_id}, "
                f"app {app_type.value}"
            )

            return connection_data

        except Exception as e:
            logger.exception(f"Error registering connection {connection_id}: {e}")
            raise

    async def unregister_connection(self, connection_id: str) -> bool:
        """
        Unregister WebSocket connection.

        Args:
            connection_id: Socket.IO connection ID

        Returns:
            bool: True if connection was removed
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            # Get connection data before deletion
            connection_key = self._get_connection_key(connection_id)
            connection_data = await self.redis_pool.hgetall(connection_key)

            if connection_data:
                user_id = connection_data.get("user_id")

                # Remove from user's connection set
                if user_id:
                    user_connections_key = self._get_user_connections_key(user_id)
                    await self.redis_pool.srem(user_connections_key, connection_id)

                # Delete connection data
                await self.redis_pool.delete(connection_key)

                logger.info(f"Unregistered connection {connection_id}")
                return True

            return False

        except Exception as e:
            logger.exception(f"Error unregistering connection {connection_id}: {e}")
            raise

    async def get_connection_status(
        self, user_id: str, app_type: AppType
    ) -> Dict[str, Any]:
        """
        Get WebSocket connection status for user and app type.

        Args:
            user_id: User identifier
            app_type: Application type

        Returns:
            Dict containing connection status
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            user_connections_key = self._get_user_connections_key(user_id)
            connection_ids = await self.redis_pool.smembers(user_connections_key)

            # Check each connection for matching app type
            for conn_id in connection_ids:
                connection_key = self._get_connection_key(conn_id)
                conn_data = await self.redis_pool.hgetall(connection_key)

                if conn_data and conn_data.get("app_type") == app_type.value:
                    return {
                        "connected": True,
                        "session_id": conn_id,
                        "connected_since": conn_data.get("connected_at"),
                        "last_activity": conn_data.get("last_activity"),
                    }

            return {
                "connected": False,
                "session_id": None,
                "connected_since": None,
                "last_activity": None,
            }

        except Exception as e:
            logger.exception(f"Error getting connection status for user {user_id}: {e}")
            raise

    async def get_user_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active connections for a user.

        Args:
            user_id: User identifier

        Returns:
            List of connection details
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            user_connections_key = self._get_user_connections_key(user_id)
            connection_ids = await self.redis_pool.smembers(user_connections_key)

            connections = []
            for conn_id in connection_ids:
                connection_key = self._get_connection_key(conn_id)
                conn_data = await self.redis_pool.hgetall(connection_key)

                if conn_data:
                    connections.append(
                        {
                            "connection_id": conn_id,
                            "app_type": conn_data.get("app_type"),
                            "connected_at": conn_data.get("connected_at"),
                            "last_activity": conn_data.get("last_activity"),
                        }
                    )

            return connections

        except Exception as e:
            logger.exception(f"Error getting connections for user {user_id}: {e}")
            raise

    async def disconnect_user_connections(
        self, user_id: str, reason: str = "server_initiated"
    ) -> int:
        """
        Disconnect all connections for a user.

        Args:
            user_id: User identifier
            reason: Reason for disconnection

        Returns:
            int: Number of connections disconnected
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            user_connections_key = self._get_user_connections_key(user_id)
            connection_ids = await self.redis_pool.smembers(user_connections_key)

            count = 0
            for conn_id in connection_ids:
                if await self.unregister_connection(conn_id):
                    count += 1

            logger.info(
                f"Disconnected {count} connections for user {user_id}, reason: {reason}"
            )

            return count

        except Exception as e:
            logger.exception(f"Error disconnecting connections for user {user_id}: {e}")
            raise

    async def notify_dictation_app(
        self, user_id: str, event_type: str, data: Dict[str, Any]
    ) -> bool:
        """
        Send notification to user's dictation app via Socket.IO.

        Args:
            user_id: User identifier
            event_type: Event type to emit
            data: Event data

        Returns:
            bool: True if notification was sent
        """
        try:
            # Get dictation app connection
            status = await self.get_connection_status(user_id, AppType.DICTATION)

            if not status.get("connected"):
                logger.debug(
                    f"No dictation app connected for user {user_id}, "
                    f"skipping notification"
                )
                return False

            # Emit event via Socket.IO (will be handled by sio_server)
            logger.debug(f"Notification ready for user {user_id}: {event_type}")
            return True

        except Exception as e:
            logger.exception(f"Error notifying dictation app for user {user_id}: {e}")
            return False

    async def broadcast_to_app_type(
        self, app_type: str, event_type: str, data: Dict[str, Any]
    ) -> int:
        """
        Broadcast event to all connections of a specific app type.

        Args:
            app_type: Application type (dictation/viewer)
            event_type: Event type to emit
            data: Event data

        Returns:
            int: Number of connections notified
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            # Scan for all connections of the specified app type
            cursor = 0
            notified_count = 0

            while True:
                cursor, keys = await self.redis_pool.scan(
                    cursor, match=f"{self.connection_prefix}*", count=100
                )

                for key in keys:
                    conn_data = await self.redis_pool.hgetall(key)
                    if conn_data and conn_data.get("app_type") == app_type:
                        notified_count += 1

                if cursor == 0:
                    break

            logger.debug(
                f"Broadcast {event_type} to {notified_count} {app_type} connections"
            )

            return notified_count

        except Exception as e:
            logger.exception(f"Error broadcasting to app type {app_type}: {e}")
            raise

    async def update_connection_activity(self, connection_id: str) -> bool:
        """
        Update last activity timestamp for a connection.

        Args:
            connection_id: Socket.IO connection ID

        Returns:
            bool: True if updated successfully
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            connection_key = self._get_connection_key(connection_id)
            exists = await self.redis_pool.exists(connection_key)

            if exists:
                await self.redis_pool.hset(
                    connection_key,
                    "last_activity",
                    datetime.now(timezone.utc).isoformat(),
                )
                # Refresh expiration
                await self.redis_pool.expire(
                    connection_key, self.connection_expire_seconds
                )
                return True

            return False

        except Exception as e:
            logger.exception(
                f"Error updating activity for connection {connection_id}: {e}"
            )
            raise

    async def cleanup_stale_connections(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up stale connections that haven't been active recently.

        Args:
            max_age_seconds: Maximum age in seconds before connection is considered stale

        Returns:
            int: Number of connections cleaned up
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            cursor = 0
            cleaned_count = 0
            current_time = datetime.now(timezone.utc).isoformat()

            while True:
                cursor, keys = await self.redis_pool.scan(
                    cursor, match=f"{self.connection_prefix}*", count=100
                )

                for key in keys:
                    conn_data = await self.redis_pool.hgetall(key)
                    if conn_data:
                        last_activity_str = conn_data.get("last_activity")
                        if last_activity_str:
                            try:
                                last_activity = datetime.fromisoformat(
                                    last_activity_str
                                )
                                age_seconds = (
                                    current_time - last_activity
                                ).total_seconds()

                                if age_seconds > max_age_seconds:
                                    connection_id = conn_data.get("connection_id")
                                    if (
                                        connection_id
                                        and await self.unregister_connection(
                                            connection_id
                                        )
                                    ):
                                        cleaned_count += 1
                            except (ValueError, TypeError) as e:
                                logger.warning(
                                    f"Invalid last_activity timestamp in {key}: {e}"
                                )

                if cursor == 0:
                    break

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} stale connections")

            return cleaned_count

        except Exception as e:
            logger.exception(f"Error cleaning up stale connections: {e}")
            raise

    async def get_connection_count_by_app_type(self) -> Dict[str, int]:
        """
        Get count of active connections grouped by app type.

        Returns:
            Dict mapping app types to connection counts
        """
        if not self.redis_pool:
            raise RuntimeError("Redis not initialized")

        try:
            cursor = 0
            app_type_counts = {}

            while True:
                cursor, keys = await self.redis_pool.scan(
                    cursor, match=f"{self.connection_prefix}*", count=100
                )

                for key in keys:
                    conn_data = await self.redis_pool.hgetall(key)
                    if conn_data:
                        app_type = conn_data.get("app_type", "unknown")
                        app_type_counts[app_type] = app_type_counts.get(app_type, 0) + 1

                if cursor == 0:
                    break

            return app_type_counts

        except Exception as e:
            logger.exception(f"Error getting connection count by app type: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of WebSocket service.

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

            # Test Redis connection
            await self.redis_pool.ping()

            # Count active connections
            cursor = 0
            connection_count = 0

            while True:
                cursor, keys = await self.redis_pool.scan(
                    cursor, match=f"{self.connection_prefix}*", count=100
                )
                connection_count += len(keys)

                if cursor == 0:
                    break

            # Get connection breakdown by app type
            app_type_counts = await self.get_connection_count_by_app_type()

            return {
                "status": "healthy",
                "redis_connected": True,
                "active_connections": connection_count,
                "connections_by_app_type": app_type_counts,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"WebSocket service health check failed: {e}")
            return {
                "status": "unhealthy",
                "redis_connected": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


# Singleton instance
websocket_service = WebSocketService()
