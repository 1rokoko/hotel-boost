"""
Admin audit logging utilities
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import structlog

from app.models.admin_audit_log import AdminAuditLog, AuditAction, AuditSeverity
from app.database import get_db_session

logger = structlog.get_logger(__name__)


class AdminAuditLogger:
    """
    Utility class for admin audit logging
    
    Provides convenient methods for logging admin actions and events.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize audit logger
        
        Args:
            db_session: Database session (optional, will create if not provided)
        """
        self.db_session = db_session
    
    def log_action(
        self,
        admin_user_id: Optional[uuid.UUID],
        action: AuditAction,
        description: str,
        severity: AuditSeverity = AuditSeverity.LOW,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        hotel_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> AdminAuditLog:
        """
        Log an admin action
        
        Args:
            admin_user_id: ID of the admin user performing the action
            action: Type of action performed
            description: Human-readable description
            severity: Severity level of the action
            target_type: Type of target object
            target_id: ID of target object
            hotel_id: Hotel context
            ip_address: IP address of the request
            user_agent: User agent string
            request_id: Request correlation ID
            old_values: Previous values before change
            new_values: New values after change
            metadata: Additional metadata
            success: Whether action was successful
            error_message: Error message if failed
            
        Returns:
            AdminAuditLog: Created audit log entry
        """
        try:
            # Create audit log entry
            audit_log = AdminAuditLog.create_log(
                admin_user_id=admin_user_id,
                action=action,
                description=description,
                severity=severity,
                target_type=target_type,
                target_id=target_id,
                hotel_id=hotel_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                old_values=old_values,
                new_values=new_values,
                metadata=metadata,
                success=success,
                error_message=error_message
            )
            
            # Save to database
            if self.db_session:
                db = self.db_session
            else:
                db = get_db_session()

            db.add(audit_log)
            db.commit()
            db.refresh(audit_log)
            
            logger.info(
                "Admin action logged",
                audit_log_id=str(audit_log.id),
                admin_user_id=str(admin_user_id) if admin_user_id else None,
                action=action.value,
                severity=severity.value,
                success=success
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(
                "Failed to log admin action",
                error=str(e),
                admin_user_id=str(admin_user_id) if admin_user_id else None,
                action=action.value
            )
            raise
    
    async def log_login_attempt(
        self,
        username: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        admin_user_id: Optional[uuid.UUID] = None,
        error_message: Optional[str] = None
    ) -> AdminAuditLog:
        """
        Log a login attempt
        
        Args:
            username: Username used for login
            success: Whether login was successful
            ip_address: IP address of the request
            user_agent: User agent string
            admin_user_id: Admin user ID (if successful)
            error_message: Error message (if failed)
            
        Returns:
            AdminAuditLog: Created audit log entry
        """
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        severity = AuditSeverity.LOW if success else AuditSeverity.MEDIUM
        description = f"Login attempt for username: {username}"
        
        if success:
            description += " - SUCCESS"
        else:
            description += " - FAILED"
        
        return await self.log_action(
            admin_user_id=admin_user_id,
            action=action,
            description=description,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"username": username},
            success=success,
            error_message=error_message
        )
    
    async def log_user_management(
        self,
        admin_user_id: uuid.UUID,
        action: AuditAction,
        target_user_id: uuid.UUID,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AdminAuditLog:
        """
        Log user management actions
        
        Args:
            admin_user_id: ID of admin performing the action
            action: Type of user management action
            target_user_id: ID of user being managed
            changes: Changes made to the user
            ip_address: IP address of the request
            user_agent: User agent string
            
        Returns:
            AdminAuditLog: Created audit log entry
        """
        action_descriptions = {
            AuditAction.USER_CREATED: "Created new admin user",
            AuditAction.USER_UPDATED: "Updated admin user",
            AuditAction.USER_DELETED: "Deleted admin user",
            AuditAction.USER_ACTIVATED: "Activated admin user",
            AuditAction.USER_DEACTIVATED: "Deactivated admin user",
            AuditAction.ROLE_CHANGED: "Changed admin user role",
            AuditAction.PERMISSIONS_CHANGED: "Changed admin user permissions"
        }
        
        description = action_descriptions.get(action, "User management action")
        description += f" (target: {target_user_id})"
        
        old_values = None
        new_values = None
        if changes:
            old_values = changes.get("old_values")
            new_values = changes.get("new_values")
        
        return await self.log_action(
            admin_user_id=admin_user_id,
            action=action,
            description=description,
            severity=AuditSeverity.MEDIUM,
            target_type="admin_user",
            target_id=str(target_user_id),
            ip_address=ip_address,
            user_agent=user_agent,
            old_values=old_values,
            new_values=new_values,
            success=True
        )
    
    async def log_hotel_management(
        self,
        admin_user_id: uuid.UUID,
        action: AuditAction,
        hotel_id: uuid.UUID,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AdminAuditLog:
        """
        Log hotel management actions
        
        Args:
            admin_user_id: ID of admin performing the action
            action: Type of hotel management action
            hotel_id: ID of hotel being managed
            changes: Changes made to the hotel
            ip_address: IP address of the request
            user_agent: User agent string
            
        Returns:
            AdminAuditLog: Created audit log entry
        """
        action_descriptions = {
            AuditAction.HOTEL_CREATED: "Created new hotel",
            AuditAction.HOTEL_UPDATED: "Updated hotel",
            AuditAction.HOTEL_DELETED: "Deleted hotel",
            AuditAction.HOTEL_SETTINGS_CHANGED: "Changed hotel settings"
        }
        
        description = action_descriptions.get(action, "Hotel management action")
        description += f" (hotel: {hotel_id})"
        
        old_values = None
        new_values = None
        if changes:
            old_values = changes.get("old_values")
            new_values = changes.get("new_values")
        
        return await self.log_action(
            admin_user_id=admin_user_id,
            action=action,
            description=description,
            severity=AuditSeverity.MEDIUM,
            target_type="hotel",
            target_id=str(hotel_id),
            hotel_id=hotel_id,
            ip_address=ip_address,
            user_agent=user_agent,
            old_values=old_values,
            new_values=new_values,
            success=True
        )
    
    async def log_data_export(
        self,
        admin_user_id: uuid.UUID,
        export_type: str,
        hotel_id: Optional[uuid.UUID] = None,
        record_count: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AdminAuditLog:
        """
        Log data export actions
        
        Args:
            admin_user_id: ID of admin performing the export
            export_type: Type of data being exported
            hotel_id: Hotel ID (if hotel-specific export)
            record_count: Number of records exported
            ip_address: IP address of the request
            user_agent: User agent string
            
        Returns:
            AdminAuditLog: Created audit log entry
        """
        description = f"Exported {export_type} data"
        if hotel_id:
            description += f" for hotel {hotel_id}"
        if record_count:
            description += f" ({record_count} records)"
        
        return await self.log_action(
            admin_user_id=admin_user_id,
            action=AuditAction.DATA_EXPORTED,
            description=description,
            severity=AuditSeverity.MEDIUM,
            target_type="data_export",
            hotel_id=hotel_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "export_type": export_type,
                "record_count": record_count
            },
            success=True
        )
    
    async def log_security_event(
        self,
        admin_user_id: Optional[uuid.UUID],
        event_type: str,
        description: str,
        severity: AuditSeverity = AuditSeverity.HIGH,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AdminAuditLog:
        """
        Log security events
        
        Args:
            admin_user_id: ID of admin user (if applicable)
            event_type: Type of security event
            description: Description of the event
            severity: Severity level
            ip_address: IP address of the request
            user_agent: User agent string
            metadata: Additional metadata
            
        Returns:
            AdminAuditLog: Created audit log entry
        """
        action_map = {
            "violation": AuditAction.SECURITY_VIOLATION,
            "unauthorized": AuditAction.UNAUTHORIZED_ACCESS,
            "suspicious": AuditAction.SUSPICIOUS_ACTIVITY
        }
        
        action = action_map.get(event_type, AuditAction.SECURITY_VIOLATION)
        
        return await self.log_action(
            admin_user_id=admin_user_id,
            action=action,
            description=description,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
            success=False
        )
