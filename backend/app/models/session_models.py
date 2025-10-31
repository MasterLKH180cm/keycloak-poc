"""
Comprehensive session models for the radiology dictation system.

This module contains both SQLAlchemy database models and Pydantic API models
for session management, including:
- Database models: Session and SessionEvent tables for persistent storage
- API models: Request/response models for session management endpoints
- WebSocket models: Connection and status management models
- Study operation models: Open/close study event models

The session management system tracks multi-event user sessions across
Viewer, Dictation, and Worklist applications, synchronizing state via
Redis Streams with unique event_id tracking.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator
from sqlalchemy import ARRAY, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# SQLAlchemy Base for database models
Base = declarative_base()


# ===== DATABASE MODELS =====


class Session(Base):
    """
    User session tracking table.

    Stores session information with unique session_id derived from Keycloak
    session_state or generated UUID. Each session can contain multiple events.
    """

    __tablename__ = "sessions"

    session_id = Column(
        String,
        primary_key=True,
        comment="Session ID from Keycloak session_state or generated UUID",
    )
    userid = Column(
        String, nullable=False, index=True, comment="User ID from JWT sub claim"
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Session creation timestamp",
    )
    last_updated = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last activity timestamp",
    )

    # Relationships
    events = relationship(
        "SessionEvent", back_populates="session", cascade="all, delete-orphan"
    )


class SessionEvent(Base):
    """
    Session events tracking table.

    Stores individual events within a session (open_study, close_study, etc.)
    with full context and target application information for Redis streaming.
    """

    __tablename__ = "session_events"

    event_id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique event identifier",
    )
    session_id = Column(
        String,
        ForeignKey("sessions.session_id"),
        nullable=False,
        index=True,
        comment="Reference to parent session",
    )
    userid = Column(
        String, nullable=False, index=True, comment="User ID for query optimization"
    )
    event = Column(
        String, nullable=False, comment="Event type: open_study, close_study, etc."
    )
    studyid = Column(
        String, nullable=True, comment="Study identifier for study-related events"
    )
    datetime = Column(
        DateTime(timezone=True), nullable=False, comment="Event occurrence timestamp"
    )
    source = Column(
        String, nullable=False, comment="Source application triggering the event"
    )
    target = Column(
        ARRAY(String),
        nullable=True,
        comment="Target applications for event propagation",
    )

    # Store additional event data as JSON string
    event_data = Column(
        Text, nullable=True, comment="JSON-encoded additional event data"
    )

    # Relationship
    session = relationship("Session", back_populates="events")


# ===== ENUMS =====


class AppType(str, Enum):
    """Enumeration of valid application types for WebSocket connections and event routing."""

    DICTATION = "dictation"
    VIEWER = "viewer"
    WORKLIST = "worklist"
    ADMIN = "admin"


# ===== SESSION MANAGEMENT API MODELS =====


class StudyOpenedRequest(BaseModel):
    """
    Request model for opening a study.

    Used by /session/api/study_opened endpoint to register study open events
    with full patient and study context for cross-application synchronization.
    """

    study_id: str = Field(..., description="Unique study identifier")
    patient_id: str = Field(
        ..., description="Patient identifier (e.g., 'SSE_Leia, Princess')"
    )
    patient_dob: str = Field(..., description="Patient date of birth (ISO format)")
    accession_number: str = Field(..., description="Study accession number")
    current_study_name: str = Field(
        ..., description="Human-readable study name/description"
    )
    source: str = Field(..., description="Source application initiating the event")
    target: List[str] = Field(
        ..., description="Target applications to receive the event"
    )

    @validator(
        "study_id", "patient_id", "accession_number", "current_study_name", "source"
    )
    def validate_non_empty_strings(cls, v):
        """Validate that required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @validator("target")
    def validate_target_apps(cls, v):
        """Validate target applications against allowed app types."""
        if not v:
            raise ValueError("At least one target application is required")
        valid_apps = ["viewer", "dictation", "worklist", "admin"]
        for app in v:
            if app not in valid_apps:
                raise ValueError(
                    f"Invalid target app: {app}. Must be one of: {valid_apps}"
                )
        return v


