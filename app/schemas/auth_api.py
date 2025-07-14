"""
Authentication API schemas for user authentication endpoints

This module defines Pydantic schemas specifically for authentication API endpoints.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.models.role import UserRole


class AuthLoginRequest(BaseModel):
    """Schema for authentication login request"""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    remember_me: bool = Field(default=False, description="Whether to extend session duration")


class AuthLoginResponse(BaseModel):
    """Schema for authentication login response"""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: Dict[str, Any] = Field(..., description="User information")
    session_id: str = Field(..., description="Session identifier")


class AuthTokenRefreshRequest(BaseModel):
    """Schema for token refresh request"""
    
    refresh_token: str = Field(..., description="JWT refresh token")


class AuthTokenRefreshResponse(BaseModel):
    """Schema for token refresh response"""
    
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class AuthLogoutRequest(BaseModel):
    """Schema for logout request"""
    
    refresh_token: Optional[str] = Field(None, description="JWT refresh token to invalidate")


class AuthLogoutResponse(BaseModel):
    """Schema for logout response"""
    
    message: str = Field(default="Successfully logged out", description="Logout confirmation message")


class AuthRegisterRequest(BaseModel):
    """Schema for user registration request"""
    
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    full_name: str = Field(..., min_length=1, max_length=255, description="User full name")
    password: str = Field(..., min_length=8, description="User password")
    role: UserRole = Field(default=UserRole.VIEWER, description="User role")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Associated hotel ID")
    
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


class AuthRegisterResponse(BaseModel):
    """Schema for user registration response"""
    
    user: Dict[str, Any] = Field(..., description="Created user information")
    message: str = Field(default="User registered successfully", description="Registration confirmation message")


class AuthPasswordChangeRequest(BaseModel):
    """Schema for password change request"""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @field_validator('new_password')
    @classmethod
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


class AuthPasswordChangeResponse(BaseModel):
    """Schema for password change response"""
    
    message: str = Field(default="Password changed successfully", description="Password change confirmation")


class AuthPasswordResetRequest(BaseModel):
    """Schema for password reset request"""
    
    email: EmailStr = Field(..., description="User email address")


class AuthPasswordResetResponse(BaseModel):
    """Schema for password reset response"""
    
    message: str = Field(default="Password reset instructions sent to email", description="Reset confirmation")


class AuthPasswordResetConfirmRequest(BaseModel):
    """Schema for password reset confirmation request"""
    
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @field_validator('new_password')
    @classmethod
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


class AuthPasswordResetConfirmResponse(BaseModel):
    """Schema for password reset confirmation response"""
    
    message: str = Field(default="Password reset successfully", description="Reset confirmation")


class AuthMeResponse(BaseModel):
    """Schema for current user information response"""
    
    user: Dict[str, Any] = Field(..., description="Current user information")
    permissions: List[str] = Field(..., description="User permissions")
    session_info: Dict[str, Any] = Field(..., description="Session information")


class AuthPermissionCheckRequest(BaseModel):
    """Schema for permission check request"""
    
    permission: str = Field(..., description="Permission to check")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Hotel ID for hotel-specific permissions")


class AuthPermissionCheckResponse(BaseModel):
    """Schema for permission check response"""
    
    has_permission: bool = Field(..., description="Whether user has the permission")
    reason: Optional[str] = Field(None, description="Reason if permission is denied")


class AuthSessionInfo(BaseModel):
    """Schema for session information"""
    
    user_id: uuid.UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    username: str = Field(..., description="Username")
    role: UserRole = Field(..., description="User role")
    hotel_id: Optional[uuid.UUID] = Field(None, description="Associated hotel ID")
    permissions: List[str] = Field(..., description="User permissions")
    session_id: str = Field(..., description="Session ID")
    login_time: datetime = Field(..., description="Login timestamp")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    expires_at: datetime = Field(..., description="Session expiration time")


class AuthErrorResponse(BaseModel):
    """Schema for authentication error response"""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class AuthValidateTokenRequest(BaseModel):
    """Schema for token validation request"""
    
    token: str = Field(..., description="JWT token to validate")
    token_type: str = Field(default="access", description="Token type (access or refresh)")


class AuthValidateTokenResponse(BaseModel):
    """Schema for token validation response"""
    
    valid: bool = Field(..., description="Whether token is valid")
    user_id: Optional[uuid.UUID] = Field(None, description="User ID if token is valid")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")
    reason: Optional[str] = Field(None, description="Reason if token is invalid")
