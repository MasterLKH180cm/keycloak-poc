import logging

from app.db.redis import get_redis
from app.services.keycloak_service import keycloak_service
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# Security configuration
security = HTTPBearer(auto_error=True)

# Constants
BEARER_SCHEME = "Bearer"
UNAUTHORIZED_DETAIL = "Could not validate credentials"
SESSION_EXPIRED_DETAIL = "Session expired"
ROLE_REQUIRED_DETAIL = "Role '{}' required"


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Verify JWT token and return user information.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        dict: User information including keycloak_id, username, email, roles

    Raises:
        HTTPException: 401 if token is invalid or session expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=UNAUTHORIZED_DETAIL,
        headers={"WWW-Authenticate": BEARER_SCHEME},
    )

    try:
        # Verify token with Keycloak and get user info
        access_token = credentials.credentials
        userinfo = keycloak_service.openid_client.userinfo(access_token)

        # Verify user session exists in Redis
        user_id = userinfo["sub"]
        redis_client = await get_redis()
        session_data = await redis_client.get_session(user_id)

        if not session_data:
            logger.warning(f"Session expired for user: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=SESSION_EXPIRED_DETAIL,
            )

        return {
            "keycloak_id": userinfo["sub"],
            "username": userinfo["preferred_username"],
            "email": userinfo["email"],
            "roles": userinfo.get("realm_access", {}).get("roles", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise credentials_exception


async def get_current_user(token_data: dict = Depends(verify_token)) -> dict:
    """
    Get current authenticated user.

    Args:
        token_data: Verified token data from verify_token dependency

    Returns:
        dict: Current user information
    """
    return token_data


def require_role(required_role: str):
    """
    Create a dependency that requires a specific role.

    Args:
        required_role: The role name that is required

    Returns:
        Callable: FastAPI dependency that checks for the required role

    Raises:
        HTTPException: 403 if user lacks the required role
    """

    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = current_user.get("roles", [])
        if required_role not in user_roles:
            username = current_user.get("username", "unknown")
            logger.warning(
                f"Access denied: User '{username}' lacks required role "
                f"'{required_role}'. User roles: {user_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=ROLE_REQUIRED_DETAIL.format(required_role),
            )
        return current_user

    return role_checker


# Specific role requirements for healthcare
require_admin = require_role("admin")
require_clinician = require_role("clinician")
require_nurse = require_role("nurse")
