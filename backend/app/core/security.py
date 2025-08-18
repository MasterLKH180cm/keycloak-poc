import logging

from app.db.redis import get_redis
from app.services.keycloak_service import keycloak_service
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)
security = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify JWT token and return user information"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # First try to verify with Keycloak
        userinfo = keycloak_service.openid_client.userinfo(credentials.credentials)

        # Check if user session exists in Redis
        redis_client = await get_redis()
        session_data = await redis_client.get_session(userinfo["sub"])

        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired",
            )

        return {
            "keycloak_id": userinfo["sub"],
            "username": userinfo["preferred_username"],
            "email": userinfo["email"],
            "roles": userinfo.get("realm_access", {}).get("roles", []),
        }

    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise credentials_exception


async def get_current_user(token_data: dict = Depends(verify_token)):
    """Get current authenticated user"""
    return token_data


def require_role(required_role: str):
    """Create a dependency that requires a specific role"""

    def role_checker(current_user: dict = Depends(get_current_user)):
        if required_role not in current_user.get("roles", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return current_user

    return role_checker


# Specific role requirements for healthcare
require_admin = require_role("admin")
require_clinician = require_role("clinician")
require_nurse = require_role("nurse")
