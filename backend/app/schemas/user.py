import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    username: str = Field(
        ..., min_length=3, max_length=50, description="Username must be 3-50 characters"
    )
    email: EmailStr = Field(..., description="Valid email address required")
    first_name: str = Field(
        ..., min_length=1, max_length=100, description="First name required"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=100, description="Last name required"
    )
    department: Optional[str] = Field(
        None, max_length=100, description="User's department"
    )
    role: str = Field(default="user", description="User role in the system")
    license_number: Optional[str] = Field(
        None, max_length=50, description="Professional license number"
    )
    npi_number: Optional[str] = Field(
        None, max_length=10, description="National Provider Identifier"
    )

    @validator("username")
    def validate_username(cls, v):
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, underscores, and hyphens"
            )
        return v.lower()

    @validator("npi_number")
    def validate_npi(cls, v):
        if v and not re.match(r"^\d{10}$", v):
            raise ValueError("NPI number must be exactly 10 digits")
        return v


class UserCreate(UserBase):
    password: str = Field(
        ..., min_length=12, description="Password must be at least 12 characters"
    )

    @validator("password")
    def validate_password_strength(cls, v):
        # Healthcare-grade password requirements
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserResponse(UserBase):
    id: str
    keycloak_id: str
    is_active: bool
    email_verified: bool
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    license_number: Optional[str] = Field(None, max_length=50)
    npi_number: Optional[str] = Field(None, max_length=10)

    @validator("npi_number")
    def validate_npi(cls, v):
        if v and not re.match(r"^\d{10}$", v):
            raise ValueError("NPI number must be exactly 10 digits")
        return v


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Valid refresh token")


class AuditLogResponse(BaseModel):
    id: str
    action: str
    details: Optional[str]
    ip_address: Optional[str]
    success: bool
    timestamp: datetime

    class Config:
        from_attributes = True
