import logging
from datetime import datetime

from app.core.security import get_current_user
from app.db.redis import get_redis
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    TokenRefreshRequest,
    UserResponse,
)
from app.services.keycloak_service import keycloak_service
from fastapi import APIRouter, Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
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

        # Get user info from Keycloak
        userinfo = auth_result["userinfo"]

        # Create session in Redis
        session_data = {
            "user_id": userinfo["sub"],
            "keycloak_id": userinfo["sub"],
            "username": userinfo["preferred_username"],
            "email": userinfo["email"],
            "first_name": userinfo.get("given_name", ""),
            "last_name": userinfo.get("family_name", ""),
            "role": userinfo.get("role", "user"),
            "login_time": datetime.utcnow().isoformat(),
            "ip_address": client_ip,
            "user_agent": user_agent,
        }

        await redis_client.set_session(
            userinfo["sub"],
            session_data,
            expire_seconds=1800,  # 30 minutes
        )

        # Create user response from Keycloak data
        user_response = UserResponse(
            id=userinfo["sub"],
            keycloak_id=userinfo["sub"],
            username=userinfo["preferred_username"],
            email=userinfo["email"],
            first_name=userinfo.get("given_name", ""),
            last_name=userinfo.get("family_name", ""),
            email_verified=userinfo.get("email_verified", False),
            is_active=userinfo.get("enabled", True),
            role=userinfo.get("role", "user"),
            department=userinfo.get("department"),
            license_number=userinfo.get("license_number"),
            npi_number=userinfo.get("npi_number"),
            created_at=None,
            updated_at=None,
            last_login=datetime.utcnow(),
        )

        return LoginResponse(
            access_token=auth_result["access_token"],
            refresh_token=auth_result["refresh_token"],
            expires_in=auth_result["expires_in"],
            user=user_response,
        )

    except ValueError as e:
        logger.warning(
            f"Failed login attempt for {login_data.username} from {client_ip}: {e}"
        )
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
    refresh_data: TokenRefreshRequest,
    current_user: dict = Depends(get_current_user),
    redis_client=Depends(get_redis),
):
    """Logout user and invalidate session"""
    print(current_user, refresh_data)
    try:
        # Remove session from Redis
        await redis_client.delete_session(current_user["keycloak_id"])

        # Optionally logout from Keycloak
        await keycloak_service.logout_user(refresh_data.refresh_token)

        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    try:
        # Get user info from Keycloak
        userinfo = await keycloak_service.get_user_info(current_user["id"])

        user_response = UserResponse(
            id=userinfo["id"],
            keycloak_id=userinfo["id"],
            username=userinfo["username"],
            email=userinfo["email"],
            first_name=userinfo.get("firstName", ""),
            last_name=userinfo.get("lastName", ""),
            email_verified=userinfo.get("emailVerified", False),
            is_active=userinfo.get("enabled", True),
            role=userinfo.get("attributes", {}).get("role", ["user"])[0]
            if userinfo.get("attributes", {}).get("role")
            else "user",
            department=userinfo.get("attributes", {}).get("department", [None])[0],
            license_number=userinfo.get("attributes", {}).get("license_number", [None])[
                0
            ],
            npi_number=userinfo.get("attributes", {}).get("npi_number", [None])[0],
            created_at=None,
            updated_at=None,
            last_login=None,
        )

        return user_response

    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


async def log_failed_login(username: str, ip_address: str, user_agent: str, error: str):
    """Log failed login attempt"""
    logger.warning(f"Failed login attempt for {username} from {ip_address}: {error}")
