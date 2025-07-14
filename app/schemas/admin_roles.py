"""
Admin role management schemas
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field

from app.models.admin_user import AdminRole, AdminPermission


class RoleAssignmentRequest(BaseModel):
    """Schema for role assignment request"""
    
    role: AdminRole = Field(..., description="Role to assign to the user")


class PermissionUpdateRequest(BaseModel):
    """Schema for permission update request"""
    
    permissions: List[AdminPermission] = Field(..., description="List of permissions to assign")


class RoleResponse(BaseModel):
    """Schema for role information response"""
    
    role: str = Field(..., description="Role identifier")
    name: str = Field(..., description="Human-readable role name")
    description: str = Field(..., description="Role description")
    permissions: List[str] = Field(..., description="Default permissions for this role")
    can_assign: bool = Field(..., description="Whether current user can assign this role")


class PermissionResponse(BaseModel):
    """Schema for permission information response"""
    
    permission: str = Field(..., description="Permission identifier")
    name: str = Field(..., description="Human-readable permission name")
    description: str = Field(..., description="Permission description")
    category: str = Field(..., description="Permission category")


class RoleHierarchyItem(BaseModel):
    """Schema for role hierarchy item"""
    
    role: str = Field(..., description="Role identifier")
    level: int = Field(..., description="Role level in hierarchy")
    can_manage: List[str] = Field(..., description="Roles this role can manage")
    description: str = Field(..., description="Role description")


class RoleHierarchyResponse(BaseModel):
    """Schema for role hierarchy response"""
    
    roles: List[RoleHierarchyItem] = Field(..., description="Role hierarchy information")
    permission_categories: Dict[str, List[str]] = Field(..., description="Permission categories")


class RoleValidationResponse(BaseModel):
    """Schema for role assignment validation response"""
    
    can_assign: bool = Field(..., description="Whether assignment is allowed")
    target_user_id: str = Field(..., description="Target user ID")
    role: str = Field(..., description="Role being validated")
    reason: str = Field(..., description="Reason for validation result")


class PermissionMatrixRole(BaseModel):
    """Schema for permission matrix role entry"""
    
    permissions: List[str] = Field(..., description="Permissions for this role")
    permission_count: int = Field(..., description="Number of permissions")
    description: str = Field(..., description="Role description")


class PermissionCategoryItem(BaseModel):
    """Schema for permission category item"""
    
    permission: str = Field(..., description="Permission identifier")
    description: str = Field(..., description="Permission description")


class PermissionMatrixResponse(BaseModel):
    """Schema for permission matrix response"""
    
    role_permissions: Dict[str, PermissionMatrixRole] = Field(..., description="Role to permissions mapping")
    permission_categories: Dict[str, List[PermissionCategoryItem]] = Field(..., description="Permission categories")
    total_roles: int = Field(..., description="Total number of roles")
    total_permissions: int = Field(..., description="Total number of permissions")
