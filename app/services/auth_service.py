"""
Authentication service for user management

This service handles user authentication, registration, and session management
for the general user system (separate from admin authentication).
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.core.security import Security, AuthenticationError, SecurityError
from app.utils.jwt_handler import JWTHandler
from app.models.user import User
from app.models.role import Role

logger = structlog.get_logger(__name__)


class AuthService:
    """Authentication service for user management"""
    
    def __init__(self, db: AsyncSession):
        """
        Initialize authentication service
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def authenticate_user(self, email: str, password: str) -> User:
        """
        Authenticate user with email and password
        
        Args:
            email: User email
            password: User password
            
        Returns:
            User: Authenticated user
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Find user by email
            stmt = select(User).where(User.email == email.lower())
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning("Authentication failed - user not found", email=email)
                raise AuthenticationError("Invalid email or password")
            
            # Check if user is active
            if not user.is_active:
                logger.warning("Authentication failed - user inactive", user_id=str(user.id))
                raise AuthenticationError("Account is deactivated")
            
            # Check if account is locked
            if user.is_locked:
                logger.warning("Authentication failed - account locked", user_id=str(user.id))
                raise AuthenticationError("Account is locked")
            
            # Verify password
            if not user.verify_password(password):
                # Increment failed login attempts
                await self._handle_failed_login(user)
                logger.warning("Authentication failed - invalid password", user_id=str(user.id))
                raise AuthenticationError("Invalid email or password")
            
            # Reset failed login attempts on successful login
            await self._handle_successful_login(user)
            
            logger.info("User authenticated successfully", user_id=str(user.id), email=email)
            return user
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error("Unexpected error during authentication", error=str(e))
            raise AuthenticationError("Authentication failed")
    
    async def create_access_token(self, user: User) -> Dict[str, Any]:
        """
        Create access token for user
        
        Args:
            user: User instance
            
        Returns:
            Dict containing token information
        """
        user_data = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role.value if user.role else None,
            "hotel_id": user.hotel_id,
            "permissions": user.permissions
        }
        
        tokens = JWTHandler.create_user_tokens(user_data)
        
        logger.info("Access token created", user_id=str(user.id))
        return tokens
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Dict containing new access token
            
        Raises:
            AuthenticationError: If refresh fails
        """
        try:
            # Validate refresh token
            refresh_payload = JWTHandler.validate_refresh_token(refresh_token)
            user_id = uuid.UUID(refresh_payload["sub"])
            
            # Get current user data
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning("Token refresh failed - user not found", user_id=str(user_id))
                raise AuthenticationError("User not found")
            
            if not user.is_active:
                logger.warning("Token refresh failed - user inactive", user_id=str(user_id))
                raise AuthenticationError("Account is deactivated")
            
            # Create new access token
            user_data = {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role.value if user.role else None,
                "hotel_id": user.hotel_id,
                "permissions": user.permissions
            }
            
            new_token = JWTHandler.refresh_access_token(refresh_token, user_data)
            
            logger.info("Token refreshed successfully", user_id=str(user_id))
            return new_token
            
        except Exception as e:
            logger.error("Token refresh failed", error=str(e))
            raise AuthenticationError("Token refresh failed")
    
    async def register_user(
        self,
        email: str,
        password: str,
        username: str,
        full_name: str,
        role: str = "viewer",
        hotel_id: Optional[uuid.UUID] = None
    ) -> User:
        """
        Register new user
        
        Args:
            email: User email
            password: User password
            username: Username
            full_name: User full name
            role: User role (default: viewer)
            hotel_id: Associated hotel ID
            
        Returns:
            User: Created user
            
        Raises:
            AuthenticationError: If registration fails
        """
        try:
            # Check if email already exists
            stmt = select(User).where(User.email == email.lower())
            result = await self.db.execute(stmt)
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                raise AuthenticationError("Email already registered")
            
            # Check if username already exists
            stmt = select(User).where(User.username == username)
            result = await self.db.execute(stmt)
            existing_username = result.scalar_one_or_none()
            
            if existing_username:
                raise AuthenticationError("Username already taken")
            
            # Validate password strength
            is_strong, issues = Security.is_strong_password(password)
            if not is_strong:
                raise AuthenticationError(f"Password requirements not met: {', '.join(issues)}")
            
            # Create new user
            user = User(
                email=email.lower(),
                username=username,
                full_name=full_name,
                role=role,
                hotel_id=hotel_id
            )
            user.set_password(password)
            
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            
            logger.info("User registered successfully", user_id=str(user.id), email=email)
            return user
            
        except AuthenticationError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error("User registration failed", error=str(e))
            raise AuthenticationError("Registration failed")
    
    async def _handle_failed_login(self, user: User) -> None:
        """Handle failed login attempt"""
        try:
            failed_attempts = int(user.failed_login_attempts) + 1
            user.failed_login_attempts = str(failed_attempts)
            
            # Lock account after 5 failed attempts
            if failed_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
                logger.warning("Account locked due to failed attempts", user_id=str(user.id))
            
            await self.db.commit()
            
        except Exception as e:
            logger.error("Error handling failed login", error=str(e))
    
    async def _handle_successful_login(self, user: User) -> None:
        """Handle successful login"""
        try:
            user.failed_login_attempts = "0"
            user.locked_until = None
            user.last_login = datetime.utcnow()
            
            await self.db.commit()
            
        except Exception as e:
            logger.error("Error handling successful login", error=str(e))
    
    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Get user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            Optional[User]: User if found
        """
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Error getting user by ID", error=str(e))
            return None
