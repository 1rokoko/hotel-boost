"""
Admin user management endpoints
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.api.v1.endpoints.admin_auth import get_current_admin_user
from app.schemas.admin_auth import (
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserResponse,
    AdminUserListResponse,
    AdminUserSearchParams
)
from app.services.admin_user_service import (
    AdminUserService,
    get_admin_user_service
)
from app.models.admin_user import AdminPermission
from app.core.admin_security import AdminSecurity, AdminAuthorizationError

logger = structlog.get_logger(__name__)

router = APIRouter()


def require_permission(permission: AdminPermission):
    """Dependency to require specific permission"""
    async def check_permission(
        current_user = Depends(get_current_admin_user)
    ):
        try:
            user_service = userService(db)
            AdminSecurity.validate_admin_access(current_user, permission)
            return current_user
        except AdminAuthorizationError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
    return check_permission


@router.get("/", response_model=AdminUserListResponse)
async def list_admin_users(
    search_params: AdminUserSearchParams = Depends(),
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    List admin users with filtering and pagination
    """
    try:
        users, total = await user_service.list_users(
            search_params=search_params,
            requesting_user=current_user
        )
        
        total_pages = (total + search_params.per_page - 1) // search_params.per_page
        
        return AdminUserListResponse(
            users=[AdminUserResponse.from_orm(user) for user in users],
            total=total,
            page=search_params.page,
            per_page=search_params.per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error("Error listing admin users", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.post("/", response_model=AdminUserResponse)
async def create_admin_user(
    user_data: AdminUserCreate,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Create new admin user
    """
    try:
        new_user = await user_service.create_user(
            user_data=user_data,
            creating_user=current_user
        )
        
        logger.info(
            "Admin user created",
            created_user_id=str(new_user.id),
            created_by=str(current_user.id)
        )
        
        return AdminUserResponse.from_orm(new_user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Error creating admin user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.get("/{user_id}", response_model=AdminUserResponse)
async def get_admin_user(
    user_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Get admin user by ID
    """
    try:
        user = await user_service.get_user_by_id(
            user_id=user_id,
            requesting_user=current_user
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return AdminUserResponse.from_orm(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting admin user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: uuid.UUID,
    user_data: AdminUserUpdate,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Update admin user
    """
    try:
        updated_user = await user_service.update_user(
            user_id=user_id,
            user_data=user_data,
            updating_user=current_user
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "Admin user updated",
            updated_user_id=str(updated_user.id),
            updated_by=str(current_user.id)
        )
        
        return AdminUserResponse.from_orm(updated_user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating admin user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/{user_id}")
async def delete_admin_user(
    user_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Delete admin user
    """
    try:
        success = await user_service.delete_user(
            user_id=user_id,
            deleting_user=current_user
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "Admin user deleted",
            deleted_user_id=str(user_id),
            deleted_by=str(current_user.id)
        )
        
        return {"message": "User deleted successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting admin user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


@router.post("/{user_id}/activate")
async def activate_admin_user(
    user_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Activate admin user account
    """
    try:
        success = await user_service.activate_user(
            user_id=user_id,
            activating_user=current_user
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "Admin user activated",
            activated_user_id=str(user_id),
            activated_by=str(current_user.id)
        )
        
        return {"message": "User activated successfully"}
        
    except Exception as e:
        logger.error("Error activating admin user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user"
        )


@router.post("/{user_id}/deactivate")
async def deactivate_admin_user(
    user_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Deactivate admin user account
    """
    try:
        success = await user_service.deactivate_user(
            user_id=user_id,
            deactivating_user=current_user
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "Admin user deactivated",
            deactivated_user_id=str(user_id),
            deactivated_by=str(current_user.id)
        )
        
        return {"message": "User deactivated successfully"}
        
    except Exception as e:
        logger.error("Error deactivating admin user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user"
        )


@router.post("/{user_id}/unlock")
async def unlock_admin_user(
    user_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Unlock admin user account
    """
    try:
        success = await user_service.unlock_user(
            user_id=user_id,
            unlocking_user=current_user
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "Admin user unlocked",
            unlocked_user_id=str(user_id),
            unlocked_by=str(current_user.id)
        )
        
        return {"message": "User unlocked successfully"}
        
    except Exception as e:
        logger.error("Error unlocking admin user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unlock user"
        )
