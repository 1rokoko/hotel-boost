"""
Admin authentication endpoints for WhatsApp Hotel Bot
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.schemas.admin_auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminTokenRefreshRequest,
    AdminTokenRefreshResponse,
    AdminPasswordChangeRequest,
    AdminPasswordResetRequest,
    AdminPasswordResetConfirm,
    AdminUserResponse,
    AdminSessionInfo
)
from app.services.admin_auth_service import (
    AdminAuthService,
    AdminAuthenticationError,
    AdminAuthorizationError
)
from app.core.admin_security import AdminSecurity, AdminTokenError
from app.models.admin_audit_log import AuditAction, AuditSeverity
from app.utils.admin_audit import AdminAuditLogger

logger = structlog.get_logger(__name__)
security = HTTPBearer()

router = APIRouter()


async def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated admin user from JWT token
    
    Args:
        credentials: HTTP Bearer credentials
        db: Database session
        auth_service: Admin authentication service
        
    Returns:
        AdminUser: Current authenticated admin user
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        auth_service = authService(db)
        # Verify token
        token_payload = AdminSecurity.verify_token(credentials.credentials, "access")
        user_id = uuid.UUID(token_payload["sub"])
        
        # Get user from database
        admin_user = await auth_service.get_admin_user_by_id(user_id)
        if not admin_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Check if user is active
        if not admin_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated"
            )
        
        # Check if user is locked
        if admin_user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is locked"
            )
        
        return admin_user
        
    except AdminTokenError as e:
        logger.warning("Token verification failed", error=str(e))
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


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    request: Request,
    login_data: AdminLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Admin user login
    
    Authenticates admin user and returns JWT tokens.
    """
    try:
        audit_logger = AdminAuditLogger(db)
        auth_service = AdminAuthService(db)

        # Authenticate user
        admin_user = auth_service.authenticate_user(
            login_data.username,
            login_data.password
        )
        
        # Create tokens
        tokens = AdminSecurity.create_admin_tokens(admin_user)
        
        # Update last login
        await auth_service.update_last_login(admin_user.id)
        
        # Log successful login
        await audit_logger.log_action(
            admin_user_id=admin_user.id,
            action=AuditAction.LOGIN,
            description=f"Admin user {admin_user.username} logged in successfully",
            severity=AuditSeverity.LOW,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            success=True
        )
        
        logger.info(
            "Admin user logged in successfully",
            user_id=str(admin_user.id),
            username=admin_user.username,
            ip_address=request.client.host
        )
        
        return AdminLoginResponse(**tokens)
        
    except AdminAuthenticationError as e:
        # Log failed login attempt
        await audit_logger.log_action(
            admin_user_id=None,
            action=AuditAction.LOGIN_FAILED,
            description=f"Failed login attempt for username: {login_data.username}",
            severity=AuditSeverity.MEDIUM,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            success=False,
            error_message=str(e)
        )
        
        logger.warning(
            "Admin login failed",
            username=login_data.username,
            error=str(e),
            ip_address=request.client.host
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    except Exception as e:
        logger.error("Login error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=AdminTokenRefreshResponse)
async def refresh_token(
    refresh_data: AdminTokenRefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    """
    try:
        # Verify refresh token
        token_payload = AdminSecurity.verify_token(refresh_data.refresh_token, "refresh")
        user_id = uuid.UUID(token_payload["sub"])
        
        # Get user from database
        admin_user = await auth_service.get_admin_user_by_id(user_id)
        if not admin_user or not admin_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Create new access token
        token_data = {
            "sub": str(admin_user.id),
            "username": admin_user.username,
            "email": admin_user.email,
            "role": admin_user.role.value,
            "hotel_id": str(admin_user.hotel_id) if admin_user.hotel_id else None,
            "permissions": admin_user.permissions
        }
        
        access_token = AdminSecurity.create_access_token(token_data)
        
        return AdminTokenRefreshResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=30 * 60  # 30 minutes
        )
        
    except AdminTokenError as e:
        logger.warning("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    except Exception as e:
        logger.error("Token refresh error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout")
async def admin_logout(
    request: Request,
    current_user = Depends(get_current_admin_user)
):
    """
    Admin user logout
    
    Note: In a stateless JWT system, logout is primarily for logging purposes.
    In production, you might want to implement token blacklisting.
    """
    try:
        # Log logout
        await audit_logger.log_action(
            admin_user_id=current_user.id,
            action=AuditAction.LOGOUT,
            description=f"Admin user {current_user.username} logged out",
            severity=AuditSeverity.LOW,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            success=True
        )
        
        logger.info(
            "Admin user logged out",
            user_id=str(current_user.id),
            username=current_user.username
        )
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error("Logout error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/me", response_model=AdminUserResponse)
def get_current_user_info(
    current_user = Depends(get_current_admin_user)
):
    """
    Get current admin user information
    """
    return AdminUserResponse.model_validate(current_user)


@router.get("/session", response_model=AdminSessionInfo)
def get_session_info(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user = Depends(get_current_admin_user)
):
    """
    Get current session information
    """
    try:
        # Verify token to get expiration
        token_payload = AdminSecurity.verify_token(credentials.credentials, "access")
        expires_at = datetime.fromtimestamp(token_payload["exp"])
        
        return AdminSessionInfo(
            user_id=current_user.id,
            username=current_user.username,
            role=current_user.role,
            permissions=current_user.permissions,
            hotel_id=current_user.hotel_id,
            session_id=AdminSecurity.generate_session_id(),
            expires_at=expires_at
        )
        
    except Exception as e:
        logger.error("Session info error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session info"
        )


@router.post("/change-password")
async def change_password(
    request: Request,
    password_data: AdminPasswordChangeRequest,
    current_user = Depends(get_current_admin_user)
):
    """
    Change admin user password
    """
    try:
        # Change password
        await auth_service.change_password(
            current_user.id,
            password_data.current_password,
            password_data.new_password
        )
        
        # Log password change
        await audit_logger.log_action(
            admin_user_id=current_user.id,
            action=AuditAction.PASSWORD_CHANGED,
            description=f"Admin user {current_user.username} changed password",
            severity=AuditSeverity.MEDIUM,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            success=True
        )
        
        logger.info(
            "Admin user changed password",
            user_id=str(current_user.id),
            username=current_user.username
        )
        
        return {"message": "Password changed successfully"}
        
    except AdminAuthenticationError as e:
        logger.warning("Password change failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Password change error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )
