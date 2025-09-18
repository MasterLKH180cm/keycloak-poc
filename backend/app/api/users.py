import logging
from datetime import datetime
from typing import List, Optional

from app.core.security import get_current_user, require_admin
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.keycloak_service import keycloak_service
from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create new user (Admin only)"""
    try:
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
                "role": [user_data.role] if user_data.role else ["user"],
                "department": [user_data.department] if user_data.department else [],
                "license_number": [user_data.license_number]
                if user_data.license_number
                else [],
                "npi_number": [user_data.npi_number] if user_data.npi_number else [],
                "created_by": [current_user["username"]],
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
            is_active=created_user.get("enabled", True),
            role=created_user.get("attributes", {}).get("role", ["user"])[0],
            department=created_user.get("attributes", {}).get("department", [None])[0],
            license_number=created_user.get("attributes", {}).get(
                "license_number", [None]
            )[0],
            npi_number=created_user.get("attributes", {}).get("npi_number", [None])[0],
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
    department: Optional[str] = Query(None, description="Filter by department"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """List all users with filtering and pagination (Admin only)"""
    try:
        # Get users from Keycloak
        users = await keycloak_service.list_users(
            first=skip, max=limit, search=None, enabled=is_active
        )
        print(users)
        user_responses = []
        for user in users:
            # Apply filters
            user_department = user.get("attributes", {}).get("department", [None])[0]
            user_role = user.get("attributes", {}).get("role", ["user"])[0]

            if department and user_department != department:
                continue
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
                is_active=user.get("enabled", True),
                role=user_role,
                department=user_department,
                license_number=user.get("attributes", {}).get("license_number", [None])[
                    0
                ],
                npi_number=user.get("attributes", {}).get("npi_number", [None])[0],
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
            is_active=user.get("enabled", True),
            role=user.get("attributes", {}).get("role", ["user"])[0]
            if user.get("attributes", {}).get("role")
            else "user",
            department=user.get("attributes", {}).get("department", [None])[0],
            license_number=user.get("attributes", {}).get("license_number", [None])[0],
            npi_number=user.get("attributes", {}).get("npi_number", [None])[0],
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
        if "department" in update_data:
            attributes["department"] = (
                [update_data["department"]] if update_data["department"] else []
            )
        if "role" in update_data:
            attributes["role"] = (
                [update_data["role"]] if update_data["role"] else ["user"]
            )
        if "license_number" in update_data:
            attributes["license_number"] = (
                [update_data["license_number"]] if update_data["license_number"] else []
            )
        if "npi_number" in update_data:
            attributes["npi_number"] = (
                [update_data["npi_number"]] if update_data["npi_number"] else []
            )

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
            is_active=updated_user.get("enabled", True),
            role=updated_user.get("attributes", {}).get("role", ["user"])[0]
            if updated_user.get("attributes", {}).get("role")
            else "user",
            department=updated_user.get("attributes", {}).get("department", [None])[0],
            license_number=updated_user.get("attributes", {}).get(
                "license_number", [None]
            )[0],
            npi_number=updated_user.get("attributes", {}).get("npi_number", [None])[0],
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


@router.delete("/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Permanently delete user (Admin only) - Use with caution"""
    try:
        # Delete user from Keycloak
        await keycloak_service.delete_user(user_id)

        logger.info(f"User {user_id} deleted by {current_user['username']}")
        return {"message": "User deleted successfully"}

    except Exception as e:
        logger.error(f"User deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user",
        )


@router.post("/{user_id}/deactivate", dependencies=[Depends(require_admin)])
async def deactivate_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Deactivate user (Admin only) - We disable instead of delete for audit purposes"""
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

        return {"message": "User deactivated successfully"}

    except Exception as e:
        logger.error(f"User deactivation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user",
        )


@router.post("/{user_id}/reset-password", dependencies=[Depends(require_admin)])
async def reset_user_password(
    user_id: str,
    password: str,
    temporary: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """Reset user password (Admin only)"""
    try:
        await keycloak_service.reset_user_password(user_id, password, temporary)
        return {"message": "Password reset successfully"}

    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password",
        )


@router.post("/{user_id}/activate", dependencies=[Depends(require_admin)])
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

        return {"message": "User activated successfully"}

    except Exception as e:
        logger.error(f"User activation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user",
        )
