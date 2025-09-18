import logging
from datetime import datetime
from typing import List, Optional

from app.core.security import get_current_user, require_admin
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.user_management import (
    PasswordResetRequest,
    PasswordResetResponse,
    UserActivationResponse,
    UserDeletionResponse,
)
from app.services.keycloak_service import keycloak_service
from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def create_user(
    user_data: UserCreate,
    role: str = Query("user", description="Role to assign to the user (user or admin)"),
    current_user: dict = Depends(get_current_user),
):
    """Create new user (Admin only)"""
    try:
        # Validate role parameter
        if role not in ["user", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be either 'user' or 'admin'",
            )

        # Check if username or email already exists in Keycloak
        existing_user = await keycloak_service.get_user_by_username(user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

        existing_email = await keycloak_service.get_user_by_email(user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

        # Create user in Keycloak
        print(current_user)
        keycloak_user_data = {
            "username": user_data.username,
            "email": user_data.email,
            "firstName": user_data.first_name,
            "lastName": user_data.last_name,
            "enabled": True,
            "emailVerified": False,
            "attributes": {
                "created_by": [current_user["username"]],
                "role": [role],
            },
        }

        if user_data.password:
            keycloak_user_data["credentials"] = [
                {
                    "type": "password",
                    "value": user_data.password,
                    "temporary": user_data.temporary_password
                    if hasattr(user_data, "temporary_password")
                    else True,
                }
            ]

        keycloak_id = await keycloak_service.create_user(keycloak_user_data)

        # Get created user info
        created_user = await keycloak_service.get_user_info(keycloak_id)

        user_response = UserResponse(
            id=created_user["id"],
            keycloak_id=created_user["id"],
            username=created_user["username"],
            email=created_user["email"],
            first_name=created_user.get("firstName", ""),
            last_name=created_user.get("lastName", ""),
            email_verified=created_user.get("emailVerified", False),
            enable=created_user.get("enabled", True),
            created_at=None,
            updated_at=None,
            last_login=None,
        )

        return user_response

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"User creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )


@router.get(
    "/", response_model=List[UserResponse], dependencies=[Depends(require_admin)]
)
async def list_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    role: Optional[str] = Query(None, description="Filter by role"),
    enable: Optional[bool] = Query(None, description="Filter by active status"),
):
    """List all users with filtering and pagination (Admin only)"""
    try:
        # Get users from Keycloak
        users = await keycloak_service.list_users(
            first=skip, max=limit, search=None, enabled=enable
        )
        print(users)
        user_responses = []
        for user in users:
            # Apply filters
            user_role = user.get("attributes", {}).get("role", ["user"])[0]

            if role and user_role != role:
                continue

            user_response = UserResponse(
                id=user["id"],
                keycloak_id=user["id"],
                username=user["username"],
                email=user.get("email", ""),
                first_name=user.get("firstName", ""),
                last_name=user.get("lastName", ""),
                email_verified=user.get("emailVerified", False),
                enable=user.get("enabled", True),
                created_at=None,
                updated_at=None,
                last_login=None,
            )
            user_responses.append(user_response)

        return user_responses

    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users",
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get user by ID (Admin or own profile)"""
    try:
        # Check if user can access this profile
        if user_id != current_user["keycloak_id"] and "admin" not in current_user.get(
            "roles", []
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this user",
            )

        # Get user from Keycloak
        user = await keycloak_service.get_user_info(user_id)

        user_response = UserResponse(
            id=user["id"],
            keycloak_id=user["id"],
            username=user["username"],
            email=user["email"],
            first_name=user.get("firstName", ""),
            last_name=user.get("lastName", ""),
            email_verified=user.get("emailVerified", False),
            enable=user.get("enabled", True),
            created_at=None,
            updated_at=None,
            last_login=None,
        )

        return user_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update user (Admin or own profile)"""
    try:
        # Check permissions
        if user_id != current_user["keycloak_id"] and "admin" not in current_user.get(
            "roles", []
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this user",
            )

        # Prepare update data for Keycloak
        update_data = user_data.dict(exclude_unset=True)
        keycloak_update_data = {}

        if "first_name" in update_data:
            keycloak_update_data["firstName"] = update_data["first_name"]
        if "last_name" in update_data:
            keycloak_update_data["lastName"] = update_data["last_name"]
        if "email" in update_data:
            keycloak_update_data["email"] = update_data["email"]

        # Handle attributes
        attributes = {}

        # Get current user info to preserve existing data
        current_user_info = await keycloak_service.get_user_info(user_id)
        print("Current user info before update:", current_user_info)
        print("Current user email before update:", current_user_info.get("email"))

        # Preserve email if not being updated
        if "email" not in keycloak_update_data and current_user_info.get("email"):
            keycloak_update_data["email"] = current_user_info["email"]

        if attributes:
            current_attributes = current_user_info.get("attributes", {})
            current_attributes.update(attributes)
            current_attributes["updated_by"] = [current_user["username"]]
            keycloak_update_data["attributes"] = current_attributes

        # Debug: Print what we're sending to Keycloak
        print("Updating user with data:", keycloak_update_data)

        # Update user in Keycloak
        await keycloak_service.update_user(user_id, keycloak_update_data)

        # Get updated user info
        updated_user = await keycloak_service.get_user_info(user_id)
        print("Full updated_user response:", updated_user)
        print("Email field specifically:", repr(updated_user.get("email")))
        print(
            "All keys in updated_user:",
            list(updated_user.keys()) if updated_user else "None",
        )
        user_response = UserResponse(
            id=updated_user.get("id", ""),
            keycloak_id=updated_user.get("id", ""),
            username=updated_user.get("username", ""),
            email=updated_user.get("email", ""),
            first_name=updated_user.get("firstName", ""),
            last_name=updated_user.get("lastName", ""),
            email_verified=updated_user.get("emailVerified", True),
            enable=updated_user.get("enabled", True),
            created_at=None,
            updated_at=None,
            last_login=None,
        )

        return user_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to update user",
        )


