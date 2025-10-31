# filepath: c:\Users\angel\keycloak-poc\backend\app\schemas\user_management.py
from typing import List, Optional

from app.schemas.user import UserResponse
from pydantic import BaseModel, Field


class UserListRequest(BaseModel):
    """Request model for listing users with filters and pagination"""

    skip: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(
        default=100, ge=1, le=1000, description="Number of records to return"
    )
    role: Optional[str] = Field(None, description="Filter by role")
    enable: Optional[bool] = Field(None, description="Filter by active status")


class UserListResponse(BaseModel):
    """Response model for user list"""

    users: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    skip: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Number of records returned")

    class Config:
        from_attributes = True


class PasswordResetRequest(BaseModel):
    """Request model for password reset"""

    password: str = Field(
        ..., min_length=12, description="New password (min 12 characters)"
    )
    temporary: bool = Field(default=True, description="Whether password is temporary")


class PasswordResetResponse(BaseModel):
    """Response model for password reset"""

    message: str = Field(
        default="Password reset successfully", description="Success message"
    )


class UserActivationResponse(BaseModel):
    """Response model for user activation/deactivation"""

    message: str = Field(..., description="Operation result message")


class UserDeletionResponse(BaseModel):
    """Response model for user deletion"""

    message: str = Field(
        default="User deleted successfully", description="Success message"
    )


class ErrorResponse(BaseModel):
    """Standard error response model"""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    timestamp: Optional[str] = Field(None, description="Error timestamp")

    class Config:
        from_attributes = True
