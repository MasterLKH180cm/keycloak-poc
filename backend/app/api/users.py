import logging
from typing import List, Optional

from app.core.security import get_current_user, require_admin
from app.db.database import get_db
from app.models.user import User, UserAuditLog
from app.schemas.user import AuditLogResponse, UserCreate, UserResponse, UserUpdate
from app.services.keycloak_service import keycloak_service
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create new user (Admin only)"""
    try:
        # Check if username or email already exists
        existing_user = await db.execute(
            select(User).where(
                (User.username == user_data.username) | (User.email == user_data.email)
            )
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already exists",
            )

        # Create user in Keycloak first
        keycloak_id = await keycloak_service.create_user(user_data)

        # Create user in local database
        db_user = User(
            keycloak_id=keycloak_id,
            username=user_data.username,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            department=user_data.department,
            role=user_data.role,
            license_number=user_data.license_number,
            npi_number=user_data.npi_number,
            created_by=current_user["username"],
        )

        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        # Create audit log
        audit_log = UserAuditLog(
            user_id=db_user.id,
            action="USER_CREATED",
            details=f"User created by {current_user['username']}",
            success=True,
        )
        db.add(audit_log)
        await db.commit()

        return UserResponse.from_orm(db_user)

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
    db: AsyncSession = Depends(get_db),
):
    """List all users with filtering and pagination (Admin only)"""
    query = select(User)

    # Apply filters
    if department:
        query = query.where(User.department == department)
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(User.created_at.desc())

    result = await db.execute(query)
    users = result.scalars().all()

    return [UserResponse.from_orm(user) for user in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get user by ID (Admin or own profile)"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if user can access this profile
    if user.keycloak_id != current_user[
        "keycloak_id"
    ] and "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user",
        )

    return UserResponse.from_orm(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update user (Admin or own profile)"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check permissions
    if user.keycloak_id != current_user[
        "keycloak_id"
    ] and "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    try:
        # Update local database
        update_data = user_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_by = current_user["username"]

        # Update Keycloak user
        keycloak_update_data = {
            "firstName": user.first_name,
            "lastName": user.last_name,
            "attributes": {
                "department": [user.department] if user.department else [],
                "license_number": [user.license_number] if user.license_number else [],
                "npi_number": [user.npi_number] if user.npi_number else [],
            },
        }

        await keycloak_service.update_user(user.keycloak_id, keycloak_update_data)

        await db.commit()
        await db.refresh(user)

        # Create audit log
        audit_log = UserAuditLog(
            user_id=user.id,
            action="USER_UPDATED",
            details=f"User updated by {current_user['username']}",
            success=True,
        )
        db.add(audit_log)
        await db.commit()

        return UserResponse.from_orm(user)

    except Exception as e:
        await db.rollback()
        logger.error(f"User update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        )


@router.delete("/{user_id}", dependencies=[Depends(require_admin)])
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Deactivate user (Admin only) - We don't delete for audit purposes"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    try:
        # Deactivate in local database
        user.is_active = False
        user.updated_by = current_user["username"]

        # Disable in Keycloak
        await keycloak_service.update_user(user.keycloak_id, {"enabled": False})

        await db.commit()

        # Create audit log
        audit_log = UserAuditLog(
            user_id=user.id,
            action="USER_DEACTIVATED",
            details=f"User deactivated by {current_user['username']}",
            success=True,
        )
        db.add(audit_log)
        await db.commit()

        return {"message": "User deactivated successfully"}

    except Exception as e:
        await db.rollback()
        logger.error(f"User deactivation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user",
        )


@router.get("/{user_id}/audit-logs", response_model=List[AuditLogResponse])
async def get_user_audit_logs(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get user audit logs (Admin or own logs)"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check permissions
    if user.keycloak_id != current_user[
        "keycloak_id"
    ] and "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access audit logs",
        )

    query = (
        select(UserAuditLog)
        .where(UserAuditLog.user_id == user_id)
        .order_by(UserAuditLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    audit_logs = result.scalars().all()

    return [AuditLogResponse.from_orm(log) for log in audit_logs]