@router.delete(
    "/{user_id}",
    response_model=UserDeletionResponse,
    dependencies=[Depends(require_admin)],
)
async def delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Permanently delete user (Admin only) - Use with caution"""
    try:
        # Delete user from Keycloak
        await keycloak_service.delete_user(user_id)

        logger.info(f"User {user_id} deleted by {current_user['username']}")
        return UserDeletionResponse()

    except Exception as e:
        logger.error(f"User deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user",
        )


@router.post(
    "/{user_id}/deactivate",
    response_model=UserActivationResponse,
    dependencies=[Depends(require_admin)],
)
async def deactivate_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Deactivate user (Admin only) - Disable instead of delete for audit"""
    try:
        # Disable user in Keycloak
        await keycloak_service.update_user(
            user_id,
            {
                "enabled": False,
                "attributes": {
                    "deactivated_by": [current_user["username"]],
                    "deactivated_at": [datetime.utcnow().isoformat()],
                },
            },
        )

        return UserActivationResponse(message="User deactivated successfully")

    except Exception as e:
        logger.error(f"User deactivation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user",
        )


@router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetResponse,
    dependencies=[Depends(require_admin)],
)
async def reset_user_password(
    user_id: str,
    password_data: PasswordResetRequest,
    current_user: dict = Depends(get_current_user),
):
    """Reset user password (Admin only)"""
    try:
        await keycloak_service.reset_user_password(
            user_id, password_data.password, password_data.temporary
        )
        return PasswordResetResponse()

    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password",
        )


@router.post(
    "/{user_id}/activate",
    response_model=UserActivationResponse,
    dependencies=[Depends(require_admin)],
)
async def activate_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Activate user (Admin only)"""
    try:
        await keycloak_service.update_user(
            user_id,
            {
                "enabled": True,
                "attributes": {
                    "activated_by": [current_user["username"]],
                    "activated_at": [datetime.utcnow().isoformat()],
                },
            },
        )

        return UserActivationResponse(message="User activated successfully")

    except Exception as e:
        logger.error(f"User activation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user",
        )
