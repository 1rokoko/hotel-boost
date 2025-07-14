"""
Admin user management service
"""

import uuid
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload
import structlog

from app.models.admin_user import AdminUser, AdminRole, AdminPermission
from app.models.admin_audit_log import AuditAction, AuditSeverity
from app.schemas.admin_auth import (
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserSearchParams
)
from app.core.admin_security import AdminSecurity, AdminAuthenticationError
from app.utils.admin_audit import AdminAuditLogger
from app.database import get_db_session

logger = structlog.get_logger(__name__)


class AdminUserService:
    """
    Service for admin user management operations
    """
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        """
        Initialize admin user service
        
        Args:
            db_session: Database session (optional)
        """
        self.db_session = db_session
        self.audit_logger = AdminAuditLogger(db_session)
    
    async def list_users(
        self,
        search_params: AdminUserSearchParams,
        requesting_user: AdminUser
    ) -> Tuple[List[AdminUser], int]:
        """
        List admin users with filtering and pagination
        
        Args:
            search_params: Search and filter parameters
            requesting_user: User making the request
            
        Returns:
            Tuple of (users list, total count)
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Build base query
                query = select(AdminUser)
                count_query = select(func.count(AdminUser.id))
                
                # Apply filters based on user permissions
                conditions = []
                
                # Super admin can see all users
                if requesting_user.role != AdminRole.SUPER_ADMIN:
                    # Hotel admins can only see users from their hotel
                    if requesting_user.hotel_id:
                        conditions.append(AdminUser.hotel_id == requesting_user.hotel_id)
                    else:
                        # If user has no hotel association, they can't see other users
                        conditions.append(AdminUser.id == requesting_user.id)
                
                # Apply search filters
                if search_params.search:
                    search_term = f"%{search_params.search}%"
                    conditions.append(
                        or_(
                            AdminUser.username.ilike(search_term),
                            AdminUser.email.ilike(search_term),
                            AdminUser.full_name.ilike(search_term)
                        )
                    )
                
                if search_params.role:
                    conditions.append(AdminUser.role == search_params.role)
                
                if search_params.hotel_id:
                    conditions.append(AdminUser.hotel_id == search_params.hotel_id)
                
                if search_params.is_active is not None:
                    conditions.append(AdminUser.is_active == search_params.is_active)
                
                if search_params.is_verified is not None:
                    conditions.append(AdminUser.is_verified == search_params.is_verified)
                
                # Apply conditions
                if conditions:
                    query = query.where(and_(*conditions))
                    count_query = count_query.where(and_(*conditions))
                
                # Get total count
                total_result = await db.execute(count_query)
                total = total_result.scalar() or 0
                
                # Apply sorting
                if search_params.sort_by == "username":
                    sort_column = AdminUser.username
                elif search_params.sort_by == "email":
                    sort_column = AdminUser.email
                elif search_params.sort_by == "full_name":
                    sort_column = AdminUser.full_name
                elif search_params.sort_by == "role":
                    sort_column = AdminUser.role
                elif search_params.sort_by == "last_login":
                    sort_column = AdminUser.last_login
                else:
                    sort_column = AdminUser.created_at
                
                if search_params.sort_order == "desc":
                    query = query.order_by(desc(sort_column))
                else:
                    query = query.order_by(sort_column)
                
                # Apply pagination
                offset = (search_params.page - 1) * search_params.per_page
                query = query.offset(offset).limit(search_params.per_page)
                
                # Execute query
                result = await db.execute(query)
                users = result.scalars().all()
                
                return list(users), total
                
        except Exception as e:
            logger.error("Error listing admin users", error=str(e))
            raise
    
    async def get_user_by_id(
        self,
        user_id: uuid.UUID,
        requesting_user: AdminUser
    ) -> Optional[AdminUser]:
        """
        Get admin user by ID
        
        Args:
            user_id: User ID to retrieve
            requesting_user: User making the request
            
        Returns:
            AdminUser or None if not found/not accessible
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Get user
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    return None
                
                # Check access permissions
                if not self._can_access_user(requesting_user, user):
                    return None
                
                return user
                
        except Exception as e:
            logger.error("Error getting admin user by ID", error=str(e))
            return None
    
    async def create_user(
        self,
        user_data: AdminUserCreate,
        creating_user: AdminUser
    ) -> AdminUser:
        """
        Create new admin user
        
        Args:
            user_data: User creation data
            creating_user: User creating the new user
            
        Returns:
            Created AdminUser
            
        Raises:
            ValueError: If creation fails due to validation
        """
        try:
            # Validate permissions
            if not self._can_create_user(creating_user, user_data):
                raise ValueError("Insufficient permissions to create user")
            
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Check if username or email already exists
                existing_user = await self._check_user_exists(db, user_data.username, user_data.email)
                if existing_user:
                    raise ValueError("Username or email already exists")
                
                # Create new user
                new_user = AdminUser(
                    email=user_data.email.lower(),
                    username=user_data.username.lower(),
                    full_name=user_data.full_name,
                    role=user_data.role,
                    permissions=[p.value for p in user_data.permissions],
                    hotel_id=user_data.hotel_id,
                    is_active=user_data.is_active,
                    is_verified=False
                )
                
                # Set password
                new_user.set_password(user_data.password)
                
                # Add to database
                db.add(new_user)
                await db.commit()
                await db.refresh(new_user)
                
                # Log user creation
                await self.audit_logger.log_user_management(
                    admin_user_id=creating_user.id,
                    action=AuditAction.USER_CREATED,
                    target_user_id=new_user.id,
                    changes={
                        "new_values": {
                            "username": new_user.username,
                            "email": new_user.email,
                            "role": new_user.role.value,
                            "hotel_id": str(new_user.hotel_id) if new_user.hotel_id else None
                        }
                    }
                )
                
                logger.info(
                    "Admin user created",
                    created_user_id=str(new_user.id),
                    created_by=str(creating_user.id),
                    role=new_user.role.value
                )
                
                return new_user
                
        except ValueError:
            raise
        except Exception as e:
            logger.error("Error creating admin user", error=str(e))
            raise ValueError("Failed to create user")
    
    async def update_user(
        self,
        user_id: uuid.UUID,
        user_data: AdminUserUpdate,
        updating_user: AdminUser
    ) -> Optional[AdminUser]:
        """
        Update admin user
        
        Args:
            user_id: User ID to update
            user_data: Update data
            updating_user: User performing the update
            
        Returns:
            Updated AdminUser or None if not found
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Get existing user
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    return None
                
                # Check access permissions
                if not self._can_modify_user(updating_user, user):
                    raise ValueError("Insufficient permissions to update user")
                
                # Store old values for audit
                old_values = {
                    "email": user.email,
                    "username": user.username,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "permissions": user.permissions,
                    "hotel_id": str(user.hotel_id) if user.hotel_id else None,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified
                }
                
                # Update fields
                if user_data.email is not None:
                    user.email = user_data.email.lower()
                if user_data.username is not None:
                    user.username = user_data.username.lower()
                if user_data.full_name is not None:
                    user.full_name = user_data.full_name
                if user_data.role is not None:
                    user.role = user_data.role
                if user_data.permissions is not None:
                    user.permissions = [p.value for p in user_data.permissions]
                if user_data.hotel_id is not None:
                    user.hotel_id = user_data.hotel_id
                if user_data.is_active is not None:
                    user.is_active = user_data.is_active
                if user_data.is_verified is not None:
                    user.is_verified = user_data.is_verified
                
                await db.commit()
                await db.refresh(user)
                
                # Store new values for audit
                new_values = {
                    "email": user.email,
                    "username": user.username,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "permissions": user.permissions,
                    "hotel_id": str(user.hotel_id) if user.hotel_id else None,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified
                }
                
                # Log user update
                await self.audit_logger.log_user_management(
                    admin_user_id=updating_user.id,
                    action=AuditAction.USER_UPDATED,
                    target_user_id=user.id,
                    changes={
                        "old_values": old_values,
                        "new_values": new_values
                    }
                )
                
                logger.info(
                    "Admin user updated",
                    updated_user_id=str(user.id),
                    updated_by=str(updating_user.id)
                )
                
                return user
                
        except ValueError:
            raise
        except Exception as e:
            logger.error("Error updating admin user", error=str(e))
            raise ValueError("Failed to update user")
    
    def _can_access_user(self, requesting_user: AdminUser, target_user: AdminUser) -> bool:
        """Check if requesting user can access target user"""
        # Super admin can access all users
        if requesting_user.role == AdminRole.SUPER_ADMIN:
            return True
        
        # Users can access themselves
        if requesting_user.id == target_user.id:
            return True
        
        # Hotel admins can access users from their hotel
        if (requesting_user.role == AdminRole.HOTEL_ADMIN and 
            requesting_user.hotel_id and 
            requesting_user.hotel_id == target_user.hotel_id):
            return True
        
        return False
    
    def _can_create_user(self, creating_user: AdminUser, user_data: AdminUserCreate) -> bool:
        """Check if user can create new user with specified data"""
        # Super admin can create any user
        if creating_user.role == AdminRole.SUPER_ADMIN:
            return True
        
        # Hotel admins can create users for their hotel
        if (creating_user.role == AdminRole.HOTEL_ADMIN and 
            creating_user.hotel_id and 
            user_data.hotel_id == creating_user.hotel_id):
            # Can't create super admins or hotel admins
            if user_data.role in [AdminRole.SUPER_ADMIN, AdminRole.HOTEL_ADMIN]:
                return False
            return True
        
        return False
    
    def _can_modify_user(self, modifying_user: AdminUser, target_user: AdminUser) -> bool:
        """Check if user can modify target user"""
        # Super admin can modify any user
        if modifying_user.role == AdminRole.SUPER_ADMIN:
            return True
        
        # Users can modify themselves (limited)
        if modifying_user.id == target_user.id:
            return True
        
        # Hotel admins can modify users from their hotel
        if (modifying_user.role == AdminRole.HOTEL_ADMIN and 
            modifying_user.hotel_id and 
            modifying_user.hotel_id == target_user.hotel_id):
            # Can't modify super admins or other hotel admins
            if target_user.role in [AdminRole.SUPER_ADMIN, AdminRole.HOTEL_ADMIN]:
                return False
            return True
        
        return False

    async def delete_user(
        self,
        user_id: uuid.UUID,
        deleting_user: AdminUser
    ) -> bool:
        """
        Delete admin user

        Args:
            user_id: User ID to delete
            deleting_user: User performing the deletion

        Returns:
            bool: True if deleted successfully
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()

            async with session as db:
                # Get user to delete
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    return False

                # Check permissions
                if not self._can_modify_user(deleting_user, user):
                    raise ValueError("Insufficient permissions to delete user")

                # Can't delete yourself
                if user.id == deleting_user.id:
                    raise ValueError("Cannot delete your own account")

                # Store user info for audit
                user_info = {
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value,
                    "hotel_id": str(user.hotel_id) if user.hotel_id else None
                }

                # Delete user
                await db.delete(user)
                await db.commit()

                # Log user deletion
                await self.audit_logger.log_user_management(
                    admin_user_id=deleting_user.id,
                    action=AuditAction.USER_DELETED,
                    target_user_id=user_id,
                    changes={
                        "old_values": user_info
                    }
                )

                logger.info(
                    "Admin user deleted",
                    deleted_user_id=str(user_id),
                    deleted_by=str(deleting_user.id)
                )

                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error("Error deleting admin user", error=str(e))
            raise ValueError("Failed to delete user")

    async def activate_user(
        self,
        user_id: uuid.UUID,
        activating_user: AdminUser
    ) -> bool:
        """
        Activate admin user account

        Args:
            user_id: User ID to activate
            activating_user: User performing the activation

        Returns:
            bool: True if activated successfully
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()

            async with session as db:
                # Get user
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    return False

                # Check permissions
                if not self._can_modify_user(activating_user, user):
                    raise ValueError("Insufficient permissions to activate user")

                # Activate user
                user.is_active = True
                await db.commit()

                # Log activation
                await self.audit_logger.log_user_management(
                    admin_user_id=activating_user.id,
                    action=AuditAction.USER_ACTIVATED,
                    target_user_id=user.id
                )

                logger.info(
                    "Admin user activated",
                    activated_user_id=str(user.id),
                    activated_by=str(activating_user.id)
                )

                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error("Error activating admin user", error=str(e))
            return False

    async def deactivate_user(
        self,
        user_id: uuid.UUID,
        deactivating_user: AdminUser
    ) -> bool:
        """
        Deactivate admin user account

        Args:
            user_id: User ID to deactivate
            deactivating_user: User performing the deactivation

        Returns:
            bool: True if deactivated successfully
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()

            async with session as db:
                # Get user
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    return False

                # Check permissions
                if not self._can_modify_user(deactivating_user, user):
                    raise ValueError("Insufficient permissions to deactivate user")

                # Can't deactivate yourself
                if user.id == deactivating_user.id:
                    raise ValueError("Cannot deactivate your own account")

                # Deactivate user
                user.is_active = False
                await db.commit()

                # Log deactivation
                await self.audit_logger.log_user_management(
                    admin_user_id=deactivating_user.id,
                    action=AuditAction.USER_DEACTIVATED,
                    target_user_id=user.id
                )

                logger.info(
                    "Admin user deactivated",
                    deactivated_user_id=str(user.id),
                    deactivated_by=str(deactivating_user.id)
                )

                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error("Error deactivating admin user", error=str(e))
            return False

    async def unlock_user(
        self,
        user_id: uuid.UUID,
        unlocking_user: AdminUser
    ) -> bool:
        """
        Unlock admin user account

        Args:
            user_id: User ID to unlock
            unlocking_user: User performing the unlock

        Returns:
            bool: True if unlocked successfully
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()

            async with session as db:
                # Get user
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    return False

                # Check permissions
                if not self._can_modify_user(unlocking_user, user):
                    raise ValueError("Insufficient permissions to unlock user")

                # Unlock user
                user.unlock_account()
                await db.commit()

                # Log unlock
                await self.audit_logger.log_action(
                    admin_user_id=unlocking_user.id,
                    action=AuditAction.ACCOUNT_UNLOCKED,
                    description=f"Unlocked account for user {user.username}",
                    severity=AuditSeverity.MEDIUM,
                    target_type="admin_user",
                    target_id=str(user.id),
                    success=True
                )

                logger.info(
                    "Admin user unlocked",
                    unlocked_user_id=str(user.id),
                    unlocked_by=str(unlocking_user.id)
                )

                return True

        except ValueError:
            raise
        except Exception as e:
            logger.error("Error unlocking admin user", error=str(e))
            return False

    async def _check_user_exists(
        self,
        db: AsyncSession,
        username: str,
        email: str
    ) -> Optional[AdminUser]:
        """Check if user with username or email already exists"""
        stmt = select(AdminUser).where(
            or_(
                AdminUser.username == username.lower(),
                AdminUser.email == email.lower()
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


async def get_admin_user_service(db: AsyncSession = None) -> AdminUserService:
    """
    Dependency to get admin user service
    
    Args:
        db: Database session
        
    Returns:
        AdminUserService: Admin user service instance
    """
    return AdminUserService(db_session=db)
