"""
Admin Audit Log model for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, DateTime, Index, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID, INET
from sqlalchemy.orm import relationship, validates
import enum

from app.models.base import BaseModel, TimestampMixin


class AuditAction(str, enum.Enum):
    """Audit action types"""
    # Authentication actions
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    
    # User management actions
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    ROLE_CHANGED = "role_changed"
    PERMISSIONS_CHANGED = "permissions_changed"
    
    # Hotel management actions
    HOTEL_CREATED = "hotel_created"
    HOTEL_UPDATED = "hotel_updated"
    HOTEL_DELETED = "hotel_deleted"
    HOTEL_SETTINGS_CHANGED = "hotel_settings_changed"
    
    # System configuration actions
    SYSTEM_SETTINGS_CHANGED = "system_settings_changed"
    TRIGGER_CREATED = "trigger_created"
    TRIGGER_UPDATED = "trigger_updated"
    TRIGGER_DELETED = "trigger_deleted"
    TEMPLATE_CREATED = "template_created"
    TEMPLATE_UPDATED = "template_updated"
    TEMPLATE_DELETED = "template_deleted"
    
    # Data actions
    DATA_EXPORTED = "data_exported"
    REPORT_GENERATED = "report_generated"
    BULK_OPERATION = "bulk_operation"
    
    # Security actions
    SECURITY_VIOLATION = "security_violation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class AuditSeverity(str, enum.Enum):
    """Audit log severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AdminAuditLog(BaseModel, TimestampMixin):
    """
    Admin audit log model for tracking administrative actions
    
    Provides comprehensive audit trail for all admin operations.
    """
    __tablename__ = "admin_audit_logs"
    
    # User who performed the action
    admin_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('admin_users.id', ondelete='SET NULL'),
        nullable=True,
        comment="Admin user who performed the action"
    )
    
    # Action details
    action = Column(
        SQLEnum(AuditAction),
        nullable=False,
        comment="Type of action performed"
    )
    
    severity = Column(
        SQLEnum(AuditSeverity),
        nullable=False,
        default=AuditSeverity.LOW,
        comment="Severity level of the action"
    )
    
    # Target information
    target_type = Column(
        String(100),
        nullable=True,
        comment="Type of target object (user, hotel, trigger, etc.)"
    )
    
    target_id = Column(
        String(255),
        nullable=True,
        comment="ID of the target object"
    )
    
    # Hotel context (for multi-tenant tracking)
    hotel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hotels.id', ondelete='SET NULL'),
        nullable=True,
        comment="Hotel context for the action"
    )
    
    # Request information
    ip_address = Column(
        INET,
        nullable=True,
        comment="IP address of the request"
    )
    
    user_agent = Column(
        Text,
        nullable=True,
        comment="User agent string"
    )
    
    request_id = Column(
        String(100),
        nullable=True,
        comment="Request correlation ID"
    )
    
    # Action details
    description = Column(
        Text,
        nullable=False,
        comment="Human-readable description of the action"
    )
    
    # Data changes
    old_values = Column(
        JSONB,
        nullable=True,
        comment="Previous values before the change"
    )
    
    new_values = Column(
        JSONB,
        nullable=True,
        comment="New values after the change"
    )
    
    # Additional context
    audit_metadata = Column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional metadata about the action"
    )
    
    # Status
    success = Column(
        String(10),
        nullable=False,
        default="true",
        comment="Whether the action was successful"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if action failed"
    )
    
    __table_args__ = (
        # Indexes for performance
        Index('idx_audit_logs_admin_user_id', 'admin_user_id'),
        Index('idx_audit_logs_action', 'action'),
        Index('idx_audit_logs_severity', 'severity'),
        Index('idx_audit_logs_target_type', 'target_type'),
        Index('idx_audit_logs_target_id', 'target_id'),
        Index('idx_audit_logs_hotel_id', 'hotel_id'),
        Index('idx_audit_logs_created_at', 'created_at'),
        Index('idx_audit_logs_ip_address', 'ip_address'),
        Index('idx_audit_logs_success', 'success'),
        
        # Composite indexes for common queries
        Index('idx_audit_logs_user_action', 'admin_user_id', 'action'),
        Index('idx_audit_logs_hotel_action', 'hotel_id', 'action'),
        Index('idx_audit_logs_date_action', 'created_at', 'action'),
        Index('idx_audit_logs_severity_date', 'severity', 'created_at'),
    )
    
    # Relationships
    admin_user = relationship("AdminUser", back_populates="audit_logs")
    hotel = relationship("Hotel")
    
    @validates('action')
    def validate_action(self, key, action):
        """Validate action type"""
        if not action:
            raise ValueError("Action is required")
        return action
    
    @validates('description')
    def validate_description(self, key, description):
        """Validate description"""
        if not description or not description.strip():
            raise ValueError("Description is required")
        return description.strip()
    
    @validates('success')
    def validate_success(self, key, success):
        """Validate success field"""
        if success not in ["true", "false"]:
            raise ValueError("Success must be 'true' or 'false'")
        return success
    
    @property
    def is_successful(self) -> bool:
        """Check if action was successful"""
        return self.success == "true"
    
    @classmethod
    def create_log(
        cls,
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
        audit_metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> 'AdminAuditLog':
        """
        Create a new audit log entry
        
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
            AdminAuditLog: New audit log entry
        """
        return cls(
            admin_user_id=admin_user_id,
            action=action,
            severity=severity,
            target_type=target_type,
            target_id=target_id,
            hotel_id=hotel_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            description=description,
            old_values=old_values or {},
            new_values=new_values or {},
            audit_metadata=audit_metadata or {},
            success="true" if success else "false",
            error_message=error_message
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': str(self.id),
            'admin_user_id': str(self.admin_user_id) if self.admin_user_id else None,
            'action': self.action.value,
            'severity': self.severity.value,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'hotel_id': str(self.hotel_id) if self.hotel_id else None,
            'ip_address': str(self.ip_address) if self.ip_address else None,
            'user_agent': self.user_agent,
            'request_id': self.request_id,
            'description': self.description,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'metadata': self.metadata,
            'success': self.is_successful,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f"<AdminAuditLog(id={self.id}, action={self.action}, user={self.admin_user_id})>"
