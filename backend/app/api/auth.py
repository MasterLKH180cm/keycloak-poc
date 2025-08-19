import logging
from datetime import datetime, timedelta

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.redis import get_redis
from app.models.user import User, UserAuditLog
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    TokenRefreshRequest,
    UserResponse,
)
from app.services.keycloak_service import keycloak_service
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis),
):
    """Authenticate user and create session"""
    try:
        # Get client IP and user agent for audit
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "Unknown")
        # Authenticate with Keycloak
        auth_result = await keycloak_service.authenticate_user(
            login_data.username, login_data.password
        )

        # Get or create user in local database
        user = await get_or_create_user_from_keycloak(db, auth_result["userinfo"])
        print(f"User info: {user}")
        # Create session in Redis
        session_data = {
            "user_id": user.id,
            "keycloak_id": user.keycloak_id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "login_time": datetime.utcnow().isoformat(),
            "ip_address": client_ip,
            "user_agent": user_agent,
        }

        await redis_client.set_session(
            user.keycloak_id,
            session_data,
            expire_seconds=1800,  # 30 minutes
        )

        # Update user last login
        user.last_login = datetime.utcnow()
        user.failed_login_attempts = 0
        user.account_locked_until = None

        # Create audit log
        audit_log = UserAuditLog(
            user_id=user.id,
            action="LOGIN",
            details=f"Successful login from {client_ip}",
            ip_address=client_ip,
            user_agent=user_agent,
            success=True,
        )
        db.add(audit_log)
        await db.commit()

        return LoginResponse(
            access_token=auth_result["access_token"],
            refresh_token=auth_result["refresh_token"],
            expires_in=auth_result["expires_in"],
            user=UserResponse.from_orm(user),
        )

    except ValueError as e:
        # Log failed login attempt
        await log_failed_login(db, login_data.username, client_ip, user_agent, str(e))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        )


@router.post("/refresh")
async def refresh_token(
    refresh_data: TokenRefreshRequest, redis_client=Depends(get_redis)
):
    """Refresh access token"""
    try:
        token_result = await keycloak_service.refresh_token(refresh_data.refresh_token)

        return {
            "access_token": token_result["access_token"],
            "refresh_token": token_result.get(
                "refresh_token", refresh_data.refresh_token
            ),
            "expires_in": token_result["expires_in"],
            "token_type": "bearer",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    redis_client=Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    """Logout user and invalidate session"""
    try:
        # Remove session from Redis
        await redis_client.delete_session(current_user["keycloak_id"])

        # Create audit log
        audit_log = UserAuditLog(
            user_id=current_user["keycloak_id"],
            action="LOGOUT",
            details="User logged out successfully",
            success=True,
        )
        db.add(audit_log)
        await db.commit()

        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Get current user profile"""
    user = await db.get(User, {"keycloak_id": current_user["keycloak_id"]})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return UserResponse.from_orm(user)


async def get_or_create_user_from_keycloak(db: AsyncSession, userinfo: dict) -> User:
    """Get existing user or create new one from Keycloak userinfo"""
    # Try to find existing user
    result = await db.execute(select(User).where(User.keycloak_id == userinfo["sub"]))
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
        user = User(
            keycloak_id=userinfo["sub"],
            username=userinfo["preferred_username"],
            email=userinfo["email"],
            first_name=userinfo.get("given_name", ""),
            last_name=userinfo.get("family_name", ""),
            email_verified=userinfo.get("email_verified", False),
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def log_failed_login(
    db: AsyncSession, username: str, ip_address: str, user_agent: str, error: str
):
    """Log failed login attempt"""
    try:
        # Try to find user for failed login tracking
        result = await db.execute(
            select(User).where((User.username == username) | (User.email == username))
        )
        user = result.scalar_one_or_none()

        if user:
            user.failed_login_attempts += 1

            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)

            # Create audit log
            audit_log = UserAuditLog(
                user_id=user.id,
                action="LOGIN_FAILED",
                details=f"Failed login attempt: {error}",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
            )
            db.add(audit_log)

        await db.commit()
    except Exception as e:
        logger.error(f"Failed to log failed login: {e}")
