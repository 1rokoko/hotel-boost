"""
Authentication schemas for user authentication

This module defines Pydantic schemas for user authentication requests and responses.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.role import UserRole


class UserBase(BaseModel):
    """Base user schema"""
    
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")
    role: UserRole = Field(default=UserRole.VIEWER, description="User role")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Associated hotel ID for hotel-specific users")
    is_active: bool = Field(default=True, description="Whether the user account is active")


class UserCreate(UserBase):
    """Schema for creating a new user"""
    
    password: str = Field(..., min_length=8, description="User password")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')

        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')

        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')

        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')

        return v


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    
    email: Optional[EmailStr] = Field(None, description="User email address")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Username")
    full_name: Optional[str] = Field(None, min_length=1, max_length=255, description="User full name")
    role: Optional[UserRole] = Field(None, description="User role")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Associated hotel ID")
    is_active: Optional[bool] = Field(None, description="Whether the user account is active")
    permissions: Optional[List[str]] = Field(None, description="User permissions")


class UserResponse(UserBase):
    """Schema for user response"""
    
    id: uuid.UUID = Field(..., description="User unique identifier")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    is_verified: bool = Field(..., description="Whether the user email is verified")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    is_locked: bool = Field(..., description="Whether the user account is locked")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: datetime = Field(..., description="User last update timestamp")
    
    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Schema for login request"""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    """Schema for login response"""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="User information")


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request"""
    
    refresh_token: str = Field(..., description="JWT refresh token")


class TokenRefreshResponse(BaseModel):
    """Schema for token refresh response"""
    
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class PasswordChangeRequest(BaseModel):
    """Schema for password change request"""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        
        return v


class PasswordResetRequest(BaseModel):
    """Schema for password reset request"""
    
    email: EmailStr = Field(..., description="User email address")


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""
    
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        
        return v


class UserSessionInfo(BaseModel):
    """Schema for user session information"""
    
    user_id: uuid.UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    username: str = Field(..., description="Username")
    role: UserRole = Field(..., description="User role")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Associated hotel ID")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    session_id: str = Field(..., description="Session ID")
    expires_at: datetime = Field(..., description="Session expiration time")


class PermissionCheck(BaseModel):
    """Schema for permission check request"""
    
    permission: str = Field(..., description="Permission to check")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Hotel ID for hotel-specific permissions")


class PermissionCheckResponse(BaseModel):
    """Schema for permission check response"""
    
    has_permission: bool = Field(..., description="Whether user has the permission")
    reason: Optional[str] = Field(None, description="Reason if permission is denied")


class RoleInfo(BaseModel):
    """Schema for role information"""
    
    name: str = Field(..., description="Role name")
    display_name: str = Field(..., description="Human-readable role name")
    description: Optional[str] = Field(None, description="Role description")
    permissions: List[str] = Field(default_factory=list, description="Role permissions")


class UserListResponse(BaseModel):
    """Schema for user list response"""
    
    users: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Number of users per page")
    pages: int = Field(..., description="Total number of pages")
