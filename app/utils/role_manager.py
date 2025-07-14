"""
Role management utilities

This module provides utilities for managing user roles and permissions.
"""

import uuid
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.user import User
from app.models.role import Role, UserRole, UserPermission
from app.services.rbac_service import RBACService

logger = structlog.get_logger(__name__)


class RoleManager:
    """Utility class for role management operations"""
    
    def __init__(self, db: AsyncSession):
        """
        Initialize role manager
        
        Args:
            db: Database session
        """
        self.db = db
        self.rbac_service = RBACService(db)
    
    async def initialize_default_roles(self) -> bool:
        """
        Initialize default system roles if they don't exist
        
        Returns:
            bool: True if initialization was successful
        """
        try:
            default_roles = [
                {
                    "name": "super_admin",
                    "display_name": "Super Administrator",
                    "description": "Full system access with all permissions",
                    "permissions": [p.value for p in UserPermission]
                },
                {
                    "name": "hotel_admin",
                    "display_name": "Hotel Administrator",
                    "description": "Hotel administrator with management permissions",
                    "permissions": [
                        UserPermission.MANAGE_HOTEL_SETTINGS.value,
                        UserPermission.VIEW_HOTEL_ANALYTICS.value,
                        UserPermission.MANAGE_HOTEL_USERS.value,
                        UserPermission.MANAGE_TRIGGERS.value,
                        UserPermission.VIEW_CONVERSATIONS.value,
                        UserPermission.SEND_MESSAGES.value,
                        UserPermission.MANAGE_TEMPLATES.value,
                        UserPermission.VIEW_ANALYTICS.value,
                        UserPermission.EXPORT_DATA.value,
                        UserPermission.GENERATE_REPORTS.value,
                        UserPermission.VIEW_MONITORING.value,
                    ]
                },
                {
                    "name": "hotel_staff",
                    "display_name": "Hotel Staff",
                    "description": "Hotel staff member with operational permissions",
                    "permissions": [
                        UserPermission.VIEW_CONVERSATIONS.value,
                        UserPermission.SEND_MESSAGES.value,
                        UserPermission.VIEW_ANALYTICS.value,
                        UserPermission.VIEW_MONITORING.value,
                    ]
                },
                {
                    "name": "viewer",
                    "display_name": "Viewer",
                    "description": "Read-only access to hotel data and analytics",
                    "permissions": [
                        UserPermission.VIEW_CONVERSATIONS.value,
                        UserPermission.VIEW_ANALYTICS.value,
                    ]
                }
            ]
            
            for role_data in default_roles:
                existing_role = await self.rbac_service.get_role_by_name(role_data["name"])
                if not existing_role:
                    await self.rbac_service.create_role(
                        name=role_data["name"],
                        display_name=role_data["display_name"],
                        description=role_data["description"],
                        permissions=role_data["permissions"],
                        is_system_role=True
                    )
                    logger.info("Default role created", role_name=role_data["name"])
            
            return True
            
        except Exception as e:
            logger.error("Failed to initialize default roles", error=str(e))
            return False
    
    def get_role_hierarchy(self) -> Dict[UserRole, int]:
        """
        Get role hierarchy levels
        
        Returns:
            Dict mapping roles to hierarchy levels (higher number = more permissions)
        """
        return {
            UserRole.VIEWER: 1,
            UserRole.HOTEL_STAFF: 2,
            UserRole.HOTEL_ADMIN: 3,
            UserRole.SUPER_ADMIN: 4
        }
    
    def can_user_manage_role(self, manager_role: UserRole, target_role: UserRole) -> bool:
        """
        Check if a user with manager_role can manage users with target_role
        
        Args:
            manager_role: Role of the user trying to manage
            target_role: Role being managed
            
        Returns:
            bool: True if management is allowed
        """
        hierarchy = self.get_role_hierarchy()
        manager_level = hierarchy.get(manager_role, 0)
        target_level = hierarchy.get(target_role, 0)
        
        # Super admin can manage all roles
        if manager_role == UserRole.SUPER_ADMIN:
            return True
        
        # Users can only manage roles at their level or below
        return manager_level > target_level
    
    def get_manageable_roles(self, user_role: UserRole) -> List[UserRole]:
        """
        Get list of roles that a user can manage
        
        Args:
            user_role: User's role
            
        Returns:
            List[UserRole]: Roles that can be managed
        """
        hierarchy = self.get_role_hierarchy()
        user_level = hierarchy.get(user_role, 0)
        
        manageable = []
        for role, level in hierarchy.items():
            if user_role == UserRole.SUPER_ADMIN or level <= user_level:
                manageable.append(role)
        
        return manageable
    
    def get_role_permissions_diff(
        self,
        from_role: UserRole,
        to_role: UserRole
    ) -> Dict[str, List[str]]:
        """
        Get permission differences between roles
        
        Args:
            from_role: Source role
            to_role: Target role
            
        Returns:
            Dict with 'added' and 'removed' permission lists
        """
        from_permissions = set(Role.get_default_role_permissions(from_role))
        to_permissions = set(Role.get_default_role_permissions(to_role))
        
        return {
            "added": list(to_permissions - from_permissions),
            "removed": list(from_permissions - to_permissions)
        }
    
    async def bulk_assign_role(
        self,
        user_ids: List[uuid.UUID],
        role: UserRole,
        manager_user: User
    ) -> Dict[str, Any]:
        """
        Assign role to multiple users
        
        Args:
            user_ids: List of user IDs
            role: Role to assign
            manager_user: User performing the assignment
            
        Returns:
            Dict with assignment results
        """
        results = {
            "successful": [],
            "failed": [],
            "skipped": []
        }
        
        try:
            # Check if manager can assign this role
            if not self.can_user_manage_role(manager_user.role, role):
                raise ValueError(f"Insufficient permissions to assign role '{role.value}'")
            
            for user_id in user_ids:
                try:
                    success = await self.rbac_service.assign_role_to_user(user_id, role)
                    if success:
                        results["successful"].append(str(user_id))
                    else:
                        results["failed"].append(str(user_id))
                        
                except Exception as e:
                    logger.warning("Failed to assign role to user", user_id=str(user_id), error=str(e))
                    results["failed"].append(str(user_id))
            
            logger.info(
                "Bulk role assignment completed",
                role=role.value,
                successful=len(results["successful"]),
                failed=len(results["failed"])
            )
            
            return results
            
        except Exception as e:
            logger.error("Bulk role assignment failed", error=str(e))
            raise ValueError("Bulk role assignment failed")
    
    async def get_role_usage_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about role usage
        
        Returns:
            Dict with role usage statistics
        """
        try:
            from sqlalchemy import func, select
            
            # Get user count by role
            stmt = select(
                User.role,
                func.count(User.id).label('user_count')
            ).group_by(User.role)
            
            result = await self.db.execute(stmt)
            role_counts = {row.role.value: row.user_count for row in result}
            
            # Get total user count
            total_stmt = select(func.count(User.id))
            total_result = await self.db.execute(total_stmt)
            total_users = total_result.scalar()
            
            # Get active user count by role
            active_stmt = select(
                User.role,
                func.count(User.id).label('active_count')
            ).where(User.is_active == True).group_by(User.role)
            
            active_result = await self.db.execute(active_stmt)
            active_counts = {row.role.value: row.active_count for row in active_result}
            
            return {
                "total_users": total_users,
                "role_distribution": role_counts,
                "active_role_distribution": active_counts,
                "role_percentages": {
                    role: round((count / total_users) * 100, 2) if total_users > 0 else 0
                    for role, count in role_counts.items()
                }
            }
            
        except Exception as e:
            logger.error("Failed to get role usage statistics", error=str(e))
            return {}
    
    def validate_permission_assignment(
        self,
        user_role: UserRole,
        permissions: List[str]
    ) -> Dict[str, Any]:
        """
        Validate permission assignment for a role
        
        Args:
            user_role: User's role
            permissions: Permissions to validate
            
        Returns:
            Dict with validation results
        """
        valid_permissions = [p.value for p in UserPermission]
        role_permissions = set(Role.get_default_role_permissions(user_role))
        
        invalid_permissions = [p for p in permissions if p not in valid_permissions]
        redundant_permissions = [p for p in permissions if p in role_permissions]
        new_permissions = [p for p in permissions if p not in role_permissions and p in valid_permissions]
        
        return {
            "valid": len(invalid_permissions) == 0,
            "invalid_permissions": invalid_permissions,
            "redundant_permissions": redundant_permissions,
            "new_permissions": new_permissions,
            "total_permissions": len(permissions)
        }
    
    async def cleanup_orphaned_permissions(self) -> int:
        """
        Remove invalid permissions from all users
        
        Returns:
            int: Number of users cleaned up
        """
        try:
            valid_permissions = [p.value for p in UserPermission]
            cleaned_count = 0
            
            # Get all users with permissions
            from sqlalchemy import select
            stmt = select(User).where(User.permissions != [])
            result = await self.db.execute(stmt)
            users = result.scalars().all()
            
            for user in users:
                original_permissions = user.permissions.copy()
                cleaned_permissions = [p for p in user.permissions if p in valid_permissions]
                
                if len(cleaned_permissions) != len(original_permissions):
                    user.permissions = cleaned_permissions
                    cleaned_count += 1
            
            if cleaned_count > 0:
                await self.db.commit()
                logger.info("Cleaned up orphaned permissions", users_affected=cleaned_count)
            
            return cleaned_count
            
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to cleanup orphaned permissions", error=str(e))
            return 0
