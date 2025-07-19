"""
Role model for WhatsApp Hotel Bot application

This module defines user roles and permissions for the general user system
(separate from admin roles).
"""

import enum
from typing import List, Dict, Any
from sqlalchemy import Column, String, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import validates

from app.models.base import BaseModel, TimestampMixin


class UserRole(str, enum.Enum):
    """User roles for the general user system"""
    SUPER_ADMIN = "super_admin"  # Full system access
    HOTEL_ADMIN = "hotel_admin"  # Hotel-specific admin
    HOTEL_STAFF = "hotel_staff"  # Hotel staff member
    VIEWER = "viewer"           # Read-only access


class UserPermission(str, enum.Enum):
    """User permissions for the general user system"""
    # System permissions
    MANAGE_SYSTEM = "manage_system"
    VIEW_SYSTEM_METRICS = "view_system_metrics"
    MANAGE_HOTELS = "manage_hotels"
    
    # Hotel permissions
    MANAGE_HOTEL_SETTINGS = "manage_hotel_settings"
    VIEW_HOTEL_ANALYTICS = "view_hotel_analytics"
    MANAGE_HOTEL_USERS = "manage_hotel_users"
    MANAGE_TRIGGERS = "manage_triggers"
    
    # Message permissions
    VIEW_CONVERSATIONS = "view_conversations"
    SEND_MESSAGES = "send_messages"
    MANAGE_TEMPLATES = "manage_templates"
    
    # Analytics permissions
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_DATA = "export_data"
    GENERATE_REPORTS = "generate_reports"
    
    # Monitoring permissions
    VIEW_MONITORING = "view_monitoring"
    MANAGE_ALERTS = "manage_alerts"


class Role(BaseModel, TimestampMixin):
    """
    Role model for user role-based access control
    
    This model defines roles and their associated permissions for the general
    user system.
    """
    __tablename__ = "user_roles"
    
    # Role information
    name = Column(
        String(50),
        nullable=False,
        unique=True,
        comment="Role name"
    )
    
    display_name = Column(
        String(100),
        nullable=False,
        comment="Human-readable role name"
    )
    
    description = Column(
        String(500),
        nullable=True,
        comment="Role description"
    )
    
    # Permissions
    permissions = Column(
        JSON,
        nullable=False,
        default=list,
        comment="List of permissions for this role"
    )
    
    # Role metadata
    is_system_role = Column(
        String(10),
        nullable=False,
        default="false",
        comment="Whether this is a system-defined role"
    )
    
    is_active = Column(
        String(10),
        nullable=False,
        default="true",
        comment="Whether this role is active"
    )
    
    # Additional metadata
    role_metadata = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Additional role metadata"
    )
    
    __table_args__ = (
        # Indexes for performance
        Index('idx_user_roles_name', 'name'),
        Index('idx_user_roles_active', 'is_active'),
        Index('idx_user_roles_system', 'is_system_role'),
    )
    
    @validates('name')
    def validate_name(self, key, name):
        """Validate role name"""
        if not name or len(name.strip()) == 0:
            raise ValueError("Role name cannot be empty")
        
        if len(name) > 50:
            raise ValueError("Role name cannot exceed 50 characters")
        
        # Convert to lowercase and replace spaces with underscores
        return name.lower().replace(' ', '_')
    
    @validates('permissions')
    def validate_permissions(self, key, permissions):
        """Validate permissions list"""
        if not isinstance(permissions, list):
            raise ValueError("Permissions must be a list")
        
        # Validate each permission
        valid_permissions = [p.value for p in UserPermission]
        for permission in permissions:
            if permission not in valid_permissions:
                raise ValueError(f"Invalid permission: {permission}")
        
        return permissions
    
    @property
    def is_system_role_bool(self) -> bool:
        """Get is_system_role as boolean"""
        return self.is_system_role == "true"
    
    @is_system_role_bool.setter
    def is_system_role_bool(self, value: bool):
        """Set is_system_role from boolean"""
        self.is_system_role = "true" if value else "false"
    
    @property
    def is_active_bool(self) -> bool:
        """Get is_active as boolean"""
        return self.is_active == "true"
    
    @is_active_bool.setter
    def is_active_bool(self, value: bool):
        """Set is_active from boolean"""
        self.is_active = "true" if value else "false"
    
    def has_permission(self, permission: UserPermission) -> bool:
        """
        Check if role has specific permission
        
        Args:
            permission: Permission to check
            
        Returns:
            bool: True if role has permission
        """
        return permission.value in self.permissions
    
    def add_permission(self, permission: UserPermission) -> None:
        """
        Add permission to role
        
        Args:
            permission: Permission to add
        """
        if permission.value not in self.permissions:
            self.permissions = self.permissions + [permission.value]
    
    def remove_permission(self, permission: UserPermission) -> None:
        """
        Remove permission from role
        
        Args:
            permission: Permission to remove
        """
        if permission.value in self.permissions:
            self.permissions = [p for p in self.permissions if p != permission.value]
    
    def get_permission_objects(self) -> List[UserPermission]:
        """
        Get permission objects for this role
        
        Returns:
            List[UserPermission]: List of permission enums
        """
        permission_objects = []
        for permission_str in self.permissions:
            try:
                permission_objects.append(UserPermission(permission_str))
            except ValueError:
                # Skip invalid permissions
                continue
        return permission_objects
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert role to dictionary
        
        Returns:
            Dict[str, Any]: Role data
        """
        return {
            "id": str(self.id),
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "permissions": self.permissions,
            "is_system_role": self.is_system_role_bool,
            "is_active": self.is_active_bool,
            "metadata": self.role_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_default_role_permissions(cls, role: UserRole) -> List[str]:
        """
        Get default permissions for a role
        
        Args:
            role: User role
            
        Returns:
            List[str]: List of permission strings
        """
        role_permissions = {
            UserRole.SUPER_ADMIN: [p.value for p in UserPermission],
            UserRole.HOTEL_ADMIN: [
                UserPermission.MANAGE_HOTEL_SETTINGS.value,
                UserPermission.VIEW_HOTEL_ANALYTICS.value,
                UserPermission.MANAGE_HOTEL_USERS.value,
                UserPermission.MANAGE_TRIGGERS.value,
                UserPermission.VIEW_CONVERSATIONS.value,
                UserPermission.SEND_MESSAGES.value,
                UserPermission.MANAGE_TEMPLATES.value,
                UserPermission.VIEW_ANALYTICS.value,
                UserPermission.EXPORT_DATA.value,
                UserPermission.GENERATE_REPORTS.value,
                UserPermission.VIEW_MONITORING.value,
            ],
            UserRole.HOTEL_STAFF: [
                UserPermission.VIEW_CONVERSATIONS.value,
                UserPermission.SEND_MESSAGES.value,
                UserPermission.VIEW_ANALYTICS.value,
                UserPermission.VIEW_MONITORING.value,
            ],
            UserRole.VIEWER: [
                UserPermission.VIEW_CONVERSATIONS.value,
                UserPermission.VIEW_ANALYTICS.value,
            ]
        }
        
        return role_permissions.get(role, [])
