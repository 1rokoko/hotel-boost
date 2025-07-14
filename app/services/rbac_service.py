"""
Role-Based Access Control (RBAC) service

This service provides role and permission management functionality
for the user authentication system.
"""

import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
import structlog

from app.models.user import User
from app.models.role import Role, UserRole, UserPermission
from app.core.security import AuthorizationError

logger = structlog.get_logger(__name__)


class RBACService:
    """Role-Based Access Control service"""
    
    def __init__(self, db: AsyncSession):
        """
        Initialize RBAC service
        
        Args:
            db: Database session
        """
        self.db = db
    
    async def create_role(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        is_system_role: bool = False
    ) -> Role:
        """
        Create a new role
        
        Args:
            name: Role name
            display_name: Human-readable role name
            description: Role description
            permissions: List of permissions
            is_system_role: Whether this is a system role
            
        Returns:
            Role: Created role
            
        Raises:
            ValueError: If role already exists or invalid data
        """
        try:
            # Check if role already exists
            stmt = select(Role).where(Role.name == name.lower())
            result = await self.db.execute(stmt)
            existing_role = result.scalar_one_or_none()
            
            if existing_role:
                raise ValueError(f"Role '{name}' already exists")
            
            # Validate permissions
            if permissions:
                valid_permissions = [p.value for p in UserPermission]
                for permission in permissions:
                    if permission not in valid_permissions:
                        raise ValueError(f"Invalid permission: {permission}")
            
            # Create role
            role = Role(
                name=name.lower(),
                display_name=display_name,
                description=description,
                permissions=permissions or [],
                is_system_role_bool=is_system_role
            )
            
            self.db.add(role)
            await self.db.commit()
            await self.db.refresh(role)
            
            logger.info("Role created", role_id=str(role.id), name=name)
            return role
            
        except ValueError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to create role", error=str(e))
            raise ValueError("Role creation failed")
    
    async def get_role_by_id(self, role_id: uuid.UUID) -> Optional[Role]:
        """
        Get role by ID
        
        Args:
            role_id: Role ID
            
        Returns:
            Optional[Role]: Role if found
        """
        try:
            stmt = select(Role).where(Role.id == role_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get role by ID", error=str(e))
            return None
    
    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """
        Get role by name
        
        Args:
            name: Role name
            
        Returns:
            Optional[Role]: Role if found
        """
        try:
            stmt = select(Role).where(Role.name == name.lower())
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get role by name", error=str(e))
            return None
    
    async def list_roles(
        self,
        active_only: bool = True,
        include_system: bool = True
    ) -> List[Role]:
        """
        List all roles
        
        Args:
            active_only: Only return active roles
            include_system: Include system roles
            
        Returns:
            List[Role]: List of roles
        """
        try:
            stmt = select(Role)
            
            conditions = []
            if active_only:
                conditions.append(Role.is_active == "true")
            
            if not include_system:
                conditions.append(Role.is_system_role == "false")
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            stmt = stmt.order_by(Role.name)
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("Failed to list roles", error=str(e))
            return []
    
    async def update_role(
        self,
        role_id: uuid.UUID,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Role]:
        """
        Update role
        
        Args:
            role_id: Role ID
            display_name: New display name
            description: New description
            permissions: New permissions list
            is_active: New active status
            
        Returns:
            Optional[Role]: Updated role
            
        Raises:
            ValueError: If invalid data or system role modification
        """
        try:
            # Get role
            role = await self.get_role_by_id(role_id)
            if not role:
                raise ValueError("Role not found")
            
            # Check if system role
            if role.is_system_role_bool:
                raise ValueError("Cannot modify system role")
            
            # Validate permissions
            if permissions:
                valid_permissions = [p.value for p in UserPermission]
                for permission in permissions:
                    if permission not in valid_permissions:
                        raise ValueError(f"Invalid permission: {permission}")
            
            # Update fields
            if display_name is not None:
                role.display_name = display_name
            
            if description is not None:
                role.description = description
            
            if permissions is not None:
                role.permissions = permissions
            
            if is_active is not None:
                role.is_active_bool = is_active
            
            await self.db.commit()
            await self.db.refresh(role)
            
            logger.info("Role updated", role_id=str(role_id))
            return role
            
        except ValueError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to update role", error=str(e))
            raise ValueError("Role update failed")
    
    async def delete_role(self, role_id: uuid.UUID) -> bool:
        """
        Delete role
        
        Args:
            role_id: Role ID
            
        Returns:
            bool: True if deleted successfully
            
        Raises:
            ValueError: If role not found or system role
        """
        try:
            # Get role
            role = await self.get_role_by_id(role_id)
            if not role:
                raise ValueError("Role not found")
            
            # Check if system role
            if role.is_system_role_bool:
                raise ValueError("Cannot delete system role")
            
            # Check if role is in use
            stmt = select(User).where(User.role == UserRole(role.name))
            result = await self.db.execute(stmt)
            users_with_role = result.scalars().all()
            
            if users_with_role:
                raise ValueError(f"Cannot delete role: {len(users_with_role)} users have this role")
            
            # Delete role
            await self.db.delete(role)
            await self.db.commit()
            
            logger.info("Role deleted", role_id=str(role_id))
            return True
            
        except ValueError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to delete role", error=str(e))
            raise ValueError("Role deletion failed")
    
    async def assign_role_to_user(
        self,
        user_id: uuid.UUID,
        role: UserRole
    ) -> bool:
        """
        Assign role to user
        
        Args:
            user_id: User ID
            role: Role to assign
            
        Returns:
            bool: True if assigned successfully
            
        Raises:
            ValueError: If user not found or invalid role
        """
        try:
            # Get user
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError("User not found")
            
            # Assign role
            user.role = role
            await self.db.commit()
            
            logger.info("Role assigned to user", user_id=str(user_id), role=role.value)
            return True
            
        except ValueError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to assign role to user", error=str(e))
            raise ValueError("Role assignment failed")
    
    async def add_permission_to_user(
        self,
        user_id: uuid.UUID,
        permission: UserPermission
    ) -> bool:
        """
        Add permission to user
        
        Args:
            user_id: User ID
            permission: Permission to add
            
        Returns:
            bool: True if added successfully
        """
        try:
            # Get user
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError("User not found")
            
            # Add permission if not already present
            if permission.value not in user.permissions:
                user.permissions = user.permissions + [permission.value]
                await self.db.commit()
                
                logger.info("Permission added to user", user_id=str(user_id), permission=permission.value)
            
            return True
            
        except ValueError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to add permission to user", error=str(e))
            raise ValueError("Permission addition failed")
    
    async def remove_permission_from_user(
        self,
        user_id: uuid.UUID,
        permission: UserPermission
    ) -> bool:
        """
        Remove permission from user
        
        Args:
            user_id: User ID
            permission: Permission to remove
            
        Returns:
            bool: True if removed successfully
        """
        try:
            # Get user
            stmt = select(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError("User not found")
            
            # Remove permission if present
            if permission.value in user.permissions:
                user.permissions = [p for p in user.permissions if p != permission.value]
                await self.db.commit()
                
                logger.info("Permission removed from user", user_id=str(user_id), permission=permission.value)
            
            return True
            
        except ValueError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to remove permission from user", error=str(e))
            raise ValueError("Permission removal failed")
