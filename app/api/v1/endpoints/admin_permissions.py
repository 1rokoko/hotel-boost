"""
Admin permission management endpoints
"""

import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.api.v1.endpoints.admin_auth import get_current_admin_user
from app.schemas.admin_permissions import (
    PermissionValidationRequest,
    PermissionValidationResponse,
    PermissionConflictResponse,
    PermissionDependencyResponse,
    PermissionSuggestionResponse
)
from app.models.admin_user import AdminPermission, AdminRole
from app.utils.permission_manager import PermissionManager
from app.core.admin_security import AdminSecurity, AdminAuthorizationError

logger = structlog.get_logger(__name__)

router = APIRouter()


def require_permission(permission: AdminPermission):
    """Dependency to require specific permission"""
    def check_permission(
        current_user = Depends(get_current_admin_user)
    ):
        try:
            AdminSecurity.validate_admin_access(current_user, permission)
            return current_user
        except AdminAuthorizationError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
    return check_permission


@router.post("/validate", response_model=PermissionValidationResponse)
def validate_permission_assignment(
    validation_request: PermissionValidationRequest,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Validate permission assignment before applying
    
    Checks if the current user can assign the specified permissions
    to the target user, including scope and dependency validation.
    """
    try:
        # Get target user (this would need to be implemented)
        # For now, we'll create a mock target user
        from app.models.admin_user import AdminUser
        target_user = AdminUser(
            id=validation_request.target_user_id,
            role=AdminRole.VIEWER,  # This would be fetched from DB
            hotel_id=current_user.hotel_id,  # This would be fetched from DB
            permissions=[]
        )
        
        # Validate permission assignment
        validation_result = PermissionManager.validate_permission_assignment(
            assigning_user=current_user,
            target_user=target_user,
            permissions=validation_request.permissions
        )
        
        # Check dependencies
        dependency_result = PermissionManager.validate_permission_dependencies(
            validation_request.permissions
        )
        
        # Check conflicts
        conflicts = PermissionManager.get_permission_conflicts(
            target_user,
            validation_request.permissions
        )
        
        logger.info(
            "Permission assignment validated",
            user_id=str(current_user.id),
            target_user_id=str(validation_request.target_user_id),
            permissions_count=len(validation_request.permissions),
            valid=validation_result["valid"]
        )
        
        return PermissionValidationResponse(
            valid=validation_result["valid"] and dependency_result["valid"],
            errors=validation_result["errors"] + dependency_result.get("suggestions", []),
            warnings=[conflict["message"] for conflict in conflicts],
            allowed_permissions=validation_result["allowed_permissions"],
            denied_permissions=validation_result["denied_permissions"],
            missing_dependencies=dependency_result.get("missing_dependencies", []),
            conflicts=conflicts
        )
        
    except Exception as e:
        logger.error("Error validating permission assignment", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate permission assignment"
        )


@router.get("/user/{user_id}/effective")
def get_user_effective_permissions(
    user_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Get effective permissions for a user
    
    Returns all permissions the user has, including those from their role
    and explicit permissions.
    """
    try:
        # Get target user (this would need to be implemented)
        # For now, we'll use current user as example
        target_user = current_user
        
        # Get effective permissions
        effective_permissions = PermissionManager.get_effective_permissions(target_user)
        
        # Categorize permissions
        categorized_permissions = {}
        for permission_value in effective_permissions:
            try:
                permission = AdminPermission(permission_value)
                scope = PermissionManager.get_permission_scope(permission)
                category = scope.value
                
                if category not in categorized_permissions:
                    categorized_permissions[category] = []
                
                categorized_permissions[category].append({
                    "permission": permission_value,
                    "description": AdminSecurity.get_permission_description(permission),
                    "source": "role" if permission_value in target_user.get_role_permissions() else "explicit"
                })
            except ValueError:
                # Skip invalid permissions
                continue
        
        logger.info(
            "Effective permissions retrieved",
            user_id=str(current_user.id),
            target_user_id=str(user_id),
            permissions_count=len(effective_permissions)
        )
        
        return {
            "user_id": str(user_id),
            "role": target_user.role.value,
            "total_permissions": len(effective_permissions),
            "permissions_by_category": categorized_permissions,
            "all_permissions": list(effective_permissions)
        }
        
    except Exception as e:
        logger.error("Error getting effective permissions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get effective permissions"
        )


@router.post("/suggest-role", response_model=PermissionSuggestionResponse)
def suggest_role_for_permissions(
    permissions: List[AdminPermission],
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Suggest appropriate role based on permission set
    
    Analyzes the provided permissions and suggests the most appropriate
    role that would grant those permissions.
    """
    try:
        suggested_role = PermissionManager.suggest_role_for_permissions(permissions)
        
        # Get role information if suggestion found
        role_info = None
        if suggested_role:
            role_permissions = []
            if suggested_role == AdminRole.SUPER_ADMIN:
                role_permissions = [p.value for p in AdminPermission]
            else:
                # Get role permissions from user model
                temp_user = AdminUser(role=suggested_role, permissions=[])
                role_permissions = temp_user.get_role_permissions()
            
            role_info = {
                "role": suggested_role.value,
                "description": AdminSecurity.get_role_description(suggested_role),
                "permissions": role_permissions,
                "permission_count": len(role_permissions)
            }
        
        logger.info(
            "Role suggestion generated",
            user_id=str(current_user.id),
            permissions_count=len(permissions),
            suggested_role=suggested_role.value if suggested_role else None
        )
        
        return PermissionSuggestionResponse(
            suggested_role=role_info,
            input_permissions=[p.value for p in permissions],
            exact_match=suggested_role is not None,
            recommendation="Use suggested role" if suggested_role else "Custom permission set required"
        )
        
    except Exception as e:
        logger.error("Error suggesting role for permissions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to suggest role"
        )


@router.get("/dependencies/{permission}")
def get_permission_dependencies(
    permission: AdminPermission,
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Get dependencies for a specific permission
    
    Returns permissions that are required as dependencies for the
    specified permission to function properly.
    """
    try:
        dependencies = PermissionManager.get_permission_dependencies(permission)
        
        dependency_info = []
        for dep in dependencies:
            dependency_info.append({
                "permission": dep.value,
                "description": AdminSecurity.get_permission_description(dep),
                "scope": PermissionManager.get_permission_scope(dep).value
            })
        
        logger.info(
            "Permission dependencies retrieved",
            user_id=str(current_user.id),
            permission=permission.value,
            dependencies_count=len(dependencies)
        )
        
        return {
            "permission": permission.value,
            "description": AdminSecurity.get_permission_description(permission),
            "scope": PermissionManager.get_permission_scope(permission).value,
            "dependencies": dependency_info,
            "has_dependencies": len(dependencies) > 0
        }
        
    except Exception as e:
        logger.error("Error getting permission dependencies", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get permission dependencies"
        )


@router.get("/check")
def check_user_permission(
    permission: AdminPermission,
    hotel_id: uuid.UUID = Query(None, description="Hotel context for permission check"),
    current_user = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user has specific permission
    
    Useful for UI components to determine what actions to show/hide.
    """
    try:
        context = {"hotel_id": hotel_id} if hotel_id else None
        
        has_permission = PermissionManager.check_permission(
            user=current_user,
            required_permission=permission,
            context=context
        )
        
        return {
            "user_id": str(current_user.id),
            "permission": permission.value,
            "has_permission": has_permission,
            "context": context,
            "user_role": current_user.role.value,
            "user_hotel_id": str(current_user.hotel_id) if current_user.hotel_id else None
        }
        
    except Exception as e:
        logger.error("Error checking user permission", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check permission"
        )


@router.get("/scope-info")
def get_permission_scope_info(
    current_user = Depends(require_permission(AdminPermission.MANAGE_HOTEL_USERS)),
    db: Session = Depends(get_db)
):
    """
    Get information about permission scopes
    
    Returns details about different permission scopes and their meanings.
    """
    try:
        scope_info = {
            "global": {
                "description": "System-wide permissions that affect all hotels",
                "permissions": [],
                "restricted_to": ["super_admin"]
            },
            "hotel": {
                "description": "Hotel-specific permissions that only affect the user's hotel",
                "permissions": [],
                "restricted_to": ["super_admin", "hotel_admin"]
            },
            "user": {
                "description": "User-specific permissions for individual operations",
                "permissions": [],
                "restricted_to": ["super_admin", "hotel_admin", "hotel_staff"]
            }
        }
        
        # Categorize all permissions by scope
        for permission in AdminPermission:
            scope = PermissionManager.get_permission_scope(permission)
            scope_info[scope.value]["permissions"].append({
                "permission": permission.value,
                "description": AdminSecurity.get_permission_description(permission)
            })
        
        logger.info(
            "Permission scope info retrieved",
            user_id=str(current_user.id)
        )
        
        return scope_info
        
    except Exception as e:
        logger.error("Error getting permission scope info", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get permission scope info"
        )
