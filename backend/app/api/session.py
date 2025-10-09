"""
Session management router for the radiology dictation system.

Handles user sessions, study operations, and WebSocket connection management
with proper authentication, validation, and error handling.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.db.database import get_session_db
from app.dependencies.utils import (
    get_current_user,
    get_session_management_service,
    get_session_service,
    get_websocket_service,
)
from app.models.session_models import (
    ActiveConnectionsResponse,
    AppType,
    ErrorResponse,
    LogoutResponse,
    SessionEventResponse,
    SessionState,
    SessionStateResponse,
    StudyClosedRequest,
    StudyClosedResponse,
    StudyEventResponse,
    StudyOpenedRequest,
    StudyOpenedResponse,
    WebSocketConnectionRequest,
    WebSocketResponse,
    WebSocketStatusResponse,
)
from app.services.session_management_service import SessionManagementService
from app.services.session_service import SessionService
from app.services.websocket_service import WebSocketService
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

# Router configuration
router = APIRouter(
    prefix="/session/api",
    tags=["session"],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        403: {"model": ErrorResponse, "description": "Authorization failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

# Logger configuration
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()


# --- New Session Management Endpoints ---
@router.post(
    "/study_opened",
    response_model=StudyEventResponse,
    summary="Register study opened event",
    description="Register a study opened event and broadcast to target applications via Redis Stream",
)
async def study_opened(
    request: StudyOpenedRequest,
    user_info: Dict[str, Any] = Depends(get_current_user),
    session_mgmt_service: SessionManagementService = Depends(
        get_session_management_service
    ),
    db: AsyncSession = Depends(get_session_db),
) -> StudyEventResponse:
    """
    Register a study opened event.

    This endpoint creates a new session event, stores it in the database,
    and publishes it to Redis stream for other applications to consume.
    """
    try:
        logger.info(
            f"User {user_info['preferred_username']} opening study {request.study_id}"
        )

        # Get or create session
        session_id = await session_mgmt_service.get_or_create_session(user_info, db)

        # Prepare event data
        event_data = {
            "studyId": request.study_id,
            "patientId": request.patient_id,
            "patientDOB": request.patient_dob,
            "accessionNumber": request.accession_number,
            "currentStudyName": request.current_study_name,
        }

        # Create session event
        event = await session_mgmt_service.create_session_event(
            session_id=session_id,
            user_info=user_info,
            event_type="open_study",
            study_id=request.study_id,
            source=request.source,
            target=request.target,
            event_data=event_data,
            db=db,
        )

        # Publish to Redis stream
        redis_event_id = await session_mgmt_service.publish_to_redis_stream(
            event, user_info, event_data
        )

        logger.info(f"Successfully registered study_opened event {event['event_id']}")

        return StudyEventResponse(
            message="Study opened successfully",
            redis_event_id=redis_event_id,
            event=SessionEventResponse(**event),
        )

    except Exception as e:
        logger.exception(f"Error registering study_opened event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register study opened event: {str(e)}",
        )


@router.post(
    "/study_closed",
    response_model=StudyEventResponse,
    summary="Register study closed event",
    description="Register a study closed event and broadcast to target applications via Redis Stream",
)
async def study_closed(
    request: StudyClosedRequest,
    user_info: Dict[str, Any] = Depends(get_current_user),
    session_mgmt_service: SessionManagementService = Depends(
        get_session_management_service
    ),
    db: AsyncSession = Depends(get_session_db),
) -> StudyEventResponse:
    """
    Register a study closed event.

    This endpoint creates a new session event, stores it in the database,
    and publishes it to Redis stream for other applications to consume.
    """
    try:
        logger.info(
            f"User {user_info['preferred_username']} closing study {request.study_id}"
        )

        # Get or create session
        session_id = await session_mgmt_service.get_or_create_session(user_info, db)

        # Prepare event data
        event_data = {
            "studyId": request.study_id,
        }

        # Create session event
        event = await session_mgmt_service.create_session_event(
            session_id=session_id,
            user_info=user_info,
            event_type="close_study",
            study_id=request.study_id,
            source=request.source,
            target=request.target,
            event_data=event_data,
            db=db,
        )

        # Publish to Redis stream
        redis_event_id = await session_mgmt_service.publish_to_redis_stream(
            event, user_info, event_data
        )

        logger.info(f"Successfully registered study_closed event {event['event_id']}")

        return StudyEventResponse(
            message="Study closed successfully",
            redis_event_id=redis_event_id,
            event=SessionEventResponse(**event),
        )

    except Exception as e:
        logger.exception(f"Error registering study_closed event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register study closed event: {str(e)}",
        )


@router.get(
    "/get_session_state",
    response_model=SessionStateResponse,
    summary="Get user session state",
    description="Get the current session state and events for the authenticated user",
)
async def get_session_state(
    user_info: Dict[str, Any] = Depends(get_current_user),
    session_mgmt_service: SessionManagementService = Depends(
        get_session_management_service
    ),
    db: AsyncSession = Depends(get_session_db),
) -> SessionStateResponse:
    """Get current session state for the authenticated user."""
    try:
        session_state = await session_mgmt_service.get_session_state(user_info, db)
        logger.debug(
            f"Retrieved session state for user {user_info['preferred_username']}"
        )
        return SessionStateResponse(**session_state)

    except Exception as e:
        logger.exception(
            f"Error retrieving session state for user {user_info['sub']}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session state: {str(e)}",
        )


# --- Study Management Endpoints ---
@router.post(
    "/viewer/study_opened/{study_id}",
    response_model=StudyOpenedResponse,
    summary="Open a study in viewer application",
    description="Mark a study as opened in the viewer application and notify connected dictation clients",
)
async def open_study_in_viewer(
    study_id: str = None,
    request: StudyOpenedRequest = None,
    user_info: Dict[str, Any] = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    websocket_service: WebSocketService = Depends(get_websocket_service),
) -> StudyOpenedResponse:
    """
    Open a study in the viewer application.

    This endpoint updates the user's session state and notifies any connected
    dictation applications about the study being opened.
    """
    try:
        user_id = user_info["sub"]
        logger.info(f"User {user_id} opening viewer study {study_id}")

        # Update session state
        opened_datetime = datetime.now(timezone.utc).isoformat()
        await session_service.update_session(
            user_id,
            opened_viewer_studyid=study_id,
            opened_viewer_datetime=opened_datetime,
        )

        # Notify dictation app if connected
        await websocket_service.notify_dictation_app(
            user_id,
            "viewer_study_opened",
            {
                "study_id": study_id,
                "datetime": opened_datetime.isoformat(),
                "user_id": user_id,
                "metadata": request.metadata if request else {},
            },
        )

        logger.info(f"Successfully opened viewer study {study_id} for user {user_id}")

        return StudyOpenedResponse(
            message=f"Study {study_id} opened for viewer",
            study_id=study_id,
            datetime=opened_datetime.isoformat(),
            user_id=user_id,
        )

    except Exception as e:
        logger.exception(
            f"Error opening study {study_id} for user {user_info['sub']}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to open study: {str(e)}",
        )


@router.post(
    "/viewer/study_closed/{study_id}",
    response_model=StudyClosedResponse,
    summary="Close a study in viewer application",
    description="Mark a study as closed in the viewer application and notify connected dictation clients",
)
async def close_study_in_viewer(
    study_id: str = None,
    user_info: Dict[str, Any] = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    websocket_service: WebSocketService = Depends(get_websocket_service),
) -> StudyClosedResponse:
    """
    Close a study in the viewer application.

    This endpoint clears the viewer study from the user's session state
    and notifies connected dictation applications.
    """
    try:
        user_id = user_info["sub"]
        logger.info(f"User {user_id} closing viewer study {study_id}")

        # Update session state
        await session_service.update_session(
            user_id,
            opened_viewer_studyid=None,
            opened_viewer_datetime=None,
        )

        # Notify dictation app if connected
        await websocket_service.notify_dictation_app(
            user_id,
            "viewer_study_closed",
            {
                "study_id": study_id,
                "user_id": user_id,
            },
        )

        logger.info(f"Successfully closed viewer study {study_id} for user {user_id}")

        return StudyClosedResponse(
            message=f"Study {study_id} closed for viewer",
            study_id=study_id,
            user_id=user_id,
        )

    except Exception as e:
        logger.exception(
            f"Error closing study {study_id} for user {user_info['sub']}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close study: {str(e)}",
        )


# --- WebSocket Management Endpoints ---
@router.post(
    "/open_websocket/{app_id}",
    response_model=WebSocketResponse,
    summary="Register WebSocket connection intent",
    description="Register intent to open a WebSocket connection for the specified application type",
)
async def register_websocket_connection(
    app_id: AppType = None,
    request: WebSocketConnectionRequest = None,
    user_info: Dict[str, Any] = Depends(get_current_user),
    websocket_service: WebSocketService = Depends(get_websocket_service),
) -> WebSocketResponse:
    """
    Register WebSocket connection intent.

    This endpoint registers the user's intent to establish a WebSocket connection.
    The actual connection is established through the Socket.IO connect event.
    """
    try:
        logger.info(
            f"Registering WebSocket intent for user {user_info['sub']}, app {app_id.value}"
        )

        # Register connection intent
        connection_info = await websocket_service.register_connection_intent(
            user_info["sub"], app_id, request.client_info if request else {}
        )

        return WebSocketResponse(
            message=f"WebSocket endpoint ready for app {app_id.value}. Connect via Socket.IO with auth credentials.",
            app_id=app_id.value,
            user_id=user_info["sub"],
            connection_info=connection_info,
        )

    except Exception as e:
        logger.exception(
            f"Error registering WebSocket for user {user_info['sub']}, app {app_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register WebSocket: {str(e)}",
        )


@router.get(
    "/websocket_status/{app_id}",
    response_model=WebSocketStatusResponse,
    summary="Get WebSocket connection status",
    description="Check if user has an active WebSocket connection for the specified application",
)
async def get_websocket_status(
    app_id: AppType = None,
    user_info: Dict[str, Any] = Depends(get_current_user),
    websocket_service: WebSocketService = Depends(get_websocket_service),
) -> WebSocketStatusResponse:
    """Get WebSocket connection status for user and app."""
    try:
        status_info = await websocket_service.get_connection_status(
            user_info["sub"], app_id
        )

        return WebSocketStatusResponse(
            user_id=user_info["sub"],
            app_id=app_id.value,
            connected=status_info["connected"],
            session_id=status_info.get("session_id"),
            connected_since=status_info.get("connected_since"),
        )

    except Exception as e:
        logger.exception(
            f"Error getting WebSocket status for user {user_info['sub']}, app {app_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get WebSocket status: {str(e)}",
        )


@router.get(
    "/active_connections",
    response_model=ActiveConnectionsResponse,
    summary="Get active WebSocket connections",
    description="Get all active WebSocket connections for the authenticated user",
)
async def get_active_connections(
    user_info: Dict[str, Any] = Depends(get_current_user),
    websocket_service: WebSocketService = Depends(get_websocket_service),
) -> ActiveConnectionsResponse:
    """Get all active WebSocket connections for user."""
    try:
        connections = await websocket_service.get_user_connections(user_info["sub"])

        return ActiveConnectionsResponse(
            user_id=user_info["sub"],
            active_connections=connections,
            total_connections=len(connections),
        )

    except Exception as e:
        logger.exception(
            f"Error getting active connections for user {user_info['sub']}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active connections: {str(e)}",
        )


# --- Session State Endpoints ---
@router.get(
    "/get_session_state",
    response_model=SessionState,
    summary="Get user session state",
    description="Get the current session state for the authenticated user",
)
async def get_session_state(
    user_info: Dict[str, Any] = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
) -> SessionState:
    """Get current session state for the authenticated user."""
    try:
        session_state = await session_service.get_session(user_info["sub"])
        logger.debug(f"Retrieved session state for user {user_info['sub']}")
        return session_state

    except Exception as e:
        logger.exception(
            f"Error retrieving session state for user {user_info['sub']}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session state: {str(e)}",
        )


# --- User Management Endpoints ---
@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout user",
    description="Clear session state and disconnect all WebSocket connections for the user",
)
async def logout_user(
    user_info: Dict[str, Any] = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    websocket_service: WebSocketService = Depends(get_websocket_service),
) -> LogoutResponse:
    """
    Logout user and cleanup all associated resources.

    This endpoint clears the user's session state and disconnects
    all associated WebSocket connections.
    """
    try:
        logger.info(f"Logging out user {user_info['sub']}")

        # Clear session data
        cleared_sessions = await session_service.clear_session(user_info["sub"])

        # Disconnect WebSocket connections and notify clients
        disconnected_count = await websocket_service.disconnect_user_connections(
            user_info["sub"], reason="user_logged_out"
        )

        logger.info(f"User {user_info['sub']} logged out successfully")

        return LogoutResponse(
            message="Session cleared successfully",
            user_id=user_info["sub"],
            cleared_sessions=cleared_sessions,
            disconnected_websockets=disconnected_count,
        )

    except Exception as e:
        logger.exception(f"Error during logout for user {user_info['sub']}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to logout: {str(e)}",
        )


# --- Health Check Endpoint ---
@router.get(
    "/health",
    summary="Session service health check",
    description="Check the health status of session management services",
)
async def health_check(
    session_service: SessionService = Depends(get_session_service),
    websocket_service: WebSocketService = Depends(get_websocket_service),
) -> Dict[str, Any]:
    """Health check endpoint for session services."""
    try:
        session_health = await session_service.health_check()
        websocket_health = await websocket_service.health_check()

        return {
            "status": "healthy",
            "services": {
                "session": session_health,
                "websocket": websocket_health,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service health check failed",
        )
