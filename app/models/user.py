"""
User model for WhatsApp Hotel Bot application

This module defines the User model for general user authentication and management
(separate from admin users).
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, DateTime, Boolean, Index, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import re
from passlib.context import CryptContext

from app.models.base import BaseModel, TimestampMixin
from app.models.role import UserRole, UserPermission

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(BaseModel, TimestampMixin):
    """
    User model for general user authentication and management
    
    This model handles regular users (hotel staff, etc.) separate from admin users.
    Supports role-based access control and multi-tenant permissions.
    """
    __tablename__ = "users"
    
    # Basic user information
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        comment="User email address"
    )
    
    username = Column(
        String(100),
        nullable=False,
        unique=True,
        comment="Username"
    )
    
    full_name = Column(
        String(255),
        nullable=False,
        comment="User full name"
    )
    
    # Authentication
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Hashed password"
    )
    
    # Role and permissions
    role = Column(
        SQLEnum(UserRole),
        nullable=False,
        default=UserRole.VIEWER,
        comment="User role"
    )
    
    permissions = Column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of specific permissions"
    )
    
    # Hotel association (for hotel-specific users)
    hotel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hotels.id', ondelete='CASCADE'),
        nullable=True,
        comment="Associated hotel ID for hotel-specific users"
    )
    
    # Account status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the user account is active"
    )
    
    is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the user email is verified"
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
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional user metadata"
    )
    
    __table_args__ = (
        # Indexes for performance
        Index('idx_users_email', 'email'),
        Index('idx_users_username', 'username'),
        Index('idx_users_role', 'role'),
        Index('idx_users_hotel_id', 'hotel_id'),
        Index('idx_users_active', 'is_active'),
        Index('idx_users_last_login', 'last_login'),
    )
    
    # Relationships
    hotel = relationship("Hotel", back_populates="users")
    
    @validates('email')
    def validate_email(self, key, email):
        """Validate email format"""
        if not email:
            raise ValueError("Email is required")
        
        email = email.lower().strip()
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")
        
        return email
    
    @validates('username')
    def validate_username(self, key, username):
        """Validate username"""
        if not username:
            raise ValueError("Username is required")
        
        username = username.strip()
        
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")
        
        if len(username) > 50:
            raise ValueError("Username cannot exceed 50 characters")
        
        # Username can only contain alphanumeric characters and underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        
        return username
    
    @validates('full_name')
    def validate_full_name(self, key, full_name):
        """Validate full name"""
        if not full_name:
            raise ValueError("Full name is required")
        
        full_name = full_name.strip()
        
        if len(full_name) < 1:
            raise ValueError("Full name cannot be empty")
        
        if len(full_name) > 255:
            raise ValueError("Full name cannot exceed 255 characters")
        
        return full_name
    
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
    
    @hybrid_property
    def is_locked(self) -> bool:
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
    
    def has_permission(self, permission: UserPermission) -> bool:
        """Check if user has specific permission"""
        # Super admin has all permissions
        if self.role == UserRole.SUPER_ADMIN:
            return True
        
        # Check explicit permissions
        return permission.value in self.permissions
    
    def has_role(self, role: UserRole) -> bool:
        """Check if user has specific role"""
        return self.role == role
    
    def can_access_hotel(self, hotel_id: uuid.UUID) -> bool:
        """Check if user can access specific hotel"""
        # Super admin can access all hotels
        if self.role == UserRole.SUPER_ADMIN:
            return True
        
        # Hotel-specific users can only access their hotel
        return self.hotel_id == hotel_id
    
    def get_role_permissions(self) -> List[str]:
        """Get default permissions for user role"""
        from app.models.role import Role
        return Role.get_default_role_permissions(self.role)
    
    def get_all_permissions(self) -> List[str]:
        """Get all permissions (role + explicit)"""
        role_permissions = self.get_role_permissions()
        all_permissions = set(role_permissions + self.permissions)
        return list(all_permissions)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert user to dictionary (excluding sensitive data)
        
        Returns:
            Dict[str, Any]: User data
        """
        return {
            "id": str(self.id),
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role.value if self.role else None,
            "permissions": self.permissions,
            "hotel_id": str(self.hotel_id) if self.hotel_id else None,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_locked": self.is_locked,
            "metadata": self.user_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
