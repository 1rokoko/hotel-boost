"""
Admin authentication schemas for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, EmailStr, field_validator
import re

from app.models.admin_user import AdminRole, AdminPermission


class AdminUserBase(BaseModel):
    """Base admin user schema"""
    
    email: EmailStr = Field(..., description="Admin user email address")
    username: str = Field(..., min_length=3, max_length=50, description="Admin username")
    full_name: str = Field(..., min_length=1, max_length=255, description="Admin user full name")
    role: AdminRole = Field(default=AdminRole.VIEWER, description="Admin user role")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Associated hotel ID for hotel-specific admins")
    is_active: bool = Field(default=True, description="Whether the admin account is active")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validate username format"""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.lower()
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        """Validate full name"""
        if not v.strip():
            raise ValueError('Full name cannot be empty')
        return v.strip()


class AdminUserCreate(AdminUserBase):
    """Schema for creating admin user"""
    
    password: str = Field(..., min_length=8, description="Admin user password")
    permissions: List[AdminPermission] = Field(default_factory=list, description="Specific permissions")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        # Check for at least one uppercase, one lowercase, one digit
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        return v


class AdminUserUpdate(BaseModel):
    """Schema for updating admin user"""
    
    email: Optional[EmailStr] = Field(None, description="Admin user email address")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Admin username")
    full_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Admin user full name")
    role: Optional[AdminRole] = Field(None, description="Admin user role")
    permissions: Optional[List[AdminPermission]] = Field(None, description="Specific permissions")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Associated hotel ID")
    is_active: Optional[bool] = Field(None, description="Whether the admin account is active")
    is_verified: Optional[bool] = Field(None, description="Whether the admin email is verified")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validate username format"""
        if v is not None and not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.lower() if v else v
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        """Validate full name"""
        if v is not None and not v.strip():
            raise ValueError('Full name cannot be empty')
        return v.strip() if v else v


class AdminUserResponse(AdminUserBase):
    """Schema for admin user response"""
    
    id: uuid.UUID = Field(..., description="Admin user ID")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    is_verified: bool = Field(..., description="Whether the admin email is verified")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    is_locked: bool = Field(..., description="Whether the account is locked")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    """Schema for admin user list response"""
    
    users: List[AdminUserResponse] = Field(..., description="List of admin users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Number of users per page")
    total_pages: int = Field(..., description="Total number of pages")


class AdminLoginRequest(BaseModel):
    """Schema for admin login request"""
    
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")
    remember_me: bool = Field(default=False, description="Remember login session")


class AdminLoginResponse(BaseModel):
    """Schema for admin login response"""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: AdminUserResponse = Field(..., description="Admin user information")


class AdminTokenRefreshRequest(BaseModel):
    """Schema for token refresh request"""
    
    refresh_token: str = Field(..., description="Refresh token")


class AdminTokenRefreshResponse(BaseModel):
    """Schema for token refresh response"""
    
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class AdminPasswordChangeRequest(BaseModel):
    """Schema for password change request"""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        """Validate that passwords match"""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        """Validate new password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        # Check for at least one uppercase, one lowercase, one digit
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        return v


class AdminPasswordResetRequest(BaseModel):
    """Schema for password reset request"""
    
    email: EmailStr = Field(..., description="Admin user email")


class AdminPasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""
    
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        """Validate that passwords match"""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        """Validate new password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        # Check for at least one uppercase, one lowercase, one digit
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        
        return v


class AdminPermissionResponse(BaseModel):
    """Schema for admin permission response"""
    
    permission: str = Field(..., description="Permission name")
    description: str = Field(..., description="Permission description")


class AdminRoleResponse(BaseModel):
    """Schema for admin role response"""
    
    role: str = Field(..., description="Role name")
    description: str = Field(..., description="Role description")
    permissions: List[str] = Field(..., description="Default permissions for this role")


class AdminUserSearchParams(BaseModel):
    """Schema for admin user search parameters"""
    
    search: Optional[str] = Field(None, description="Search term for username, email, or full name")
    role: Optional[AdminRole] = Field(None, description="Filter by role")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Filter by hotel")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_verified: Optional[bool] = Field(None, description="Filter by verification status")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: str = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class AdminSessionInfo(BaseModel):
    """Schema for admin session information"""
    
    user_id: uuid.UUID = Field(..., description="Admin user ID")
    username: str = Field(..., description="Username")
    role: AdminRole = Field(..., description="User role")
    permissions: List[str] = Field(..., description="User permissions")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Associated hotel ID")
    session_id: str = Field(..., description="Session ID")
    expires_at: datetime = Field(..., description="Session expiration time")
    
    class Config:
        from_attributes = True
