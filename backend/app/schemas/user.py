import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Username must be 3-50 characters",
    )
    email: EmailStr = Field(..., description="Valid email address required")
    first_name: str = Field(
        ..., min_length=1, max_length=100, description="First name required"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=100, description="Last name required"
    )

    @validator("username")
    def validate_username(cls, v):
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, underscores, and hyphens"
            )
        return v.lower()


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
    id: str = Field(..., description="User ID (same as Keycloak ID)")
    keycloak_id: str = Field(..., description="Keycloak user ID (for internal use)")
    enable: bool
    email_verified: bool
    last_login: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = Field(None, description="Valid email address")
