"""
Admin role management endpoints
"""

import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.api.v1.endpoints.admin_auth import get_current_admin_user
from app.schemas.admin_roles import (
    RoleAssignmentRequest,
    PermissionUpdateRequest,
    RoleResponse,
    PermissionResponse,
    RoleHierarchyResponse
)
from app.services.admin_role_service import (
    AdminRoleService,
    get_admin_role_service
)
from app.models.admin_user import AdminPermission, AdminRole
from app.core.admin_security import AdminSecurity, AdminAuthorizationError

logger = structlog.get_logger(__name__)

router = APIRouter()


def require_permission(permission: AdminPermission):
    """Dependency to require specific permission"""
    async def check_permission(
        current_user = Depends(get_current_admin_user)
    ):
        try:
        role_service = roleService(db)
            AdminSecurity.validate_admin_access(current_user, permission)
            return current_user
        except AdminAuthorizationError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
    return check_permission


@router.get("/roles", response_model=List[RoleResponse])
async def list_available_roles(
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    List available roles based on user permissions
    
    Returns roles that the current user can assign to other users.
    """
    try:
        roles = await role_service.get_available_roles(current_user)
        
        logger.info(
            "Available roles listed",
            user_id=str(current_user.id),
            roles_count=len(roles)
        )
        
        return [RoleResponse(**role) for role in roles]
        
    except Exception as e:
        logger.error("Error listing available roles", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list available roles"
        )


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_available_permissions(
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    List available permissions based on user role
    
    Returns permissions that the current user can assign to other users.
    """
    try:
        permissions = await role_service.get_available_permissions(current_user)
        
        logger.info(
            "Available permissions listed",
            user_id=str(current_user.id),
            permissions_count=len(permissions)
        )
        
        return [PermissionResponse(**permission) for permission in permissions]
        
    except Exception as e:
        logger.error("Error listing available permissions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list available permissions"
        )


@router.post("/users/{user_id}/assign-role")
async def assign_role_to_user(
    user_id: uuid.UUID,
    role_assignment: RoleAssignmentRequest,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Assign role to admin user
    
    Updates the user's role and automatically adjusts their permissions
    to match the new role's default permissions.
    """
    try:
        success = await role_service.assign_role(
            user_id=user_id,
            new_role=role_assignment.role,
            assigning_user=current_user
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "Role assigned to user",
            target_user_id=str(user_id),
            new_role=role_assignment.role.value,
            assigned_by=str(current_user.id)
        )
        
        return {
            "message": f"Role {role_assignment.role.value} assigned successfully",
            "user_id": str(user_id),
            "new_role": role_assignment.role.value
        }
        
    except AdminAuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error assigning role to user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role"
        )


@router.post("/users/{user_id}/update-permissions")
async def update_user_permissions(
    user_id: uuid.UUID,
    permission_update: PermissionUpdateRequest,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Update user's specific permissions
    
    Allows fine-grained control over user permissions beyond their role's
    default permissions.
    """
    try:
        success = await role_service.update_user_permissions(
            user_id=user_id,
            permissions=permission_update.permissions,
            updating_user=current_user
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(
            "User permissions updated",
            target_user_id=str(user_id),
            permissions_count=len(permission_update.permissions),
            updated_by=str(current_user.id)
        )
        
        return {
            "message": "Permissions updated successfully",
            "user_id": str(user_id),
            "permissions": [p.value for p in permission_update.permissions]
        }
        
    except AdminAuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating user permissions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update permissions"
        )


@router.get("/hierarchy", response_model=RoleHierarchyResponse)
async def get_role_hierarchy(
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Get role hierarchy and permission structure
    
    Returns information about role levels, what roles can manage other roles,
    and permission categories.
    """
    try:
        hierarchy = await role_service.get_role_hierarchy()
        
        logger.info(
            "Role hierarchy retrieved",
            user_id=str(current_user.id)
        )
        
        return RoleHierarchyResponse(**hierarchy)
        
    except Exception as e:
        logger.error("Error getting role hierarchy", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve role hierarchy"
        )


@router.get("/validate-assignment")
def validate_role_assignment(
    target_user_id: uuid.UUID,
    role: AdminRole,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Validate if current user can assign specific role to target user
    
    Useful for UI validation before attempting role assignment.
    """
    try:
        # This would check permissions without actually making changes
        can_assign = role_service._can_assign_role(current_user, role)
        
        # Additional checks could be added here for target user validation
        
        return {
            "can_assign": can_assign,
            "target_user_id": str(target_user_id),
            "role": role.value,
            "reason": "Sufficient permissions" if can_assign else "Insufficient permissions"
        }
        
    except Exception as e:
        logger.error("Error validating role assignment", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate role assignment"
        )


@router.get("/permission-matrix")
def get_permission_matrix(
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Get permission matrix showing which roles have which permissions
    
    Returns a comprehensive view of the permission system.
    """
    try:
        matrix = {}
        
        # Get all roles and their permissions
        for role in AdminRole:
            role_permissions = role_service._get_role_permissions(role)
            matrix[role.value] = {
                "permissions": role_permissions,
                "permission_count": len(role_permissions),
                "description": AdminSecurity.get_role_description(role)
            }
        
        # Get permission categories
        permission_categories = {}
        for permission in AdminPermission:
            category = role_service._get_permission_category(permission)
            if category not in permission_categories:
                permission_categories[category] = []
            permission_categories[category].append({
                "permission": permission.value,
                "description": AdminSecurity.get_permission_description(permission)
            })
        
        logger.info(
            "Permission matrix retrieved",
            user_id=str(current_user.id)
        )
        
        return {
            "role_permissions": matrix,
            "permission_categories": permission_categories,
            "total_roles": len(AdminRole),
            "total_permissions": len(AdminPermission)
        }
        
    except Exception as e:
        logger.error("Error getting permission matrix", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve permission matrix"
        )