class StudyClosedRequest(BaseModel):
    """
    Request model for closing a study.

    Used by /session/api/study_closed endpoint to register study close events
    and notify target applications to close the study.
    """

    study_id: str = Field(..., description="Study identifier to close")
    source: str = Field(
        ..., description="Source application initiating the close event"
    )
    target: List[str] = Field(
        ..., description="Target applications to receive the close event"
    )

    @validator("study_id", "source")
    def validate_non_empty_strings(cls, v):
        """Validate that required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @validator("target")
    def validate_target_apps(cls, v):
        """Validate target applications against allowed app types."""
        if not v:
            raise ValueError("At least one target application is required")
        valid_apps = ["viewer", "dictation", "worklist", "admin"]
        for app in v:
            if app not in valid_apps:
                raise ValueError(
                    f"Invalid target app: {app}. Must be one of: {valid_apps}"
                )
        return v


class SessionEventResponse(BaseModel):
    """
    Response model for session events.

    Contains complete event information including IDs, timestamps,
    and routing information for client applications.
    """

    event_id: str = Field(..., description="Unique event identifier (UUID)")
    session_id: str = Field(..., description="Session identifier")
    event: str = Field(..., description="Event type (open_study, close_study)")
    studyid: Optional[str] = Field(None, description="Study identifier if applicable")
    datetime: str = Field(..., description="Event timestamp (ISO format)")
    source: str = Field(..., description="Source application")
    target: List[str] = Field(..., description="Target applications")


class StudyEventResponse(BaseModel):
    """
    Response model for study event operations.

    Returns success confirmation with event details and Redis stream
    event ID for tracking message propagation.
    """

    message: str = Field(..., description="Success confirmation message")
    redis_event_id: Optional[str] = Field(
        None, description="Redis stream event ID for tracking"
    )
    event: SessionEventResponse = Field(..., description="Complete event details")


class SessionStateResponse(BaseModel):
    """
    Response model for session state retrieval.

    Contains complete session information including all events
    and associated user information from JWT token.
    """

    session: Dict[str, Any] = Field(
        ..., description="Session information with events list"
    )
    user_info: Dict[str, Any] = Field(
        ..., description="User information from JWT token"
    )


# ===== LEGACY SESSION STATE MODEL =====


class SessionState(BaseModel):
    """
    Legacy session state model for backward compatibility.

    Tracks currently open studies in viewer and dictation applications.
    This model is maintained for existing API compatibility while
    the new event-based system provides enhanced functionality.
    """

    userid: str = Field(..., description="Unique user identifier")
    opened_viewer_studyid: Optional[str] = Field(
        None, description="Study ID currently open in viewer application"
    )
    opened_viewer_datetime: Optional[datetime] = Field(
        None, description="Timestamp when viewer study was opened"
    )
    opened_dictation_studyid: Optional[str] = Field(
        None, description="Study ID currently open in dictation application"
    )
    opened_dictation_datetime: Optional[datetime] = Field(
        None, description="Timestamp when dictation study was opened"
    )

    @validator("userid")
    def validate_userid(cls, v):
        """Validate user ID format and length."""
        if not v or not v.strip():
            raise ValueError("User ID cannot be empty")
        if len(v.strip()) < 3:
            raise ValueError("User ID must be at least 3 characters")
        return v.strip()

    class Config:
        """Pydantic model configuration."""

        use_enum_values = True
        validate_assignment = True
        extra = "forbid"  # Don't allow extra fields


# ===== STUDY OPERATION RESPONSE MODELS =====


class StudyOpenedResponse(BaseModel):
    """Response model for successful study opening in specific applications."""

    message: str = Field(..., description="Success message")
    study_id: str = Field(..., description="Opened study identifier")
    datetime: str = Field(..., description="ISO timestamp of when study was opened")
    user_id: str = Field(..., description="User who opened the study")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "message": "Study ABC123 opened for viewer",
                "study_id": "ABC123",
                "datetime": "2025-01-15T10:30:00.000Z",
                "user_id": "user_123",
            }
        }


class StudyClosedResponse(BaseModel):
    """Response model for successful study closing in specific applications."""

    message: str = Field(..., description="Success message")
    study_id: str = Field(..., description="Closed study identifier")
    user_id: str = Field(..., description="User who closed the study")

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "message": "Study ABC123 closed for viewer",
                "study_id": "ABC123",
                "user_id": "user_123",
            }
        }


# ===== WEBSOCKET CONNECTION MODELS =====


class WebSocketConnectionRequest(BaseModel):
    """Request model for WebSocket connection registration."""

    app_id: AppType = Field(
        ..., description="Application type for WebSocket connection"
    )
    client_info: Optional[dict] = Field(
        default_factory=dict,
        description="Additional client information (browser, version, etc.)",
    )


class WebSocketResponse(BaseModel):
    """Response model for WebSocket connection registration."""

    message: str = Field(
        ..., description="Response message with connection instructions"
    )
    app_id: str = Field(..., description="Application type")
    user_id: str = Field(..., description="User identifier")
    connection_info: Optional[dict] = Field(
        default_factory=dict, description="Additional connection information"
    )


class WebSocketStatusResponse(BaseModel):
    """Response model for WebSocket connection status check."""

    user_id: str = Field(..., description="User identifier")
    app_id: str = Field(..., description="Application type")
    connected: bool = Field(..., description="Whether connection is currently active")
    session_id: Optional[str] = Field(
        None, description="WebSocket session identifier if connected"
    )
    connected_since: Optional[datetime] = Field(
        None, description="Connection establishment timestamp"
    )


class ActiveConnectionsResponse(BaseModel):
    """Response model for retrieving all active WebSocket connections for a user."""

    user_id: str = Field(..., description="User identifier")
    active_connections: dict = Field(
        default_factory=dict, description="Dictionary of active connections by app type"
    )
    total_connections: int = Field(
        ..., description="Total number of active connections"
    )


# ===== USER MANAGEMENT MODELS =====


class LogoutResponse(BaseModel):
    """Response model for user logout operation."""

    message: str = Field(..., description="Logout confirmation message")
    user_id: str = Field(..., description="User who logged out")
    cleared_sessions: int = Field(..., description="Number of sessions cleared")
    disconnected_websockets: int = Field(
        ..., description="Number of WebSocket connections closed"
    )


# ===== ERROR HANDLING MODELS =====


class ErrorResponse(BaseModel):
    """Standard error response model for consistent error handling."""

    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Additional error details")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Error timestamp",
    )
