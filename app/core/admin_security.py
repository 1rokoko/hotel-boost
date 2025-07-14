"""
Admin security utilities for WhatsApp Hotel Bot application
"""

import uuid
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
import structlog

from app.core.config import settings
from app.models.admin_user import AdminUser, AdminRole, AdminPermission

logger = structlog.get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class AdminSecurityError(Exception):
    """Base exception for admin security errors"""
    pass


class AdminAuthenticationError(AdminSecurityError):
    """Authentication failed"""
    pass


class AdminAuthorizationError(AdminSecurityError):
    """Authorization failed"""
    pass


class AdminTokenError(AdminSecurityError):
    """Token-related error"""
    pass


class AdminSecurity:
    """Admin security utilities"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_password_reset_token() -> str:
        """Generate a secure password reset token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token
        
        Args:
            data: Token payload data
            expires_delta: Token expiration time
            
        Returns:
            str: JWT token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT refresh token
        
        Args:
            data: Token payload data
            expires_delta: Token expiration time
            
        Returns:
            str: JWT refresh token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token to verify
            token_type: Expected token type (access or refresh)
            
        Returns:
            Dict[str, Any]: Token payload
            
        Raises:
            AdminTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            
            # Check token type
            if payload.get("type") != token_type:
                raise AdminTokenError(f"Invalid token type. Expected {token_type}")
            
            # Check expiration
            exp = payload.get("exp")
            if exp is None:
                raise AdminTokenError("Token missing expiration")
            
            if datetime.utcnow() > datetime.fromtimestamp(exp):
                raise AdminTokenError("Token has expired")
            
            return payload
            
        except JWTError as e:
            logger.warning("JWT verification failed", error=str(e))
            raise AdminTokenError(f"Invalid token: {str(e)}")
    
    @staticmethod
    def create_admin_tokens(admin_user: AdminUser) -> Dict[str, Any]:
        """
        Create access and refresh tokens for admin user
        
        Args:
            admin_user: Admin user instance
            
        Returns:
            Dict containing tokens and user info
        """
        # Token payload
        token_data = {
            "sub": str(admin_user.id),
            "username": admin_user.username,
            "email": admin_user.email,
            "role": admin_user.role.value,
            "hotel_id": str(admin_user.hotel_id) if admin_user.hotel_id else None,
            "permissions": admin_user.permissions
        }
        
        # Create tokens
        access_token = AdminSecurity.create_access_token(token_data)
        refresh_token = AdminSecurity.create_refresh_token({"sub": str(admin_user.id)})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": admin_user.to_dict()
        }
    
    @staticmethod
    def check_permission(
        user_permissions: list,
        user_role: AdminRole,
        required_permission: AdminPermission,
        hotel_id: Optional[uuid.UUID] = None,
        user_hotel_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Check if user has required permission
        
        Args:
            user_permissions: User's permissions list
            user_role: User's role
            required_permission: Required permission
            hotel_id: Hotel ID being accessed (if applicable)
            user_hotel_id: User's associated hotel ID
            
        Returns:
            bool: True if user has permission
        """
        # Super admin has all permissions
        if user_role == AdminRole.SUPER_ADMIN:
            return True
        
        # Check explicit permission
        if required_permission.value not in user_permissions:
            return False
        
        # Check hotel access for hotel-specific operations
        if hotel_id is not None and user_hotel_id is not None:
            if hotel_id != user_hotel_id:
                return False
        
        return True
    
    @staticmethod
    def validate_admin_access(
        admin_user: AdminUser,
        required_permission: AdminPermission,
        target_hotel_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Validate admin user access for specific operation
        
        Args:
            admin_user: Admin user instance
            required_permission: Required permission
            target_hotel_id: Target hotel ID (if applicable)
            
        Returns:
            bool: True if access is allowed
            
        Raises:
            AdminAuthorizationError: If access is denied
        """
        # Check if account is active
        if not admin_user.is_active:
            raise AdminAuthorizationError("Account is deactivated")
        
        # Check if account is locked
        if admin_user.is_locked:
            raise AdminAuthorizationError("Account is locked")
        
        # Check permission
        has_permission = AdminSecurity.check_permission(
            user_permissions=admin_user.permissions,
            user_role=admin_user.role,
            required_permission=required_permission,
            hotel_id=target_hotel_id,
            user_hotel_id=admin_user.hotel_id
        )
        
        if not has_permission:
            raise AdminAuthorizationError(
                f"Insufficient permissions. Required: {required_permission.value}"
            )
        
        return True
    
    @staticmethod
    def get_permission_description(permission: AdminPermission) -> str:
        """Get human-readable permission description"""
        descriptions = {
            AdminPermission.MANAGE_SYSTEM: "Manage system-wide settings and configuration",
            AdminPermission.VIEW_SYSTEM_METRICS: "View system-wide metrics and performance data",
            AdminPermission.MANAGE_HOTELS: "Create, update, and delete hotels",
            AdminPermission.MANAGE_HOTEL_SETTINGS: "Manage hotel-specific settings and configuration",
            AdminPermission.VIEW_HOTEL_ANALYTICS: "View hotel analytics and statistics",
            AdminPermission.MANAGE_HOTEL_USERS: "Manage hotel staff and user accounts",
            AdminPermission.MANAGE_TRIGGERS: "Create and manage automated triggers",
            AdminPermission.VIEW_CONVERSATIONS: "View guest conversations and message history",
            AdminPermission.SEND_MESSAGES: "Send messages to guests",
            AdminPermission.MANAGE_TEMPLATES: "Create and manage message templates",
            AdminPermission.VIEW_ANALYTICS: "View analytics and reports",
            AdminPermission.EXPORT_DATA: "Export data and generate reports",
            AdminPermission.GENERATE_REPORTS: "Generate custom reports",
            AdminPermission.VIEW_MONITORING: "View system monitoring and health status",
            AdminPermission.MANAGE_ALERTS: "Manage alerts and notifications"
        }
        return descriptions.get(permission, permission.value)
    
    @staticmethod
    def get_role_description(role: AdminRole) -> str:
        """Get human-readable role description"""
        descriptions = {
            AdminRole.SUPER_ADMIN: "Full system access with all permissions",
            AdminRole.HOTEL_ADMIN: "Hotel administrator with management permissions",
            AdminRole.HOTEL_STAFF: "Hotel staff member with operational permissions",
            AdminRole.VIEWER: "Read-only access to hotel data and analytics"
        }
        return descriptions.get(role, role.value)
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session ID"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def is_strong_password(password: str) -> tuple[bool, list[str]]:
        """
        Check if password meets strength requirements
        
        Args:
            password: Password to check
            
        Returns:
            Tuple of (is_strong, list_of_issues)
        """
        issues = []
        
        if len(password) < 8:
            issues.append("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            issues.append("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            issues.append("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            issues.append("Password must contain at least one digit")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            issues.append("Password should contain at least one special character")
        
        return len(issues) == 0, issues
