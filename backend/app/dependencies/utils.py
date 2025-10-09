import logging
from typing import Any, Dict

from app.services.auth_service import AuthService
from app.services.session_management_service import SessionManagementService
from app.services.session_service import SessionService
from app.services.websocket_service import WebSocketService
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Service instances
_auth_service = None
_session_service = None
_websocket_service = None
_session_management_service = None


def get_auth_service() -> AuthService:
    """Get authentication service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def get_session_service() -> SessionService:
    """Get session service instance."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service


def get_websocket_service() -> WebSocketService:
    """Get WebSocket service instance."""
    global _websocket_service
    if _websocket_service is None:
        _websocket_service = WebSocketService()
    return _websocket_service


def get_session_management_service() -> SessionManagementService:
    """Get session management service instance."""
    global _session_management_service
    if _session_management_service is None:
        _session_management_service = SessionManagementService()
    return _session_management_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> Dict[str, Any]:
    """
    Extract and validate user from JWT token.

    Args:
        credentials: HTTP Bearer token
        auth_service: Authentication service

    Returns:
        Dict[str, Any]: Validated user information

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

        token = credentials.credentials
        user_info = await auth_service.verify_token(token)

        if not user_info.get("sub"):
            logger.warning("Token verification returned empty user_id")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_info
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
