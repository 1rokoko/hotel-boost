"""
Admin User model for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, DateTime, Boolean, Index, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import enum
import re
from passlib.context import CryptContext

from app.models.base import BaseModel, TimestampMixin

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminRole(str, enum.Enum):
    """Admin user roles"""
    SUPER_ADMIN = "super_admin"  # Full system access
    HOTEL_ADMIN = "hotel_admin"  # Hotel-specific admin
    HOTEL_STAFF = "hotel_staff"  # Hotel staff member
    VIEWER = "viewer"           # Read-only access


class AdminPermission(str, enum.Enum):
    """Admin permissions"""
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


class AdminUser(BaseModel, TimestampMixin):
    """
    Admin user model for hotel management system
    
    Supports role-based access control and multi-tenant permissions.
    """
    __tablename__ = "admin_users"
    
    # Basic user information
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        comment="Admin user email address"
    )
    
    username = Column(
        String(100),
        nullable=False,
        unique=True,
        comment="Admin username"
    )
    
    full_name = Column(
        String(255),
        nullable=False,
        comment="Admin user full name"
    )
    
    # Authentication
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Hashed password"
    )
    
    # Role and permissions
    role = Column(
        SQLEnum(AdminRole),
        nullable=False,
        default=AdminRole.VIEWER,
        comment="Admin user role"
    )
    
    permissions = Column(
        JSON,
        nullable=False,
        default=list,
        comment="List of specific permissions"
    )
    
    # Hotel association (for hotel-specific admins)
    hotel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hotels.id', ondelete='CASCADE'),
        nullable=True,
        comment="Associated hotel ID for hotel-specific admins"
    )
    
    # Account status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the admin account is active"
    )
    
    is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the admin email is verified"
    )
    
    # Session management
    last_login = Column(
        DateTime,
        nullable=True,
        comment="Last login timestamp"
    )
    
    failed_login_attempts = Column(
        String(10),
        nullable=False,
        default="0",
        comment="Number of failed login attempts"
    )
    
    locked_until = Column(
        DateTime,
        nullable=True,
        comment="Account locked until this timestamp"
    )
    
    # Additional metadata
    user_metadata = Column(
        JSON,
        nullable=False,
        default=dict,
        comment="Additional admin user metadata"
    )
    
    __table_args__ = (
        # Indexes for performance
        Index('idx_admin_users_email', 'email'),
        Index('idx_admin_users_username', 'username'),
        Index('idx_admin_users_role', 'role'),
        Index('idx_admin_users_hotel_id', 'hotel_id'),
        Index('idx_admin_users_active', 'is_active'),
        Index('idx_admin_users_last_login', 'last_login'),
    )
    
    # Relationships
    hotel = relationship("Hotel", back_populates="admin_users")
    audit_logs = relationship("AdminAuditLog", back_populates="admin_user", cascade="all, delete-orphan")
    
    @validates('email')
    def validate_email(self, key, email):
        """Validate email format"""
        if not email:
            raise ValueError("Email is required")
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")
        
        return email.lower()
    
    @validates('username')
    def validate_username(self, key, username):
        """Validate username format"""
        if not username:
            raise ValueError("Username is required")
        
        if len(username) < 3 or len(username) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        
        username_pattern = r'^[a-zA-Z0-9_-]+$'
        if not re.match(username_pattern, username):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        
        return username.lower()
    
    @validates('permissions')
    def validate_permissions(self, key, permissions):
        """Validate permissions list"""
        if not isinstance(permissions, list):
            raise ValueError("Permissions must be a list")
        
        valid_permissions = [p.value for p in AdminPermission]
        for permission in permissions:
            if permission not in valid_permissions:
                raise ValueError(f"Invalid permission: {permission}")
        
        return permissions
    
    @hybrid_property
    def is_locked(self):
        """Check if account is currently locked"""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until
    
    def set_password(self, password: str) -> None:
        """Set hashed password"""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        self.hashed_password = pwd_context.hash(password)
    
    def verify_password(self, password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(password, self.hashed_password)
    
    def has_permission(self, permission: AdminPermission) -> bool:
        """Check if user has specific permission"""
        # Super admin has all permissions
        if self.role == AdminRole.SUPER_ADMIN:
            return True
        
        # Check explicit permissions
        return permission.value in self.permissions
    
    def has_role(self, role: AdminRole) -> bool:
        """Check if user has specific role"""
        return self.role == role
    
    def can_access_hotel(self, hotel_id: uuid.UUID) -> bool:
        """Check if user can access specific hotel"""
        # Super admin can access all hotels
        if self.role == AdminRole.SUPER_ADMIN:
            return True
        
        # Hotel-specific users can only access their hotel
        return self.hotel_id == hotel_id
    
    def get_role_permissions(self) -> List[str]:
        """Get default permissions for user role"""
        role_permissions = {
            AdminRole.SUPER_ADMIN: [p.value for p in AdminPermission],
            AdminRole.HOTEL_ADMIN: [
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
            ],
            AdminRole.HOTEL_STAFF: [
                AdminPermission.VIEW_HOTEL_ANALYTICS.value,
                AdminPermission.VIEW_CONVERSATIONS.value,
                AdminPermission.SEND_MESSAGES.value,
                AdminPermission.VIEW_ANALYTICS.value,
                AdminPermission.VIEW_MONITORING.value,
            ],
            AdminRole.VIEWER: [
                AdminPermission.VIEW_HOTEL_ANALYTICS.value,
                AdminPermission.VIEW_CONVERSATIONS.value,
                AdminPermission.VIEW_ANALYTICS.value,
                AdminPermission.VIEW_MONITORING.value,
            ]
        }
        
        return role_permissions.get(self.role, [])
    
    def update_last_login(self) -> None:
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        self.failed_login_attempts = "0"
        self.locked_until = None
    
    def increment_failed_login(self) -> None:
        """Increment failed login attempts and lock if necessary"""
        current_attempts = int(self.failed_login_attempts or "0")
        current_attempts += 1
        self.failed_login_attempts = str(current_attempts)
        
        # Lock account after 5 failed attempts for 30 minutes
        if current_attempts >= 5:
            from datetime import timedelta
            self.locked_until = datetime.utcnow() + timedelta(minutes=30)
    
    def unlock_account(self) -> None:
        """Unlock account and reset failed attempts"""
        self.locked_until = None
        self.failed_login_attempts = "0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)"""
        return {
            'id': str(self.id),
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'role': self.role.value,
            'permissions': self.permissions,
            'hotel_id': str(self.hotel_id) if self.hotel_id else None,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_locked': self.is_locked,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f"<AdminUser(id={self.id}, email={self.email}, role={self.role})>"
