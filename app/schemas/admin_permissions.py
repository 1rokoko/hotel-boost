"""
Admin permission management schemas
"""

import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.models.admin_user import AdminPermission


class PermissionValidationRequest(BaseModel):
    """Schema for permission validation request"""
    
    target_user_id: uuid.UUID = Field(..., description="User ID to assign permissions to")
    permissions: List[AdminPermission] = Field(..., description="Permissions to validate")


class PermissionValidationResponse(BaseModel):
    """Schema for permission validation response"""
    
    valid: bool = Field(..., description="Whether the permission assignment is valid")
    errors: List[str] = Field(..., description="Validation errors")
    warnings: List[str] = Field(..., description="Validation warnings")
    allowed_permissions: List[str] = Field(..., description="Permissions that can be assigned")
    denied_permissions: List[str] = Field(..., description="Permissions that cannot be assigned")
    missing_dependencies: List[Dict[str, str]] = Field(..., description="Missing permission dependencies")
    conflicts: List[Dict[str, Any]] = Field(..., description="Permission conflicts")


class PermissionConflictResponse(BaseModel):
    """Schema for permission conflict response"""
    
    type: str = Field(..., description="Type of conflict")
    permissions: List[str] = Field(..., description="Conflicting permissions")
    message: str = Field(..., description="Conflict description")


class PermissionDependencyResponse(BaseModel):
    """Schema for permission dependency response"""
    
    permission: str = Field(..., description="Permission identifier")
    description: str = Field(..., description="Permission description")
    scope: str = Field(..., description="Permission scope")
    dependencies: List[Dict[str, str]] = Field(..., description="Required dependencies")
    has_dependencies: bool = Field(..., description="Whether permission has dependencies")


class RoleInfo(BaseModel):
    """Schema for role information"""
    
    role: str = Field(..., description="Role identifier")
    description: str = Field(..., description="Role description")
    permissions: List[str] = Field(..., description="Role permissions")
    permission_count: int = Field(..., description="Number of permissions")


class PermissionSuggestionResponse(BaseModel):
    """Schema for permission suggestion response"""
    
    suggested_role: Optional[RoleInfo] = Field(None, description="Suggested role information")
    input_permissions: List[str] = Field(..., description="Input permissions")
    exact_match: bool = Field(..., description="Whether suggestion is exact match")
    recommendation: str = Field(..., description="Recommendation text")


class EffectivePermissionInfo(BaseModel):
    """Schema for effective permission information"""
    
    permission: str = Field(..., description="Permission identifier")
    description: str = Field(..., description="Permission description")
    source: str = Field(..., description="Permission source (role or explicit)")


class EffectivePermissionsResponse(BaseModel):
    """Schema for effective permissions response"""
    
    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="User role")
    total_permissions: int = Field(..., description="Total number of permissions")
    permissions_by_category: Dict[str, List[EffectivePermissionInfo]] = Field(..., description="Permissions by category")
    all_permissions: List[str] = Field(..., description="All permission identifiers")


class PermissionCheckResponse(BaseModel):
    """Schema for permission check response"""
    
    user_id: str = Field(..., description="User ID")
    permission: str = Field(..., description="Permission checked")
    has_permission: bool = Field(..., description="Whether user has permission")
    context: Optional[Dict[str, Any]] = Field(None, description="Permission context")
    user_role: str = Field(..., description="User role")
    user_hotel_id: Optional[str] = Field(None, description="User hotel ID")


class ScopePermissionInfo(BaseModel):
    """Schema for scope permission information"""
    
    permission: str = Field(..., description="Permission identifier")
    description: str = Field(..., description="Permission description")


class PermissionScopeInfo(BaseModel):
    """Schema for permission scope information"""
    
    description: str = Field(..., description="Scope description")
    permissions: List[ScopePermissionInfo] = Field(..., description="Permissions in this scope")
    restricted_to: List[str] = Field(..., description="Roles that can assign these permissions")


class PermissionScopeResponse(BaseModel):
    """Schema for permission scope response"""
    
    global_: PermissionScopeInfo = Field(..., alias="global", description="Global scope permissions")
    hotel: PermissionScopeInfo = Field(..., description="Hotel scope permissions")
    user: PermissionScopeInfo = Field(..., description="User scope permissions")
