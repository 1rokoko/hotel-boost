"""
Audit logger utility for tracking hotel changes and operations
"""

import uuid
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog

from app.core.logging import get_logger
from app.core.tenant_context import get_current_hotel_id, get_current_hotel_name

logger = get_logger(__name__)


class AuditAction(Enum):
    """Audit action types"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    EXPORT = "export"
    IMPORT = "import"
    LOGIN = "login"
    LOGOUT = "logout"
    CONFIGURE = "configure"
    VALIDATE = "validate"
    VERIFY = "verify"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    RESET = "reset"


class AuditResource(Enum):
    """Audit resource types"""
    HOTEL = "hotel"
    GUEST = "guest"
    CONVERSATION = "conversation"
    MESSAGE = "message"
    CONFIGURATION = "configuration"
    USER = "user"
    SYSTEM = "system"
    INTEGRATION = "integration"
    WEBHOOK = "webhook"
    TEMPLATE = "template"
    ANALYTICS = "analytics"


@dataclass
class AuditEntry:
    """Audit log entry"""
    id: str
    timestamp: datetime
    hotel_id: Optional[uuid.UUID]
    hotel_name: Optional[str]
    user_id: Optional[str]
    user_name: Optional[str]
    action: AuditAction
    resource: AuditResource
    resource_id: Optional[str]
    resource_name: Optional[str]
    details: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    session_id: Optional[str]
    correlation_id: Optional[str]
    success: bool
    error_message: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert audit entry to dictionary"""
        data = asdict(self)
        # Convert UUID and datetime to strings
        if data['hotel_id']:
            data['hotel_id'] = str(data['hotel_id'])
        data['timestamp'] = data['timestamp'].isoformat()
        data['action'] = data['action'].value
        data['resource'] = data['resource'].value
        return data
    
    def to_json(self) -> str:
        """Convert audit entry to JSON string"""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Audit logger for tracking hotel operations and changes"""
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize audit logger
        
        Args:
            db: Optional database session for enhanced logging
        """
        self.db = db
        self.logger = logger.bind(service="audit_logger")
    
    def log_audit(
        self,
        action: AuditAction,
        resource: AuditResource,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        hotel_id: Optional[uuid.UUID] = None,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> AuditEntry:
        """
        Log an audit entry
        
        Args:
            action: Audit action
            resource: Resource type
            resource_id: Resource identifier
            resource_name: Resource name
            hotel_id: Hotel UUID (uses current context if not provided)
            user_id: User identifier
            user_name: User name
            details: Additional details
            ip_address: Client IP address
            user_agent: Client user agent
            session_id: Session identifier
            correlation_id: Correlation ID for tracking
            success: Whether operation was successful
            error_message: Error message if operation failed
            
        Returns:
            AuditEntry: Created audit entry
        """
        try:
            # Get hotel context if not provided
            if hotel_id is None:
                hotel_id = get_current_hotel_id()
            
            hotel_name = None
            if hotel_id:
                hotel_name = get_current_hotel_name()
                if not hotel_name and self.db:
                    # Try to get hotel name from database
                    from app.models.hotel import Hotel
                    hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
                    if hotel:
                        hotel_name = hotel.name
            
            # Create audit entry
            audit_entry = AuditEntry(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                hotel_id=hotel_id,
                hotel_name=hotel_name,
                user_id=user_id,
                user_name=user_name,
                action=action,
                resource=resource,
                resource_id=resource_id,
                resource_name=resource_name,
                details=details or {},
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                correlation_id=correlation_id,
                success=success,
                error_message=error_message
            )
            
            # Log the audit entry
            self.logger.info(
                f"Audit: {action.value} {resource.value}",
                audit_entry=audit_entry.to_dict()
            )
            
            # TODO: Store in audit database table or external audit system
            # For now, we're just logging to the application logs
            
            return audit_entry
            
        except Exception as e:
            # Fallback logging if audit logging fails
            self.logger.error(
                "Failed to log audit entry",
                action=action.value if action else None,
                resource=resource.value if resource else None,
                error=str(e)
            )
            # Return a minimal audit entry
            return AuditEntry(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                hotel_id=hotel_id,
                hotel_name=hotel_name,
                user_id=user_id,
                user_name=user_name,
                action=action,
                resource=resource,
                resource_id=resource_id,
                resource_name=resource_name,
                details={},
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id,
                correlation_id=correlation_id,
                success=False,
                error_message=f"Audit logging failed: {str(e)}"
            )
    
    def log_hotel_created(
        self,
        hotel_id: uuid.UUID,
        hotel_name: str,
        created_by: Optional[str] = None,
        created_by_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AuditEntry:
        """Log hotel creation"""
        return self.log_audit(
            action=AuditAction.CREATE,
            resource=AuditResource.HOTEL,
            resource_id=str(hotel_id),
            resource_name=hotel_name,
            hotel_id=hotel_id,
            user_id=created_by,
            user_name=created_by_name,
            details={
                "hotel_name": hotel_name,
                **(details or {})
            },
            **kwargs
        )
    
    def log_hotel_updated(
        self,
        hotel_id: uuid.UUID,
        hotel_name: str,
        updated_by: Optional[str] = None,
        updated_by_name: Optional[str] = None,
        updated_fields: Optional[List[str]] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AuditEntry:
        """Log hotel update"""
        return self.log_audit(
            action=AuditAction.UPDATE,
            resource=AuditResource.HOTEL,
            resource_id=str(hotel_id),
            resource_name=hotel_name,
            hotel_id=hotel_id,
            user_id=updated_by,
            user_name=updated_by_name,
            details={
                "updated_fields": updated_fields or [],
                "old_values": old_values or {},
                "new_values": new_values or {}
            },
            **kwargs
        )
    
    def log_hotel_deleted(
        self,
        hotel_id: uuid.UUID,
        hotel_name: str,
        deleted_by: Optional[str] = None,
        deleted_by_name: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs
    ) -> AuditEntry:
        """Log hotel deletion"""
        return self.log_audit(
            action=AuditAction.DELETE,
            resource=AuditResource.HOTEL,
            resource_id=str(hotel_id),
            resource_name=hotel_name,
            hotel_id=hotel_id,
            user_id=deleted_by,
            user_name=deleted_by_name,
            details={
                "reason": reason,
                "hotel_name": hotel_name
            },
            **kwargs
        )
    
    def log_configuration_changed(
        self,
        hotel_id: uuid.UUID,
        config_section: str,
        changed_by: Optional[str] = None,
        changed_by_name: Optional[str] = None,
        old_config: Optional[Dict[str, Any]] = None,
        new_config: Optional[Dict[str, Any]] = None,
        merge_operation: bool = True,
        **kwargs
    ) -> AuditEntry:
        """Log configuration changes"""
        return self.log_audit(
            action=AuditAction.CONFIGURE,
            resource=AuditResource.CONFIGURATION,
            resource_id=config_section,
            resource_name=f"Hotel Configuration - {config_section}",
            hotel_id=hotel_id,
            user_id=changed_by,
            user_name=changed_by_name,
            details={
                "config_section": config_section,
                "merge_operation": merge_operation,
                "old_config": old_config or {},
                "new_config": new_config or {}
            },
            **kwargs
        )
    
    def log_user_authentication(
        self,
        user_id: str,
        user_name: Optional[str] = None,
        action: AuditAction = AuditAction.LOGIN,
        hotel_id: Optional[uuid.UUID] = None,
        success: bool = True,
        failure_reason: Optional[str] = None,
        **kwargs
    ) -> AuditEntry:
        """Log user authentication events"""
        return self.log_audit(
            action=action,
            resource=AuditResource.USER,
            resource_id=user_id,
            resource_name=user_name,
            hotel_id=hotel_id,
            user_id=user_id,
            user_name=user_name,
            success=success,
            error_message=failure_reason,
            details={
                "authentication_action": action.value,
                "failure_reason": failure_reason
            },
            **kwargs
        )
    
    def log_data_export(
        self,
        hotel_id: uuid.UUID,
        export_type: str,
        exported_by: Optional[str] = None,
        exported_by_name: Optional[str] = None,
        record_count: Optional[int] = None,
        file_format: Optional[str] = None,
        **kwargs
    ) -> AuditEntry:
        """Log data export operations"""
        return self.log_audit(
            action=AuditAction.EXPORT,
            resource=AuditResource.ANALYTICS,
            resource_id=export_type,
            resource_name=f"Data Export - {export_type}",
            hotel_id=hotel_id,
            user_id=exported_by,
            user_name=exported_by_name,
            details={
                "export_type": export_type,
                "record_count": record_count,
                "file_format": file_format
            },
            **kwargs
        )
    
    def log_data_import(
        self,
        hotel_id: uuid.UUID,
        import_type: str,
        imported_by: Optional[str] = None,
        imported_by_name: Optional[str] = None,
        record_count: Optional[int] = None,
        file_format: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        **kwargs
    ) -> AuditEntry:
        """Log data import operations"""
        return self.log_audit(
            action=AuditAction.IMPORT,
            resource=AuditResource.ANALYTICS,
            resource_id=import_type,
            resource_name=f"Data Import - {import_type}",
            hotel_id=hotel_id,
            user_id=imported_by,
            user_name=imported_by_name,
            success=success,
            error_message=error_message,
            details={
                "import_type": import_type,
                "record_count": record_count,
                "file_format": file_format
            },
            **kwargs
        )
    
    def log_integration_event(
        self,
        hotel_id: uuid.UUID,
        integration_name: str,
        event_type: str,
        triggered_by: Optional[str] = None,
        triggered_by_name: Optional[str] = None,
        success: bool = True,
        response_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs
    ) -> AuditEntry:
        """Log integration events"""
        return self.log_audit(
            action=AuditAction.VERIFY if "verify" in event_type else AuditAction.UPDATE,
            resource=AuditResource.INTEGRATION,
            resource_id=integration_name,
            resource_name=f"{integration_name} Integration",
            hotel_id=hotel_id,
            user_id=triggered_by,
            user_name=triggered_by_name,
            success=success,
            error_message=error_message,
            details={
                "integration_name": integration_name,
                "event_type": event_type,
                "response_time_ms": response_time_ms,
                "request_id": request_id
            },
            **kwargs
        )
    
    def log_guest_interaction(
        self,
        hotel_id: uuid.UUID,
        guest_id: uuid.UUID,
        guest_name: Optional[str] = None,
        interaction_type: str = "message",
        staff_member: Optional[str] = None,
        staff_member_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AuditEntry:
        """Log guest interactions"""
        return self.log_audit(
            action=AuditAction.UPDATE,
            resource=AuditResource.GUEST,
            resource_id=str(guest_id),
            resource_name=guest_name,
            hotel_id=hotel_id,
            user_id=staff_member,
            user_name=staff_member_name,
            details={
                "interaction_type": interaction_type,
                **(details or {})
            },
            **kwargs
        )


class AuditQueryBuilder:
    """Builder for querying audit logs"""
    
    def __init__(self):
        """Initialize audit query builder"""
        self.filters = {}
        self.sort_by = "timestamp"
        self.sort_order = "desc"
        self.limit_value = 100
        self.offset_value = 0
    
    def hotel(self, hotel_id: uuid.UUID) -> 'AuditQueryBuilder':
        """Filter by hotel ID"""
        self.filters['hotel_id'] = str(hotel_id)
        return self
    
    def user(self, user_id: str) -> 'AuditQueryBuilder':
        """Filter by user ID"""
        self.filters['user_id'] = user_id
        return self
    
    def action(self, action: AuditAction) -> 'AuditQueryBuilder':
        """Filter by action"""
        self.filters['action'] = action.value
        return self
    
    def resource(self, resource: AuditResource) -> 'AuditQueryBuilder':
        """Filter by resource"""
        self.filters['resource'] = resource.value
        return self
    
    def date_range(self, start: datetime, end: datetime) -> 'AuditQueryBuilder':
        """Filter by date range"""
        self.filters['start_date'] = start.isoformat()
        self.filters['end_date'] = end.isoformat()
        return self
    
    def success_only(self) -> 'AuditQueryBuilder':
        """Filter for successful operations only"""
        self.filters['success'] = True
        return self
    
    def failures_only(self) -> 'AuditQueryBuilder':
        """Filter for failed operations only"""
        self.filters['success'] = False
        return self
    
    def sort(self, field: str, order: str = "desc") -> 'AuditQueryBuilder':
        """Set sort order"""
        self.sort_by = field
        self.sort_order = order
        return self
    
    def limit(self, limit: int) -> 'AuditQueryBuilder':
        """Set result limit"""
        self.limit_value = limit
        return self
    
    def offset(self, offset: int) -> 'AuditQueryBuilder':
        """Set result offset"""
        self.offset_value = offset
        return self
    
    def build_query(self) -> Dict[str, Any]:
        """Build query dictionary"""
        return {
            "filters": self.filters,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
            "limit": self.limit_value,
            "offset": self.offset_value
        }


# Global audit logger instance
_audit_logger_instance = None


def get_audit_logger(db: Optional[Session] = None) -> AuditLogger:
    """
    Get audit logger instance
    
    Args:
        db: Optional database session
        
    Returns:
        AuditLogger: Audit logger instance
    """
    global _audit_logger_instance
    if _audit_logger_instance is None or db is not None:
        _audit_logger_instance = AuditLogger(db)
    return _audit_logger_instance


# Convenience functions for common audit operations
def audit_hotel_created(hotel_id: uuid.UUID, hotel_name: str, **kwargs) -> AuditEntry:
    """Audit hotel creation (convenience function)"""
    audit_logger = get_audit_logger()
    return audit_logger.log_hotel_created(hotel_id, hotel_name, **kwargs)


def audit_hotel_updated(hotel_id: uuid.UUID, hotel_name: str, **kwargs) -> AuditEntry:
    """Audit hotel update (convenience function)"""
    audit_logger = get_audit_logger()
    return audit_logger.log_hotel_updated(hotel_id, hotel_name, **kwargs)


def audit_configuration_changed(hotel_id: uuid.UUID, config_section: str, **kwargs) -> AuditEntry:
    """Audit configuration change (convenience function)"""
    audit_logger = get_audit_logger()
    return audit_logger.log_configuration_changed(hotel_id, config_section, **kwargs)


def create_audit_query() -> AuditQueryBuilder:
    """Create audit query builder (convenience function)"""
    return AuditQueryBuilder()
