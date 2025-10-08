import logging

from app.dependencies.redis import get_redis_client
from app.services.auth_service import AuthService
from app.services.session_service import SessionService
from app.services.websocket_service import WebSocketService
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)
security = HTTPBearer()


def get_auth_service() -> AuthService:
    """Get authentication service instance."""
    return AuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> str:
    """
    Extract and validate user from JWT token.

    Args:
        credentials: HTTP Bearer token
        auth_service: Authentication service

    Returns:
        str: Validated user ID

    Raises:
        HTTPException: If authentication fails
    """
    try:
        if not credentials or not credentials.credentials:
            logger.warning("No authentication credentials provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No authentication token provided",
                headers={"WWW-Authenticate": "Bearer"},
            )

        print(f"credentials.credentials: {credentials.credentials}")
        user_id = await auth_service.verify_token(credentials.credentials)
        print(f"Authenticated user_id: {user_id}")

        if not user_id:
            logger.warning("Token verification returned empty user_id")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_id
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_session_service() -> SessionService:
    """Get session service instance."""
    redis_client = get_redis_client()
    return SessionService(redis_pool=redis_client)


def get_websocket_service() -> WebSocketService:
    """Get WebSocket service instance."""
    redis_client = get_redis_client()
    return WebSocketService(redis_pool=redis_client)
