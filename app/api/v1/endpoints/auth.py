"""
Authentication endpoints for user authentication

This module provides REST API endpoints for user authentication, registration,
and session management.
"""

import uuid
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.auth_service import AuthService
from app.schemas.auth_api import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthTokenRefreshRequest,
    AuthTokenRefreshResponse,
    AuthLogoutRequest,
    AuthLogoutResponse,
    AuthRegisterRequest,
    AuthRegisterResponse,
    AuthPasswordChangeRequest,
    AuthPasswordChangeResponse,
    AuthPasswordResetRequest,
    AuthPasswordResetResponse,
    AuthPasswordResetConfirmRequest,
    AuthPasswordResetConfirmResponse,
    AuthMeResponse,
    AuthPermissionCheckRequest,
    AuthPermissionCheckResponse,
    AuthValidateTokenRequest,
    AuthValidateTokenResponse,
    AuthErrorResponse
)
from app.utils.permission_checker import PermissionChecker, require_permission
from app.models.role import UserPermission
from app.core.security import Security, AuthenticationError, TokenError
from app.utils.jwt_handler import JWTHandler
from app.models.user import User

logger = structlog.get_logger(__name__)
security = HTTPBearer()

router = APIRouter()


async def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Get authentication service instance"""
    return AuthService(db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Get current authenticated user from JWT token
    
    Args:
        credentials: HTTP Bearer credentials
        auth_service: Authentication service
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        auth_service = authService(db)
        # Validate access token
        token_payload = JWTHandler.validate_access_token(credentials.credentials)
        user_id = uuid.UUID(token_payload["sub"])
        
        # Get user from database
        user = await auth_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated"
            )
        
        return user
        
    except TokenError as e:
        logger.warning("Token validation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    except Exception as e:
        logger.error("Authentication error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


@router.post("/login", response_model=AuthLoginResponse)
async def login(
    request: AuthLoginRequest
):
    """
    Authenticate user and return access token
    
    Args:
        request: Login request data
        auth_service: Authentication service
        
    Returns:
        AuthLoginResponse: Login response with tokens
    """
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(request.email, request.password)
        
        # Create tokens
        tokens = await auth_service.create_access_token(user)
        
        # Add session ID
        session_id = Security.generate_session_id()
        tokens["session_id"] = session_id
        
        logger.info("User logged in successfully", user_id=str(user.id), email=request.email)
        
        return AuthLoginResponse(**tokens)
        
    except AuthenticationError as e:
        logger.warning("Login failed", email=request.email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Login error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=AuthTokenRefreshResponse)
async def refresh_token(
    request: AuthTokenRefreshRequest
):
    """
    Refresh access token using refresh token
    
    Args:
        request: Token refresh request
        auth_service: Authentication service
        
    Returns:
        AuthTokenRefreshResponse: New access token
    """
    try:
        # Refresh token
        new_token = await auth_service.refresh_token(request.refresh_token)
        
        logger.info("Token refreshed successfully")
        
        return AuthTokenRefreshResponse(**new_token)
        
    except AuthenticationError as e:
        logger.warning("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Token refresh error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout", response_model=AuthLogoutResponse)
def logout(
    request: AuthLogoutRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Logout user and invalidate tokens
    
    Args:
        request: Logout request
        current_user: Current authenticated user
        
    Returns:
        AuthLogoutResponse: Logout confirmation
    """
    try:
        # In a production system, you would invalidate the refresh token
        # For now, we'll just log the logout
        
        logger.info("User logged out", user_id=str(current_user.id))
        
        return AuthLogoutResponse(message="Successfully logged out")
        
    except Exception as e:
        logger.error("Logout error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post("/register", response_model=AuthRegisterResponse)
async def register(
    request: AuthRegisterRequest
):
    """
    Register new user
    
    Args:
        request: Registration request data
        auth_service: Authentication service
        
    Returns:
        AuthRegisterResponse: Registration confirmation
    """
    try:
        # Register user
        user = await auth_service.register_user(
            email=request.email,
            password=request.password,
            username=request.username,
            full_name=request.full_name,
            role=request.role.value,
            hotel_id=request.hotel_id
        )
        
        logger.info("User registered successfully", user_id=str(user.id), email=request.email)
        
        return AuthRegisterResponse(
            user=user.to_dict(),
            message="User registered successfully"
        )
        
    except AuthenticationError as e:
        logger.warning("Registration failed", email=request.email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Registration error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.get("/me", response_model=AuthMeResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        AuthMeResponse: Current user information
    """
    try:
        user_dict = current_user.to_dict()
        permissions = current_user.get_all_permissions()
        
        session_info = {
            "user_id": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role.value,
            "hotel_id": str(current_user.hotel_id) if current_user.hotel_id else None,
            "last_login": current_user.last_login.isoformat() if current_user.last_login else None
        }
        
        return AuthMeResponse(
            user=user_dict,
            permissions=permissions,
            session_info=session_info
        )
        
    except Exception as e:
        logger.error("Get user info error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )


@router.post("/check-permission", response_model=AuthPermissionCheckResponse)
def check_permission(
    request: AuthPermissionCheckRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Check if current user has specific permission

    Args:
        request: Permission check request
        current_user: Current authenticated user

    Returns:
        AuthPermissionCheckResponse: Permission check result
    """
    try:
        # Validate permission
        try:
            permission = UserPermission(request.permission)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission: {request.permission}"
            )

        # Check permission
        has_permission = PermissionChecker.check_permission(
            user=current_user,
            required_permission=permission,
            hotel_id=request.hotel_id
        )

        reason = None
        if not has_permission:
            if current_user.role.value != "super_admin" and permission.value not in current_user.get_all_permissions():
                reason = f"User does not have permission: {permission.value}"
            elif request.hotel_id and current_user.hotel_id and request.hotel_id != current_user.hotel_id:
                reason = "User cannot access this hotel"

        return AuthPermissionCheckResponse(
            has_permission=has_permission,
            reason=reason
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Permission check error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Permission check failed"
        )


@router.get("/permissions", response_model=Dict[str, Any])
def get_user_permissions(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's permissions summary

    Args:
        current_user: Current authenticated user

    Returns:
        Dict: User permissions summary
    """
    try:
        permissions_summary = PermissionChecker.get_user_permissions_summary(current_user)
        return permissions_summary

    except Exception as e:
        logger.error("Get permissions error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user permissions"
        )


@router.post("/validate-token", response_model=AuthValidateTokenResponse)
def validate_token(
    request: AuthValidateTokenRequest
):
    """
    Validate JWT token

    Args:
        request: Token validation request

    Returns:
        AuthValidateTokenResponse: Token validation result
    """
    try:
        # Validate token
        if request.token_type == "access":
            payload = JWTHandler.validate_access_token(request.token)
        elif request.token_type == "refresh":
            payload = JWTHandler.validate_refresh_token(request.token)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token type"
            )

        user_id = uuid.UUID(payload["sub"])
        expires_at = JWTHandler.get_token_expiry(request.token)

        return AuthValidateTokenResponse(
            valid=True,
            user_id=user_id,
            expires_at=expires_at
        )

    except TokenError as e:
        return AuthValidateTokenResponse(
            valid=False,
            reason=str(e)
        )
    except Exception as e:
        logger.error("Token validation error", error=str(e))
        return AuthValidateTokenResponse(
            valid=False,
            reason="Token validation failed"
        )
