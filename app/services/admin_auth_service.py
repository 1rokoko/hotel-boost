"""
Admin authentication service for WhatsApp Hotel Bot
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
import structlog

from app.models.admin_user import AdminUser, AdminRole, AdminPermission
from app.models.admin_audit_log import AdminAuditLog, AuditAction, AuditSeverity
from app.core.admin_security import AdminSecurity, AdminAuthenticationError, AdminAuthorizationError
from app.database import get_db_session

logger = structlog.get_logger(__name__)


class AdminAuthService:
    """
    Service for admin authentication and user management
    """
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        """
        Initialize admin auth service
        
        Args:
            db_session: Database session (optional)
        """
        self.db_session = db_session
    
    async def authenticate_user(self, username: str, password: str) -> AdminUser:
        """
        Authenticate admin user with username/email and password
        
        Args:
            username: Username or email
            password: Password
            
        Returns:
            AdminUser: Authenticated admin user
            
        Raises:
            AdminAuthenticationError: If authentication fails
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Find user by username or email
                stmt = select(AdminUser).where(
                    and_(
                        or_(
                            AdminUser.username == username.lower(),
                            AdminUser.email == username.lower()
                        ),
                        AdminUser.is_active == True
                    )
                )
                result = await db.execute(stmt)
                admin_user = result.scalar_one_or_none()
                
                if not admin_user:
                    logger.warning("Authentication failed - user not found", username=username)
                    raise AdminAuthenticationError("Invalid credentials")
                
                # Check if account is locked
                if admin_user.is_locked:
                    logger.warning("Authentication failed - account locked", user_id=str(admin_user.id))
                    raise AdminAuthenticationError("Account is locked")
                
                # Verify password
                if not admin_user.verify_password(password):
                    # Increment failed login attempts
                    admin_user.increment_failed_login()
                    await db.commit()
                    
                    logger.warning(
                        "Authentication failed - invalid password",
                        user_id=str(admin_user.id),
                        failed_attempts=admin_user.failed_login_attempts
                    )
                    raise AdminAuthenticationError("Invalid credentials")
                
                # Update last login
                admin_user.update_last_login()
                await db.commit()
                await db.refresh(admin_user)
                
                logger.info(
                    "Admin user authenticated successfully",
                    user_id=str(admin_user.id),
                    username=admin_user.username
                )
                
                return admin_user
                
        except AdminAuthenticationError:
            raise
        except Exception as e:
            logger.error("Authentication error", error=str(e))
            raise AdminAuthenticationError("Authentication failed")
    
    async def get_admin_user_by_id(self, user_id: uuid.UUID) -> Optional[AdminUser]:
        """
        Get admin user by ID
        
        Args:
            user_id: Admin user ID
            
        Returns:
            AdminUser: Admin user or None if not found
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                return result.scalar_one_or_none()
                
        except Exception as e:
            logger.error("Error getting admin user by ID", error=str(e), user_id=str(user_id))
            return None
    
    async def get_admin_user_by_username(self, username: str) -> Optional[AdminUser]:
        """
        Get admin user by username
        
        Args:
            username: Username
            
        Returns:
            AdminUser: Admin user or None if not found
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                stmt = select(AdminUser).where(AdminUser.username == username.lower())
                result = await db.execute(stmt)
                return result.scalar_one_or_none()
                
        except Exception as e:
            logger.error("Error getting admin user by username", error=str(e), username=username)
            return None
    
    async def get_admin_user_by_email(self, email: str) -> Optional[AdminUser]:
        """
        Get admin user by email
        
        Args:
            email: Email address
            
        Returns:
            AdminUser: Admin user or None if not found
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                stmt = select(AdminUser).where(AdminUser.email == email.lower())
                result = await db.execute(stmt)
                return result.scalar_one_or_none()
                
        except Exception as e:
            logger.error("Error getting admin user by email", error=str(e), email=email)
            return None
    
    async def create_admin_user(
        self,
        email: str,
        username: str,
        full_name: str,
        password: str,
        role: AdminRole = AdminRole.VIEWER,
        permissions: Optional[List[AdminPermission]] = None,
        hotel_id: Optional[uuid.UUID] = None,
        is_active: bool = True
    ) -> AdminUser:
        """
        Create new admin user
        
        Args:
            email: Email address
            username: Username
            full_name: Full name
            password: Password
            role: User role
            permissions: Specific permissions
            hotel_id: Associated hotel ID
            is_active: Whether user is active
            
        Returns:
            AdminUser: Created admin user
            
        Raises:
            AdminAuthenticationError: If user creation fails
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Check if username or email already exists
                existing_user = await self._check_user_exists(db, username, email)
                if existing_user:
                    raise AdminAuthenticationError("Username or email already exists")
                
                # Create new admin user
                admin_user = AdminUser(
                    email=email.lower(),
                    username=username.lower(),
                    full_name=full_name,
                    role=role,
                    permissions=[p.value for p in permissions] if permissions else [],
                    hotel_id=hotel_id,
                    is_active=is_active,
                    is_verified=False
                )
                
                # Set password
                admin_user.set_password(password)
                
                # Add to database
                db.add(admin_user)
                await db.commit()
                await db.refresh(admin_user)
                
                logger.info(
                    "Admin user created successfully",
                    user_id=str(admin_user.id),
                    username=admin_user.username,
                    role=admin_user.role.value
                )
                
                return admin_user
                
        except AdminAuthenticationError:
            raise
        except Exception as e:
            logger.error("Error creating admin user", error=str(e))
            raise AdminAuthenticationError("Failed to create user")
    
    async def update_last_login(self, user_id: uuid.UUID) -> None:
        """
        Update last login timestamp for user
        
        Args:
            user_id: Admin user ID
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                admin_user = result.scalar_one_or_none()
                
                if admin_user:
                    admin_user.update_last_login()
                    await db.commit()
                    
        except Exception as e:
            logger.error("Error updating last login", error=str(e), user_id=str(user_id))
    
    async def change_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str
    ) -> None:
        """
        Change user password
        
        Args:
            user_id: Admin user ID
            current_password: Current password
            new_password: New password
            
        Raises:
            AdminAuthenticationError: If password change fails
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                admin_user = result.scalar_one_or_none()
                
                if not admin_user:
                    raise AdminAuthenticationError("User not found")
                
                # Verify current password
                if not admin_user.verify_password(current_password):
                    raise AdminAuthenticationError("Current password is incorrect")
                
                # Set new password
                admin_user.set_password(new_password)
                await db.commit()
                
                logger.info(
                    "Admin user password changed",
                    user_id=str(admin_user.id),
                    username=admin_user.username
                )
                
        except AdminAuthenticationError:
            raise
        except Exception as e:
            logger.error("Error changing password", error=str(e), user_id=str(user_id))
            raise AdminAuthenticationError("Failed to change password")
    
    async def unlock_user_account(self, user_id: uuid.UUID) -> None:
        """
        Unlock user account
        
        Args:
            user_id: Admin user ID
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                admin_user = result.scalar_one_or_none()
                
                if admin_user:
                    admin_user.unlock_account()
                    await db.commit()
                    
                    logger.info(
                        "Admin user account unlocked",
                        user_id=str(admin_user.id),
                        username=admin_user.username
                    )
                    
        except Exception as e:
            logger.error("Error unlocking user account", error=str(e), user_id=str(user_id))
    
    async def _check_user_exists(
        self,
        db: AsyncSession,
        username: str,
        email: str
    ) -> Optional[AdminUser]:
        """
        Check if user with username or email already exists
        
        Args:
            db: Database session
            username: Username to check
            email: Email to check
            
        Returns:
            AdminUser: Existing user or None
        """
        stmt = select(AdminUser).where(
            or_(
                AdminUser.username == username.lower(),
                AdminUser.email == email.lower()
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


async def get_admin_auth_service(db: AsyncSession = None) -> AdminAuthService:
    """
    Dependency to get admin auth service
    
    Args:
        db: Database session
        
    Returns:
        AdminAuthService: Admin auth service instance
    """
    return AdminAuthService(db_session=db)
