"""
JWT token handling utilities for user authentication

This module provides specialized JWT token handling for user authentication,
including token creation, validation, and refresh functionality.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import structlog

from app.core.security import Security, TokenError, AuthenticationError

logger = structlog.get_logger(__name__)


class JWTHandler:
    """JWT token handler for user authentication"""
    
    @staticmethod
    def create_user_tokens(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create access and refresh tokens for user
        
        Args:
            user_data: User data to include in token
            
        Returns:
            Dict containing tokens and metadata
        """
        # Prepare token payload
        token_payload = {
            "sub": str(user_data["id"]),
            "email": user_data["email"],
            "username": user_data.get("username"),
            "role": user_data.get("role"),
            "hotel_id": str(user_data["hotel_id"]) if user_data.get("hotel_id") else None,
            "permissions": user_data.get("permissions", [])
        }
        
        # Create tokens
        access_token = Security.create_access_token(token_payload)
        refresh_token = Security.create_refresh_token({"sub": str(user_data["id"])})
        
        logger.info(
            "User tokens created",
            user_id=str(user_data["id"]),
            email=user_data["email"]
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 30 * 60,  # 30 minutes in seconds
            "user": {
                "id": str(user_data["id"]),
                "email": user_data["email"],
                "username": user_data.get("username"),
                "role": user_data.get("role"),
                "hotel_id": str(user_data["hotel_id"]) if user_data.get("hotel_id") else None
            }
        }
    
    @staticmethod
    def validate_access_token(token: str) -> Dict[str, Any]:
        """
        Validate access token and return payload
        
        Args:
            token: JWT access token
            
        Returns:
            Dict[str, Any]: Token payload
            
        Raises:
            TokenError: If token is invalid
        """
        try:
            payload = Security.verify_token(token, "access")
            
            # Validate required fields
            required_fields = ["sub", "email"]
            for field in required_fields:
                if field not in payload:
                    raise TokenError(f"Token missing required field: {field}")
            
            logger.debug(
                "Access token validated",
                user_id=payload["sub"],
                email=payload["email"]
            )
            
            return payload
            
        except TokenError as e:
            logger.warning("Access token validation failed", error=str(e))
            raise
    
    @staticmethod
    def validate_refresh_token(token: str) -> Dict[str, Any]:
        """
        Validate refresh token and return payload
        
        Args:
            token: JWT refresh token
            
        Returns:
            Dict[str, Any]: Token payload
            
        Raises:
            TokenError: If token is invalid
        """
        try:
            payload = Security.verify_token(token, "refresh")
            
            # Validate required fields
            if "sub" not in payload:
                raise TokenError("Refresh token missing user ID")
            
            logger.debug(
                "Refresh token validated",
                user_id=payload["sub"]
            )
            
            return payload
            
        except TokenError as e:
            logger.warning("Refresh token validation failed", error=str(e))
            raise
    
    @staticmethod
    def refresh_access_token(refresh_token: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            user_data: Current user data
            
        Returns:
            Dict containing new access token
            
        Raises:
            TokenError: If refresh token is invalid
            AuthenticationError: If user data is invalid
        """
        try:
            # Validate refresh token
            refresh_payload = JWTHandler.validate_refresh_token(refresh_token)
            
            # Verify user ID matches
            if str(user_data["id"]) != refresh_payload["sub"]:
                raise AuthenticationError("User ID mismatch in refresh token")
            
            # Create new access token
            token_payload = {
                "sub": str(user_data["id"]),
                "email": user_data["email"],
                "username": user_data.get("username"),
                "role": user_data.get("role"),
                "hotel_id": str(user_data["hotel_id"]) if user_data.get("hotel_id") else None,
                "permissions": user_data.get("permissions", [])
            }
            
            new_access_token = Security.create_access_token(token_payload)
            
            logger.info(
                "Access token refreshed",
                user_id=str(user_data["id"]),
                email=user_data["email"]
            )
            
            return {
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_in": 30 * 60  # 30 minutes in seconds
            }
            
        except TokenError as e:
            logger.warning("Token refresh failed", error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during token refresh", error=str(e))
            raise AuthenticationError("Token refresh failed")
    
    @staticmethod
    def extract_user_id_from_token(token: str) -> Optional[uuid.UUID]:
        """
        Extract user ID from token without full validation
        
        Args:
            token: JWT token
            
        Returns:
            Optional[uuid.UUID]: User ID if found
        """
        try:
            payload = JWTHandler.validate_access_token(token)
            user_id_str = payload.get("sub")
            if user_id_str:
                return uuid.UUID(user_id_str)
        except (TokenError, ValueError):
            pass
        
        return None
    
    @staticmethod
    def get_token_expiry(token: str) -> Optional[datetime]:
        """
        Get token expiry time
        
        Args:
            token: JWT token
            
        Returns:
            Optional[datetime]: Token expiry time
        """
        try:
            payload = Security.verify_token(token)
            exp = payload.get("exp")
            if exp:
                return datetime.fromtimestamp(exp)
        except TokenError:
            pass
        
        return None
    
    @staticmethod
    def is_token_expired(token: str) -> bool:
        """
        Check if token is expired
        
        Args:
            token: JWT token
            
        Returns:
            bool: True if token is expired
        """
        expiry = JWTHandler.get_token_expiry(token)
        if expiry:
            return datetime.utcnow() > expiry
        return True  # Consider invalid tokens as expired
