"""
Core security utilities for WhatsApp Hotel Bot application

This module provides JWT authentication, password hashing, and security utilities
for general user authentication (separate from admin authentication).
"""

import uuid
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


class SecurityError(Exception):
    """Base exception for security errors"""
    pass


class AuthenticationError(SecurityError):
    """Authentication failed"""
    pass


class AuthorizationError(SecurityError):
    """Authorization failed"""
    pass


class TokenError(SecurityError):
    """Token-related error"""
    pass


class Security:
    """Core security utilities for user authentication"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt
        
        Args:
            password: Plain text password
            
        Returns:
            str: Hashed password
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            bool: True if password matches
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_password_reset_token() -> str:
        """
        Generate a secure password reset token
        
        Returns:
            str: URL-safe token
        """
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
            "type": "access",
            "scope": "user"  # Distinguish from admin tokens
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
            "type": "refresh",
            "scope": "user"  # Distinguish from admin tokens
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
            TokenError: If token is invalid
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            
            # Check token type
            if payload.get("type") != token_type:
                raise TokenError(f"Invalid token type. Expected {token_type}")
            
            # Check scope (ensure it's a user token, not admin)
            if payload.get("scope") != "user":
                raise TokenError("Invalid token scope")
            
            # Check expiration
            exp = payload.get("exp")
            if exp is None:
                raise TokenError("Token missing expiration")
            
            if datetime.utcnow() > datetime.fromtimestamp(exp):
                raise TokenError("Token has expired")
            
            return payload
            
        except JWTError as e:
            logger.warning("JWT verification failed", error=str(e))
            raise TokenError(f"Invalid token: {str(e)}")
    
    @staticmethod
    def generate_session_id() -> str:
        """
        Generate a unique session ID
        
        Returns:
            str: URL-safe session ID
        """
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
