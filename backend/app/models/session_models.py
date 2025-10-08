"""
Session models for the radiology dictation system.

This module contains Pydantic models for session management,
including user sessions, study operations, and WebSocket connections.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator


class AppType(str, Enum):
    """Enumeration of valid application types for WebSocket connections."""

    DICTATION = "dictation"
    VIEWER = "viewer"
    WORKLIST = "worklist"
    ADMIN = "admin"


class SessionState(BaseModel):
    """
    Represents the current session state for a user.

    Tracks which studies are currently open in different applications
    and when they were opened.
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


class StudyOpenedRequest(BaseModel):
    """Request model for opening a study."""

    study_id: str = Field(..., min_length=1, description="Study identifier")
    metadata: Optional[dict] = Field(
        default_factory=dict, description="Additional study metadata"
    )

    @validator("study_id")
    def validate_study_id(cls, v):
        """Validate study ID format."""
        if not v or not v.strip():
            raise ValueError("Study ID cannot be empty")
        return v.strip()


class StudyOpenedResponse(BaseModel):
    """Response model for successful study opening."""

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
    """Response model for successful study closing."""

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


class WebSocketConnectionRequest(BaseModel):
    """Request model for WebSocket connection registration."""

    app_id: AppType = Field(
        ..., description="Application type for WebSocket connection"
    )
    client_info: Optional[dict] = Field(
        default_factory=dict, description="Additional client information"
    )


class WebSocketResponse(BaseModel):
    """Response model for WebSocket connection registration."""

    message: str = Field(..., description="Response message")
    app_id: str = Field(..., description="Application type")
    user_id: str = Field(..., description="User identifier")
    connection_info: Optional[dict] = Field(
        default_factory=dict, description="Additional connection information"
    )


class WebSocketStatusResponse(BaseModel):
    """Response model for WebSocket connection status."""

    user_id: str = Field(..., description="User identifier")
    app_id: str = Field(..., description="Application type")
    connected: bool = Field(..., description="Whether connection is active")
    session_id: Optional[str] = Field(None, description="WebSocket session identifier")
    connected_since: Optional[datetime] = Field(
        None, description="Connection timestamp"
    )


class ActiveConnectionsResponse(BaseModel):
    """Response model for active WebSocket connections."""

    user_id: str = Field(..., description="User identifier")
    active_connections: dict = Field(
        default_factory=dict, description="Dictionary of active connections by app type"
    )
    total_connections: int = Field(
        ..., description="Total number of active connections"
    )


class LogoutResponse(BaseModel):
    """Response model for user logout."""

    message: str = Field(..., description="Logout confirmation message")
    user_id: str = Field(..., description="User who logged out")
    cleared_sessions: int = Field(..., description="Number of sessions cleared")
    disconnected_websockets: int = Field(
        ..., description="Number of WebSocket connections closed"
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Additional error details")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Error timestamp",
    )


class PatientInfo(BaseModel):
    """Model for patient information from Redis stream."""

    id: str = Field(..., description="Patient identifier")
    name: str = Field(..., description="Patient full name")
    birthday: str = Field(..., description="Patient date of birth")
    gender: Optional[str] = Field(None, description="Patient gender")
    mrn: Optional[str] = Field(None, description="Medical record number")

    @validator("name")
    def validate_name(cls, v):
        """Validate patient name."""
        if not v or not v.strip():
            raise ValueError("Patient name cannot be empty")
        return v.strip()

    @validator("birthday")
    def validate_birthday(cls, v):
        """Validate birthday format."""
        if not v:
            raise ValueError("Birthday is required")
        # Add more specific date validation if needed
        return v

    class Config:
        """Pydantic model configuration."""

        extra = "forbid"


class DictationConfig(BaseModel):
    """Configuration model for dictation session."""

    study_id: str = Field(..., description="Study identifier for dictation")
    language: str = Field("en-US", description="Language code for speech recognition")
    sample_rate: int = Field(16000, description="Audio sample rate in Hz")
    encoding: str = Field("linear16", description="Audio encoding format")
    enable_automatic_punctuation: bool = Field(
        True, description="Enable automatic punctuation"
    )
    enable_word_time_offsets: bool = Field(
        False, description="Enable word-level timestamps"
    )

    @validator("sample_rate")
    def validate_sample_rate(cls, v):
        """Validate audio sample rate."""
        valid_rates = [8000, 16000, 22050, 44100, 48000]
        if v not in valid_rates:
            raise ValueError(f"Sample rate must be one of: {valid_rates}")
        return v

    class Config:
        """Pydantic model configuration."""

        extra = "forbid"


class TranscriptionResult(BaseModel):
    """Model for transcription results."""

    transcript: str = Field(..., description="Transcribed text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    is_final: bool = Field(..., description="Whether this is the final result")
    alternatives: Optional[list] = Field(
        None, description="Alternative transcription results"
    )
    word_timestamps: Optional[list] = Field(None, description="Word-level timestamps")

    class Config:
        """Pydantic model configuration."""

        extra = "forbid"
