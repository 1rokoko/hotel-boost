"""
Permission management utilities
"""

import uuid
from typing import List, Dict, Any, Optional, Set
from enum import Enum
import structlog

from app.models.admin_user import AdminUser, AdminRole, AdminPermission
from app.core.admin_security import AdminSecurity, AdminAuthorizationError

logger = structlog.get_logger(__name__)


class PermissionScope(str, Enum):
    """Permission scope levels"""
    GLOBAL = "global"
    HOTEL = "hotel"
    USER = "user"


class PermissionManager:
    """
    Utility class for managing user permissions and access control
    
    Provides methods for checking, validating, and managing user permissions
    across different scopes and contexts.
    """
    
    @staticmethod
    def check_permission(
        user: AdminUser,
        required_permission: AdminPermission,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if user has required permission in given context
        
        Args:
            user: Admin user to check
            required_permission: Required permission
            context: Additional context (hotel_id, etc.)
            
        Returns:
            bool: True if user has permission
        """
        try:
            # Super admin has all permissions
            if user.role == AdminRole.SUPER_ADMIN:
                return True
            
            # Check if user has explicit permission
            if required_permission.value not in user.permissions:
                return False
            
            # Check context-specific permissions
            if context:
                hotel_id = context.get("hotel_id")
                if hotel_id and user.hotel_id:
                    # User can only access their own hotel
                    if str(user.hotel_id) != str(hotel_id):
                        return False
            
            return True
            
        except Exception as e:
            logger.error("Error checking permission", error=str(e))
            return False
    
    @staticmethod
    def get_effective_permissions(user: AdminUser) -> Set[str]:
        """
        Get all effective permissions for a user
        
        Args:
            user: Admin user
            
        Returns:
            Set of permission strings
        """
        try:
            # Start with explicit permissions
            permissions = set(user.permissions)
            
            # Add role-based permissions
            role_permissions = user.get_role_permissions()
            permissions.update(role_permissions)
            
            # Super admin gets all permissions
            if user.role == AdminRole.SUPER_ADMIN:
                permissions.update([p.value for p in AdminPermission])
            
            return permissions
            
        except Exception as e:
            logger.error("Error getting effective permissions", error=str(e))
            return set()
    
    @staticmethod
    def get_permission_scope(permission: AdminPermission) -> PermissionScope:
        """
        Get the scope level for a permission
        
        Args:
            permission: Permission to check
            
        Returns:
            PermissionScope: Scope level of the permission
        """
        global_permissions = [
            AdminPermission.MANAGE_SYSTEM,
            AdminPermission.VIEW_SYSTEM_METRICS,
            AdminPermission.MANAGE_HOTELS
        ]
        
        hotel_permissions = [
            AdminPermission.MANAGE_HOTEL_SETTINGS,
            AdminPermission.VIEW_HOTEL_ANALYTICS,
            AdminPermission.MANAGE_HOTEL_USERS,
            AdminPermission.MANAGE_TRIGGERS,
            AdminPermission.VIEW_CONVERSATIONS,
            AdminPermission.SEND_MESSAGES,
            AdminPermission.MANAGE_TEMPLATES,
            AdminPermission.VIEW_ANALYTICS,
            AdminPermission.EXPORT_DATA,
            AdminPermission.GENERATE_REPORTS,
            AdminPermission.VIEW_MONITORING,
            AdminPermission.MANAGE_ALERTS
        ]
        
        if permission in global_permissions:
            return PermissionScope.GLOBAL
        elif permission in hotel_permissions:
            return PermissionScope.HOTEL
        else:
            return PermissionScope.USER
    
    @staticmethod
    def validate_permission_assignment(
        assigning_user: AdminUser,
        target_user: AdminUser,
        permissions: List[AdminPermission]
    ) -> Dict[str, Any]:
        """
        Validate if assigning user can grant permissions to target user
        
        Args:
            assigning_user: User attempting to assign permissions
            target_user: User receiving permissions
            permissions: Permissions to assign
            
        Returns:
            Dict with validation results
        """
        try:
            result = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "allowed_permissions": [],
                "denied_permissions": []
            }
            
            # Super admin can assign any permissions
            if assigning_user.role == AdminRole.SUPER_ADMIN:
                result["allowed_permissions"] = [p.value for p in permissions]
                return result
            
            # Get assigning user's effective permissions
            assigning_permissions = PermissionManager.get_effective_permissions(assigning_user)
            
            for permission in permissions:
                permission_scope = PermissionManager.get_permission_scope(permission)
                
                # Check if assigning user has the permission
                if permission.value not in assigning_permissions:
                    result["denied_permissions"].append(permission.value)
                    result["errors"].append(f"You don't have permission: {permission.value}")
                    continue
                
                # Check scope-specific rules
                if permission_scope == PermissionScope.GLOBAL:
                    # Only super admin can assign global permissions
                    if assigning_user.role != AdminRole.SUPER_ADMIN:
                        result["denied_permissions"].append(permission.value)
                        result["errors"].append(f"Global permission requires super admin: {permission.value}")
                        continue
                
                elif permission_scope == PermissionScope.HOTEL:
                    # Hotel admins can only assign to users in their hotel
                    if (assigning_user.role == AdminRole.HOTEL_ADMIN and 
                        assigning_user.hotel_id != target_user.hotel_id):
                        result["denied_permissions"].append(permission.value)
                        result["errors"].append(f"Can only assign hotel permissions to users in your hotel: {permission.value}")
                        continue
                
                # Permission is allowed
                result["allowed_permissions"].append(permission.value)
            
            # Set overall validity
            result["valid"] = len(result["errors"]) == 0
            
            return result
            
        except Exception as e:
            logger.error("Error validating permission assignment", error=str(e))
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "allowed_permissions": [],
                "denied_permissions": []
            }
    
    @staticmethod
    def get_permission_conflicts(
        user: AdminUser,
        new_permissions: List[AdminPermission]
    ) -> List[Dict[str, Any]]:
        """
        Check for permission conflicts or redundancies
        
        Args:
            user: User to check
            new_permissions: New permissions to assign
            
        Returns:
            List of conflict information
        """
        try:
            conflicts = []
            current_permissions = set(user.permissions)
            new_permission_values = {p.value for p in new_permissions}
            
            # Check for redundant permissions (already has)
            redundant = current_permissions.intersection(new_permission_values)
            if redundant:
                conflicts.append({
                    "type": "redundant",
                    "permissions": list(redundant),
                    "message": "User already has these permissions"
                })
            
            # Check for role conflicts (permissions already granted by role)
            role_permissions = set(user.get_role_permissions())
            role_redundant = role_permissions.intersection(new_permission_values)
            if role_redundant:
                conflicts.append({
                    "type": "role_redundant",
                    "permissions": list(role_redundant),
                    "message": f"These permissions are already granted by role {user.role.value}"
                })
            
            # Check for scope conflicts
            hotel_permissions = [p for p in new_permissions if PermissionManager.get_permission_scope(p) == PermissionScope.HOTEL]
            if hotel_permissions and not user.hotel_id:
                conflicts.append({
                    "type": "scope_conflict",
                    "permissions": [p.value for p in hotel_permissions],
                    "message": "Hotel-scoped permissions require hotel association"
                })
            
            return conflicts
            
        except Exception as e:
            logger.error("Error checking permission conflicts", error=str(e))
            return []
    
    @staticmethod
    def suggest_role_for_permissions(permissions: List[AdminPermission]) -> Optional[AdminRole]:
        """
        Suggest appropriate role based on permission set
        
        Args:
            permissions: List of permissions
            
        Returns:
            Suggested AdminRole or None
        """
        try:
            permission_values = {p.value for p in permissions}
            
            # Check if permissions match any role exactly
            for role in AdminRole:
                role_permissions = set()
                if role == AdminRole.SUPER_ADMIN:
                    role_permissions = {p.value for p in AdminPermission}
                elif role == AdminRole.HOTEL_ADMIN:
                    role_permissions = {
                        AdminPermission.MANAGE_HOTEL_SETTINGS.value,
                        AdminPermission.VIEW_HOTEL_ANALYTICS.value,
                        AdminPermission.MANAGE_HOTEL_USERS.value,
                        AdminPermission.MANAGE_TRIGGERS.value,
                        AdminPermission.VIEW_CONVERSATIONS.value,
                        AdminPermission.SEND_MESSAGES.value,
                        AdminPermission.MANAGE_TEMPLATES.value,
                        AdminPermission.VIEW_ANALYTICS.value,
                        AdminPermission.EXPORT_DATA.value,
                        AdminPermission.GENERATE_REPORTS.value,
                        AdminPermission.VIEW_MONITORING.value,
                    }
                elif role == AdminRole.HOTEL_STAFF:
                    role_permissions = {
                        AdminPermission.VIEW_HOTEL_ANALYTICS.value,
                        AdminPermission.VIEW_CONVERSATIONS.value,
                        AdminPermission.SEND_MESSAGES.value,
                        AdminPermission.VIEW_ANALYTICS.value,
                        AdminPermission.VIEW_MONITORING.value,
                    }
                elif role == AdminRole.VIEWER:
                    role_permissions = {
                        AdminPermission.VIEW_HOTEL_ANALYTICS.value,
                        AdminPermission.VIEW_CONVERSATIONS.value,
                        AdminPermission.VIEW_ANALYTICS.value,
                        AdminPermission.VIEW_MONITORING.value,
                    }
                
                # Check if permissions are subset of role permissions
                if permission_values.issubset(role_permissions):
                    return role
            
            return None
            
        except Exception as e:
            logger.error("Error suggesting role for permissions", error=str(e))
            return None
    
    @staticmethod
    def get_permission_dependencies(permission: AdminPermission) -> List[AdminPermission]:
        """
        Get permissions that are dependencies for the given permission
        
        Args:
            permission: Permission to check dependencies for
            
        Returns:
            List of dependent permissions
        """
        try:
            dependencies = {
                AdminPermission.MANAGE_HOTEL_USERS: [AdminPermission.VIEW_HOTEL_ANALYTICS],
                AdminPermission.GENERATE_REPORTS: [AdminPermission.VIEW_ANALYTICS],
                AdminPermission.EXPORT_DATA: [AdminPermission.VIEW_ANALYTICS],
                AdminPermission.MANAGE_ALERTS: [AdminPermission.VIEW_MONITORING],
                AdminPermission.SEND_MESSAGES: [AdminPermission.VIEW_CONVERSATIONS],
                AdminPermission.MANAGE_TEMPLATES: [AdminPermission.VIEW_CONVERSATIONS],
                AdminPermission.MANAGE_TRIGGERS: [AdminPermission.VIEW_CONVERSATIONS],
            }
            
            return dependencies.get(permission, [])
            
        except Exception as e:
            logger.error("Error getting permission dependencies", error=str(e))
            return []
    
    @staticmethod
    def validate_permission_dependencies(permissions: List[AdminPermission]) -> Dict[str, Any]:
        """
        Validate that all permission dependencies are satisfied
        
        Args:
            permissions: List of permissions to validate
            
        Returns:
            Dict with validation results
        """
        try:
            result = {
                "valid": True,
                "missing_dependencies": [],
                "suggestions": []
            }
            
            permission_values = {p.value for p in permissions}
            
            for permission in permissions:
                dependencies = PermissionManager.get_permission_dependencies(permission)
                
                for dep in dependencies:
                    if dep.value not in permission_values:
                        result["missing_dependencies"].append({
                            "permission": permission.value,
                            "missing_dependency": dep.value
                        })
                        result["suggestions"].append(f"Add {dep.value} for {permission.value}")
            
            result["valid"] = len(result["missing_dependencies"]) == 0
            
            return result
            
        except Exception as e:
            logger.error("Error validating permission dependencies", error=str(e))
            return {
                "valid": False,
                "missing_dependencies": [],
                "suggestions": [f"Validation error: {str(e)}"]
            }
