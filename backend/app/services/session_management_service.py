"""
Session management service for handling multi-event user sessions.

Manages session state, events, and Redis stream publishing for
synchronization across Viewer, Dictation, and Worklist applications.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from app.core.config import settings
from app.models.session_models import Session, SessionEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


class SessionManagementService:
    """Service for managing user sessions and events with Redis streaming."""

    def __init__(self):
        """Initialize session management service."""
        self.redis_client = None
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection."""
        try:
            logger.info(f"password is {settings.redis_password}")
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_keepalive=True,
                password=settings.redis_password,
                socket_keepalive_options={},
                health_check_interval=30,
            )
            logger.info("Redis client initialized for session management")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            self.redis_client = None

    async def get_or_create_session(
        self, user_info: Dict[str, Any], db: AsyncSession
    ) -> str:
        """
        Get or create session ID for user.

        Args:
            user_info: User information from JWT
            db: Database session

        Returns:
            str: Session ID
        """
        # Use session_state from JWT if available, otherwise generate UUID
        session_id = user_info.get("session_state")
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.debug(f"Generated new session_id: {session_id}")

        user_id = user_info["sub"]

        # Check if session exists
        stmt = select(Session).where(Session.session_id == session_id)
        result = await db.execute(stmt)
        existing_session = result.scalar_one_or_none()

        if not existing_session:
            # Create new session
            new_session = Session(
                session_id=session_id,
                userid=user_id,
            )
            db.add(new_session)
            await db.commit()
            logger.info(f"Created new session {session_id} for user {user_id}")
        else:
            # Update last_updated
            existing_session.last_updated = datetime.now(timezone.utc)
            await db.commit()
            logger.debug(f"Updated existing session {session_id}")

        return session_id

    async def create_session_event(
        self,
        session_id: str,
        user_info: Dict[str, Any],
        event_type: str,
        study_id: Optional[str],
        source: str,
        target: List[str],
        event_data: Optional[Dict[str, Any]] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """
        Create a new session event.

        Args:
            session_id: Session identifier
            user_info: User information from JWT
            event_type: Type of event (open_study, close_study)
            study_id: Study identifier
            source: Source application
            target: Target applications
            event_data: Additional event data
            db: Database session

        Returns:
            Dict containing event information
        """
        event_id = str(uuid.uuid4())
        user_id = user_info["sub"]
        event_datetime = datetime.now(timezone.utc)

        # Create session event
        session_event = SessionEvent(
            event_id=event_id,
            session_id=session_id,
            userid=user_id,
            event=event_type,
            studyid=study_id,
            datetime=event_datetime,
            source=source,
            target=target,
            event_data=json.dumps(event_data) if event_data else None,
        )

        db.add(session_event)
        await db.commit()

        event_dict = {
            "event_id": event_id,
            "session_id": session_id,
            "event": event_type,
            "studyid": study_id,
            "datetime": event_datetime.isoformat(),
            "source": source,
            "target": target,
        }

        logger.info(f"Created session event {event_id} for session {session_id}")
        return event_dict

    async def publish_to_redis_stream(
        self,
        event: Dict[str, Any],
        user_info: Dict[str, Any],
        event_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Publish event to Redis stream.

        Args:
            event: Event information
            user_info: User information
            event_data: Additional event data

        Returns:
            str: Redis event ID if successful
        """
        if not self.redis_client:
            logger.warning("Redis client not available, skipping stream publish")
            return None

        try:
            # Prepare stream data
            stream_data = {
                "event": event["event"],
                "data": json.dumps(event_data) if event_data else "{}",
                "user_id": user_info["sub"],
                "session_id": event["session_id"],
                "event_id": event["event_id"],
                "source": event["source"],
                "target": json.dumps(event["target"]),
            }

            # Publish to stream (using dictation_stream as specified)
            redis_event_id = await self.redis_client.xadd(
                "dictation_stream", stream_data
            )

            logger.info(
                f"Published event {event['event_id']} to Redis stream: {redis_event_id}"
            )
            return redis_event_id

        except Exception as e:
            logger.error(f"Failed to publish to Redis stream: {e}")
            return None

    async def get_session_state(
        self, user_info: Dict[str, Any], db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get current session state for user.

        Args:
            user_info: User information from JWT
            db: Database session

        Returns:
            Dict containing session state and events
        """
        session_id = user_info.get("session_state")
        user_id = user_info["sub"]

        if not session_id:
            logger.warning(f"No session_state in JWT for user {user_id}")
            return {
                "session": {
                    "session_id": None,
                    "userid": user_id,
                    "events": [],
                },
                "user_info": {
                    "preferred_username": user_info.get("preferred_username"),
                    "email": user_info.get("email"),
                    "roles": user_info.get("roles", []),
                },
            }

        # Get session with events
        stmt = (
            select(Session)
            .options(selectinload(Session.events))
            .where(Session.session_id == session_id)
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            logger.warning(f"Session {session_id} not found for user {user_id}")
            return {
                "session": {
                    "session_id": session_id,
                    "userid": user_id,
                    "events": [],
                },
                "user_info": {
                    "preferred_username": user_info.get("preferred_username"),
                    "email": user_info.get("email"),
                    "roles": user_info.get("roles", []),
                },
            }

        # Format events
        events = []
        for event in session.events:
            events.append(
                {
                    "event_id": event.event_id,
                    "event": event.event,
                    "studyid": event.studyid,
                    "datetime": event.datetime.isoformat(),
                    "source": event.source,
                    "target": event.target,
                }
            )

        return {
            "session": {
                "session_id": session.session_id,
                "userid": session.userid,
                "events": events,
            },
            "user_info": {
                "preferred_username": user_info.get("preferred_username"),
                "email": user_info.get("email"),
                "roles": user_info.get("roles", []),
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of session management service.

        Returns:
            Dict containing health status
        """
        redis_healthy = False
        redis_error = None

        if self.redis_client:
            try:
                await self.redis_client.ping()
                redis_healthy = True
            except Exception as e:
                redis_error = str(e)

        return {
            "status": "healthy" if redis_healthy else "degraded",
            "redis_connected": redis_healthy,
            "redis_error": redis_error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
