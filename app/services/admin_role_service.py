"""
Admin role management service
"""

import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
import structlog

from app.models.admin_user import AdminUser, AdminRole, AdminPermission
from app.models.admin_audit_log import AuditAction, AuditSeverity
from app.core.admin_security import AdminSecurity, AdminAuthorizationError
from app.utils.admin_audit import AdminAuditLogger
from app.database import get_db_session

logger = structlog.get_logger(__name__)


class AdminRoleService:
    """
    Service for admin role and permission management
    """
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        """
        Initialize admin role service
        
        Args:
            db_session: Database session (optional)
        """
        self.db_session = db_session
        self.audit_logger = AdminAuditLogger(db_session)
    
    async def get_available_roles(self, requesting_user: AdminUser) -> List[Dict[str, Any]]:
        """
        Get list of available roles based on requesting user's permissions
        
        Args:
            requesting_user: User requesting role information
            
        Returns:
            List of role information dictionaries
        """
        try:
            roles = []
            
            # Super admin can see all roles
            if requesting_user.role == AdminRole.SUPER_ADMIN:
                available_roles = list(AdminRole)
            else:
                # Hotel admins can only assign hotel staff and viewer roles
                available_roles = [AdminRole.HOTEL_STAFF, AdminRole.VIEWER]
            
            for role in available_roles:
                role_info = {
                    "role": role.value,
                    "name": role.value.replace("_", " ").title(),
                    "description": AdminSecurity.get_role_description(role),
                    "permissions": self._get_role_permissions(role),
                    "can_assign": self._can_assign_role(requesting_user, role)
                }
                roles.append(role_info)
            
            logger.info(
                "Available roles retrieved",
                user_id=str(requesting_user.id),
                roles_count=len(roles)
            )
            
            return roles
            
        except Exception as e:
            logger.error("Error getting available roles", error=str(e))
            raise
    
    async def get_available_permissions(self, requesting_user: AdminUser) -> List[Dict[str, Any]]:
        """
        Get list of available permissions based on requesting user's role
        
        Args:
            requesting_user: User requesting permission information
            
        Returns:
            List of permission information dictionaries
        """
        try:
            permissions = []
            
            # Super admin can see all permissions
            if requesting_user.role == AdminRole.SUPER_ADMIN:
                available_permissions = list(AdminPermission)
            else:
                # Hotel admins can only see hotel-related permissions
                available_permissions = [
                    AdminPermission.MANAGE_HOTEL_SETTINGS,
                    AdminPermission.VIEW_HOTEL_ANALYTICS,
                    AdminPermission.MANAGE_HOTEL_USERS,
                    AdminPermission.MANAGE_TRIGGERS,
                    AdminPermission.VIEW_CONVERSATIONS,
                    AdminPermission.SEND_MESSAGES,
                    AdminPermission.MANAGE_TEMPLATES,
                    AdminPermission.VIEW_ANALYTICS,
                    AdminPermission.EXPORT_DATA,
                    AdminPermission.GENERATE_REPORTS,
                    AdminPermission.VIEW_MONITORING
                ]
            
            for permission in available_permissions:
                permission_info = {
                    "permission": permission.value,
                    "name": permission.value.replace("_", " ").title(),
                    "description": AdminSecurity.get_permission_description(permission),
                    "category": self._get_permission_category(permission)
                }
                permissions.append(permission_info)
            
            logger.info(
                "Available permissions retrieved",
                user_id=str(requesting_user.id),
                permissions_count=len(permissions)
            )
            
            return permissions
            
        except Exception as e:
            logger.error("Error getting available permissions", error=str(e))
            raise
    
    async def assign_role(
        self,
        user_id: uuid.UUID,
        new_role: AdminRole,
        assigning_user: AdminUser
    ) -> bool:
        """
        Assign role to admin user
        
        Args:
            user_id: User ID to assign role to
            new_role: New role to assign
            assigning_user: User performing the role assignment
            
        Returns:
            bool: True if role assigned successfully
        """
        try:
            # Check if assigning user can assign this role
            if not self._can_assign_role(assigning_user, new_role):
                raise AdminAuthorizationError(f"Insufficient permissions to assign role: {new_role.value}")
            
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Get target user
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                target_user = result.scalar_one_or_none()
                
                if not target_user:
                    return False
                
                # Check if assigning user can modify target user
                if not self._can_modify_user_role(assigning_user, target_user):
                    raise AdminAuthorizationError("Insufficient permissions to modify this user's role")
                
                # Store old role for audit
                old_role = target_user.role
                
                # Assign new role
                target_user.role = new_role
                
                # Update permissions to match new role
                target_user.permissions = target_user.get_role_permissions()
                
                await db.commit()
                await db.refresh(target_user)
                
                # Log role change
                await self.audit_logger.log_user_management(
                    admin_user_id=assigning_user.id,
                    action=AuditAction.ROLE_CHANGED,
                    target_user_id=target_user.id,
                    changes={
                        "old_values": {"role": old_role.value},
                        "new_values": {"role": new_role.value}
                    }
                )
                
                logger.info(
                    "Role assigned to admin user",
                    target_user_id=str(target_user.id),
                    old_role=old_role.value,
                    new_role=new_role.value,
                    assigned_by=str(assigning_user.id)
                )
                
                return True
                
        except AdminAuthorizationError:
            raise
        except Exception as e:
            logger.error("Error assigning role", error=str(e))
            raise
    
    async def update_user_permissions(
        self,
        user_id: uuid.UUID,
        permissions: List[AdminPermission],
        updating_user: AdminUser
    ) -> bool:
        """
        Update user's specific permissions
        
        Args:
            user_id: User ID to update permissions for
            permissions: List of permissions to assign
            updating_user: User performing the update
            
        Returns:
            bool: True if permissions updated successfully
        """
        try:
            # Get database session
            if self.db_session:
                session = self.db_session
            else:
                session = get_db_session()
            
            async with session as db:
                # Get target user
                stmt = select(AdminUser).where(AdminUser.id == user_id)
                result = await db.execute(stmt)
                target_user = result.scalar_one_or_none()
                
                if not target_user:
                    return False
                
                # Check if updating user can modify target user
                if not self._can_modify_user_permissions(updating_user, target_user, permissions):
                    raise AdminAuthorizationError("Insufficient permissions to modify user permissions")
                
                # Store old permissions for audit
                old_permissions = target_user.permissions.copy()
                
                # Update permissions
                target_user.permissions = [p.value for p in permissions]
                
                await db.commit()
                await db.refresh(target_user)
                
                # Log permission change
                await self.audit_logger.log_user_management(
                    admin_user_id=updating_user.id,
                    action=AuditAction.PERMISSIONS_CHANGED,
                    target_user_id=target_user.id,
                    changes={
                        "old_values": {"permissions": old_permissions},
                        "new_values": {"permissions": target_user.permissions}
                    }
                )
                
                logger.info(
                    "Permissions updated for admin user",
                    target_user_id=str(target_user.id),
                    permissions_count=len(permissions),
                    updated_by=str(updating_user.id)
                )
                
                return True
                
        except AdminAuthorizationError:
            raise
        except Exception as e:
            logger.error("Error updating user permissions", error=str(e))
            raise
    
    async def get_role_hierarchy(self) -> Dict[str, Any]:
        """
        Get role hierarchy information
        
        Returns:
            Dict containing role hierarchy and relationships
        """
        try:
            hierarchy = {
                "roles": [
                    {
                        "role": AdminRole.SUPER_ADMIN.value,
                        "level": 4,
                        "can_manage": [r.value for r in AdminRole],
                        "description": "Full system access"
                    },
                    {
                        "role": AdminRole.HOTEL_ADMIN.value,
                        "level": 3,
                        "can_manage": [AdminRole.HOTEL_STAFF.value, AdminRole.VIEWER.value],
                        "description": "Hotel management access"
                    },
                    {
                        "role": AdminRole.HOTEL_STAFF.value,
                        "level": 2,
                        "can_manage": [AdminRole.VIEWER.value],
                        "description": "Hotel operational access"
                    },
                    {
                        "role": AdminRole.VIEWER.value,
                        "level": 1,
                        "can_manage": [],
                        "description": "Read-only access"
                    }
                ],
                "permission_categories": {
                    "system": ["MANAGE_SYSTEM", "VIEW_SYSTEM_METRICS", "MANAGE_HOTELS"],
                    "hotel": ["MANAGE_HOTEL_SETTINGS", "VIEW_HOTEL_ANALYTICS", "MANAGE_HOTEL_USERS"],
                    "messaging": ["VIEW_CONVERSATIONS", "SEND_MESSAGES", "MANAGE_TEMPLATES", "MANAGE_TRIGGERS"],
                    "analytics": ["VIEW_ANALYTICS", "EXPORT_DATA", "GENERATE_REPORTS"],
                    "monitoring": ["VIEW_MONITORING", "MANAGE_ALERTS"]
                }
            }
            
            return hierarchy
            
        except Exception as e:
            logger.error("Error getting role hierarchy", error=str(e))
            raise
    
    def _get_role_permissions(self, role: AdminRole) -> List[str]:
        """Get default permissions for a role"""
        role_permissions = {
            AdminRole.SUPER_ADMIN: [p.value for p in AdminPermission],
            AdminRole.HOTEL_ADMIN: [
                AdminPermission.MANAGE_HOTEL_SETTINGS.value,
                AdminPermission.VIEW_HOTEL_ANALYTICS.value,
                AdminPermission.MANAGE_HOTEL_USERS.value,
                AdminPermission.MANAGE_TRIGGERS.value,
                AdminPermission.VIEW_CONVERSATIONS.value,
                AdminPermission.SEND_MESSAGES.value,
                AdminPermission.MANAGE_TEMPLATES.value,
                AdminPermission.VIEW_ANALYTICS.value,
                AdminPermission.EXPORT_DATA.value,
                AdminPermission.GENERATE_REPORTS.value,
                AdminPermission.VIEW_MONITORING.value,
            ],
            AdminRole.HOTEL_STAFF: [
                AdminPermission.VIEW_HOTEL_ANALYTICS.value,
                AdminPermission.VIEW_CONVERSATIONS.value,
                AdminPermission.SEND_MESSAGES.value,
                AdminPermission.VIEW_ANALYTICS.value,
                AdminPermission.VIEW_MONITORING.value,
            ],
            AdminRole.VIEWER: [
                AdminPermission.VIEW_HOTEL_ANALYTICS.value,
                AdminPermission.VIEW_CONVERSATIONS.value,
                AdminPermission.VIEW_ANALYTICS.value,
                AdminPermission.VIEW_MONITORING.value,
            ]
        }
        
        return role_permissions.get(role, [])
    
    def _get_permission_category(self, permission: AdminPermission) -> str:
        """Get category for a permission"""
        system_permissions = [
            AdminPermission.MANAGE_SYSTEM,
            AdminPermission.VIEW_SYSTEM_METRICS,
            AdminPermission.MANAGE_HOTELS
        ]
        
        hotel_permissions = [
            AdminPermission.MANAGE_HOTEL_SETTINGS,
            AdminPermission.VIEW_HOTEL_ANALYTICS,
            AdminPermission.MANAGE_HOTEL_USERS
        ]
        
        messaging_permissions = [
            AdminPermission.VIEW_CONVERSATIONS,
            AdminPermission.SEND_MESSAGES,
            AdminPermission.MANAGE_TEMPLATES,
            AdminPermission.MANAGE_TRIGGERS
        ]
        
        analytics_permissions = [
            AdminPermission.VIEW_ANALYTICS,
            AdminPermission.EXPORT_DATA,
            AdminPermission.GENERATE_REPORTS
        ]
        
        monitoring_permissions = [
            AdminPermission.VIEW_MONITORING,
            AdminPermission.MANAGE_ALERTS
        ]
        
        if permission in system_permissions:
            return "system"
        elif permission in hotel_permissions:
            return "hotel"
        elif permission in messaging_permissions:
            return "messaging"
        elif permission in analytics_permissions:
            return "analytics"
        elif permission in monitoring_permissions:
            return "monitoring"
        else:
            return "other"
    
    def _can_assign_role(self, assigning_user: AdminUser, role: AdminRole) -> bool:
        """Check if user can assign specific role"""
        # Super admin can assign any role
        if assigning_user.role == AdminRole.SUPER_ADMIN:
            return True
        
        # Hotel admins can only assign hotel staff and viewer roles
        if assigning_user.role == AdminRole.HOTEL_ADMIN:
            return role in [AdminRole.HOTEL_STAFF, AdminRole.VIEWER]
        
        return False
    
    def _can_modify_user_role(self, modifying_user: AdminUser, target_user: AdminUser) -> bool:
        """Check if user can modify target user's role"""
        # Super admin can modify any user's role
        if modifying_user.role == AdminRole.SUPER_ADMIN:
            return True
        
        # Hotel admins can modify users from their hotel (except super admins and other hotel admins)
        if (modifying_user.role == AdminRole.HOTEL_ADMIN and 
            modifying_user.hotel_id and 
            modifying_user.hotel_id == target_user.hotel_id):
            return target_user.role not in [AdminRole.SUPER_ADMIN, AdminRole.HOTEL_ADMIN]
        
        return False
    
    def _can_modify_user_permissions(
        self, 
        modifying_user: AdminUser, 
        target_user: AdminUser, 
        permissions: List[AdminPermission]
    ) -> bool:
        """Check if user can modify target user's permissions"""
        # Super admin can modify any permissions
        if modifying_user.role == AdminRole.SUPER_ADMIN:
            return True
        
        # Hotel admins can modify permissions for their hotel users
        if (modifying_user.role == AdminRole.HOTEL_ADMIN and 
            modifying_user.hotel_id and 
            modifying_user.hotel_id == target_user.hotel_id):
            
            # Can't modify super admins or other hotel admins
            if target_user.role in [AdminRole.SUPER_ADMIN, AdminRole.HOTEL_ADMIN]:
                return False
            
            # Can only assign hotel-related permissions
            allowed_permissions = [
                AdminPermission.MANAGE_HOTEL_SETTINGS,
                AdminPermission.VIEW_HOTEL_ANALYTICS,
                AdminPermission.MANAGE_HOTEL_USERS,
                AdminPermission.MANAGE_TRIGGERS,
                AdminPermission.VIEW_CONVERSATIONS,
                AdminPermission.SEND_MESSAGES,
                AdminPermission.MANAGE_TEMPLATES,
                AdminPermission.VIEW_ANALYTICS,
                AdminPermission.EXPORT_DATA,
                AdminPermission.GENERATE_REPORTS,
                AdminPermission.VIEW_MONITORING
            ]
            
            return all(p in allowed_permissions for p in permissions)
        
        return False


async def get_admin_role_service(db: AsyncSession = None) -> AdminRoleService:
    """
    Dependency to get admin role service
    
    Args:
        db: Database session
        
    Returns:
        AdminRoleService: Admin role service instance
    """
    return AdminRoleService(db_session=db)
