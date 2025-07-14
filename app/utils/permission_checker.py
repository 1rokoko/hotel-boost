"""
Permission checking utilities for user authorization

This module provides utilities for checking user permissions and access control.
"""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status, Depends, Request
import structlog

from app.models.user import User
from app.models.role import UserRole, UserPermission
from app.core.security import AuthorizationError

logger = structlog.get_logger(__name__)


class PermissionChecker:
    """Utility class for checking user permissions"""
    
    @staticmethod
    def check_permission(
        user: User,
        required_permission: UserPermission,
        hotel_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Check if user has required permission
        
        Args:
            user: User to check
            required_permission: Required permission
            hotel_id: Hotel ID being accessed (if applicable)
            
        Returns:
            bool: True if user has permission
        """
        # Super admin has all permissions
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        # Check explicit permission
        if not user.has_permission(required_permission):
            return False
        
        # Check hotel access for hotel-specific operations
        if hotel_id is not None and user.hotel_id is not None:
            if hotel_id != user.hotel_id:
                return False
        
        return True
    
    @staticmethod
    def validate_user_access(
        user: User,
        required_permission: UserPermission,
        target_hotel_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Validate user access for specific operation
        
        Args:
            user: User to validate
            required_permission: Required permission
            target_hotel_id: Target hotel ID (if applicable)
            
        Returns:
            bool: True if access is allowed
            
        Raises:
            AuthorizationError: If access is denied
        """
        # Check if account is active
        if not user.is_active:
            raise AuthorizationError("Account is deactivated")
        
        # Check if account is locked
        if user.is_locked:
            raise AuthorizationError("Account is locked")
        
        # Check permission
        has_permission = PermissionChecker.check_permission(
            user=user,
            required_permission=required_permission,
            hotel_id=target_hotel_id
        )
        
        if not has_permission:
            raise AuthorizationError(
                f"Insufficient permissions. Required: {required_permission.value}"
            )
        
        return True
    
    @staticmethod
    def get_permission_description(permission: UserPermission) -> str:
        """Get human-readable permission description"""
        descriptions = {
            UserPermission.MANAGE_SYSTEM: "Manage system-wide settings and configuration",
            UserPermission.VIEW_SYSTEM_METRICS: "View system-wide metrics and performance data",
            UserPermission.MANAGE_HOTELS: "Create, update, and delete hotels",
            UserPermission.MANAGE_HOTEL_SETTINGS: "Manage hotel-specific settings and configuration",
            UserPermission.VIEW_HOTEL_ANALYTICS: "View hotel analytics and statistics",
            UserPermission.MANAGE_HOTEL_USERS: "Manage hotel staff and user accounts",
            UserPermission.MANAGE_TRIGGERS: "Create and manage automated triggers",
            UserPermission.VIEW_CONVERSATIONS: "View guest conversations and message history",
            UserPermission.SEND_MESSAGES: "Send messages to guests",
            UserPermission.MANAGE_TEMPLATES: "Create and manage message templates",
            UserPermission.VIEW_ANALYTICS: "View analytics and reports",
            UserPermission.EXPORT_DATA: "Export data and generate reports",
            UserPermission.GENERATE_REPORTS: "Generate custom reports",
            UserPermission.VIEW_MONITORING: "View system monitoring and health status",
            UserPermission.MANAGE_ALERTS: "Manage alerts and notifications"
        }
        return descriptions.get(permission, permission.value)
    
    @staticmethod
    def get_role_description(role: UserRole) -> str:
        """Get human-readable role description"""
        descriptions = {
            UserRole.SUPER_ADMIN: "Full system access with all permissions",
            UserRole.HOTEL_ADMIN: "Hotel administrator with management permissions",
            UserRole.HOTEL_STAFF: "Hotel staff member with operational permissions",
            UserRole.VIEWER: "Read-only access to hotel data and analytics"
        }
        return descriptions.get(role, role.value)
    
    @staticmethod
    def get_user_permissions_summary(user: User) -> Dict[str, Any]:
        """
        Get summary of user permissions
        
        Args:
            user: User to analyze
            
        Returns:
            Dict containing permission summary
        """
        role_permissions = user.get_role_permissions()
        explicit_permissions = user.permissions
        all_permissions = user.get_all_permissions()
        
        return {
            "user_id": str(user.id),
            "role": user.role.value if user.role else None,
            "role_description": PermissionChecker.get_role_description(user.role) if user.role else None,
            "role_permissions": role_permissions,
            "explicit_permissions": explicit_permissions,
            "all_permissions": all_permissions,
            "hotel_id": str(user.hotel_id) if user.hotel_id else None,
            "is_super_admin": user.role == UserRole.SUPER_ADMIN,
            "permission_count": len(all_permissions)
        }


def require_permission(permission: UserPermission, hotel_id_param: Optional[str] = None):
    """
    Decorator to require specific permission for endpoint access
    
    Args:
        permission: Required permission
        hotel_id_param: Parameter name for hotel ID (if applicable)
        
    Returns:
        Dependency function
    """
    def permission_dependency(request: Request) -> User:
        """
        Check if current user has required permission
        
        Args:
            request: HTTP request with user in state
            
        Returns:
            User: Current user if authorized
            
        Raises:
            HTTPException: If permission check fails
        """
        try:
            # Get user from request state (set by auth middleware)
            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Get hotel ID if specified
            target_hotel_id = None
            if hotel_id_param:
                hotel_id_str = request.path_params.get(hotel_id_param)
                if hotel_id_str:
                    try:
                        target_hotel_id = uuid.UUID(hotel_id_str)
                    except ValueError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid hotel ID format"
                        )
            
            # Validate permission
            PermissionChecker.validate_user_access(
                user=user,
                required_permission=permission,
                target_hotel_id=target_hotel_id
            )
            
            return user
            
        except AuthorizationError as e:
            logger.warning(
                "Permission denied",
                user_id=str(user.id) if user else None,
                required_permission=permission.value,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Permission check error", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission check failed"
            )
    
    return permission_dependency


def require_role(role: UserRole):
    """
    Decorator to require specific role for endpoint access
    
    Args:
        role: Required role
        
    Returns:
        Dependency function
    """
    def role_dependency(request: Request) -> User:
        """
        Check if current user has required role
        
        Args:
            request: HTTP request with user in state
            
        Returns:
            User: Current user if authorized
            
        Raises:
            HTTPException: If role check fails
        """
        try:
            # Get user from request state
            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Check role
            if not user.has_role(role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{role.value}' required"
                )
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Role check error", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Role check failed"
            )
    
    return role_dependency


def get_current_user_from_request(request: Request) -> Optional[User]:
    """
    Get current user from request state
    
    Args:
        request: HTTP request
        
    Returns:
        Optional[User]: Current user if authenticated
    """
    return getattr(request.state, 'user', None)
