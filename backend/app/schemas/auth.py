from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request model for user login"""

    username: str = Field(..., description="Username or email", min_length=1)
    password: str = Field(..., description="User password", min_length=1)


class LoginResponse(BaseModel):
    """Response model for successful login"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="Refresh token for token renewal")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: "UserResponse" = Field(..., description="User information")


class TokenRefreshRequest(BaseModel):
    """Request model for token refresh"""

    refresh_token: str = Field(..., description="Valid refresh token")


class TokenRefreshResponse(BaseModel):
    """Response model for token refresh"""

    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(
        ..., description="Refresh token (may be the same or new)"
    )
    expires_in: int = Field(..., description="Token expiration time in seconds")
    token_type: str = Field(default="bearer", description="Token type")


class LogoutRequest(BaseModel):
    """Request model for user logout"""

    refresh_token: str = Field(..., description="Refresh token to invalidate")


class LogoutResponse(BaseModel):
    """Response model for logout"""

    message: str = Field(
        default="Logged out successfully", description="Success message"
    )


class UserProfileResponse(BaseModel):
    """Response model for current user profile"""

    id: str = Field(..., description="User ID")
    keycloak_id: str = Field(..., description="Keycloak user ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    email_verified: bool = Field(..., description="Email verification status")
    enable: bool = Field(..., description="User active status")
    created_at: Optional[datetime] = Field(
        None, description="Account creation timestamp"
    )
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    class Config:
        from_attributes = True


# Import UserResponse to avoid circular imports
try:
    from app.schemas.user import UserResponse

    LoginResponse.model_rebuild()
except ImportError:
    # Handle circular import by deferring the import
    pass
