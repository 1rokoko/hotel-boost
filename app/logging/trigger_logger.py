"""
Structured logging for trigger system
"""

import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import structlog

from app.core.logging import get_logger


class TriggerLogLevel(str, Enum):
    """Log levels for trigger events"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TriggerEventType(str, Enum):
    """Types of trigger events to log"""
    TRIGGER_CREATED = "trigger_created"
    TRIGGER_UPDATED = "trigger_updated"
    TRIGGER_DELETED = "trigger_deleted"
    TRIGGER_ACTIVATED = "trigger_activated"
    TRIGGER_DEACTIVATED = "trigger_deactivated"
    
    TRIGGER_SCHEDULED = "trigger_scheduled"
    TRIGGER_CANCELLED = "trigger_cancelled"
    TRIGGER_RESCHEDULED = "trigger_rescheduled"
    
    TRIGGER_EVALUATION_STARTED = "trigger_evaluation_started"
    TRIGGER_EVALUATION_COMPLETED = "trigger_evaluation_completed"
    TRIGGER_CONDITIONS_MET = "trigger_conditions_met"
    TRIGGER_CONDITIONS_NOT_MET = "trigger_conditions_not_met"
    
    TRIGGER_EXECUTION_STARTED = "trigger_execution_started"
    TRIGGER_EXECUTION_COMPLETED = "trigger_execution_completed"
    TRIGGER_EXECUTION_FAILED = "trigger_execution_failed"
    
    TEMPLATE_RENDERING_STARTED = "template_rendering_started"
    TEMPLATE_RENDERING_COMPLETED = "template_rendering_completed"
    TEMPLATE_RENDERING_FAILED = "template_rendering_failed"
    
    MESSAGE_SENDING_STARTED = "message_sending_started"
    MESSAGE_SENDING_COMPLETED = "message_sending_completed"
    MESSAGE_SENDING_FAILED = "message_sending_failed"
    
    BULK_OPERATION_STARTED = "bulk_operation_started"
    BULK_OPERATION_COMPLETED = "bulk_operation_completed"
    
    SYSTEM_ERROR = "system_error"
    PERFORMANCE_WARNING = "performance_warning"


class TriggerLogger:
    """Structured logger for trigger system events"""
    
    def __init__(self, correlation_id: Optional[str] = None):
        """
        Initialize trigger logger
        
        Args:
            correlation_id: Optional correlation ID for tracking related events
        """
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.logger = get_logger(__name__).bind(
            correlation_id=self.correlation_id,
            component="trigger_system"
        )
    
    def log_trigger_event(
        self,
        event_type: TriggerEventType,
        level: TriggerLogLevel = TriggerLogLevel.INFO,
        hotel_id: Optional[str] = None,
        trigger_id: Optional[str] = None,
        guest_id: Optional[str] = None,
        user_id: Optional[str] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        execution_time_ms: Optional[float] = None
    ):
        """
        Log a trigger system event
        
        Args:
            event_type: Type of event
            level: Log level
            hotel_id: Hotel ID
            trigger_id: Trigger ID
            guest_id: Guest ID
            user_id: User ID who initiated the action
            message: Human-readable message
            metadata: Additional metadata
            error: Exception if applicable
            execution_time_ms: Execution time in milliseconds
        """
        log_data = {
            "event_type": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": self.correlation_id
        }
        
        # Add IDs if provided
        if hotel_id:
            log_data["hotel_id"] = hotel_id
        if trigger_id:
            log_data["trigger_id"] = trigger_id
        if guest_id:
            log_data["guest_id"] = guest_id
        if user_id:
            log_data["user_id"] = user_id
        
        # Add performance data
        if execution_time_ms is not None:
            log_data["execution_time_ms"] = execution_time_ms
        
        # Add metadata
        if metadata:
            log_data["metadata"] = metadata
        
        # Add error information
        if error:
            log_data["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": str(error.__traceback__) if error.__traceback__ else None
            }
        
        # Log with appropriate level
        logger_method = getattr(self.logger, level.value)
        logger_method(message or f"Trigger event: {event_type.value}", **log_data)
    
    def log_trigger_creation(
        self,
        hotel_id: str,
        trigger_id: str,
        trigger_name: str,
        trigger_type: str,
        user_id: Optional[str] = None,
        execution_time_ms: Optional[float] = None
    ):
        """Log trigger creation event"""
        self.log_trigger_event(
            event_type=TriggerEventType.TRIGGER_CREATED,
            level=TriggerLogLevel.INFO,
            hotel_id=hotel_id,
            trigger_id=trigger_id,
            user_id=user_id,
            message=f"Trigger '{trigger_name}' created",
            metadata={
                "trigger_name": trigger_name,
                "trigger_type": trigger_type
            },
            execution_time_ms=execution_time_ms
        )
    
    def log_trigger_execution(
        self,
        hotel_id: str,
        trigger_id: str,
        guest_id: Optional[str],
        success: bool,
        execution_time_ms: float,
        rendered_message: Optional[str] = None,
        error: Optional[Exception] = None
    ):
        """Log trigger execution event"""
        event_type = (
            TriggerEventType.TRIGGER_EXECUTION_COMPLETED if success
            else TriggerEventType.TRIGGER_EXECUTION_FAILED
        )
        level = TriggerLogLevel.INFO if success else TriggerLogLevel.ERROR
        
        metadata = {
            "success": success,
            "message_length": len(rendered_message) if rendered_message else 0
        }
        
        if rendered_message:
            # Log first 100 characters of message for debugging
            metadata["message_preview"] = rendered_message[:100]
        
        self.log_trigger_event(
            event_type=event_type,
            level=level,
            hotel_id=hotel_id,
            trigger_id=trigger_id,
            guest_id=guest_id,
            message=f"Trigger execution {'completed' if success else 'failed'}",
            metadata=metadata,
            error=error,
            execution_time_ms=execution_time_ms
        )
    
    def log_trigger_evaluation(
        self,
        hotel_id: str,
        trigger_count: int,
        executable_count: int,
        evaluation_time_ms: float,
        trigger_type: Optional[str] = None
    ):
        """Log trigger evaluation event"""
        self.log_trigger_event(
            event_type=TriggerEventType.TRIGGER_EVALUATION_COMPLETED,
            level=TriggerLogLevel.INFO,
            hotel_id=hotel_id,
            message=f"Evaluated {trigger_count} triggers, {executable_count} executable",
            metadata={
                "trigger_count": trigger_count,
                "executable_count": executable_count,
                "trigger_type": trigger_type
            },
            execution_time_ms=evaluation_time_ms
        )
    
    def log_template_rendering(
        self,
        hotel_id: str,
        trigger_id: str,
        success: bool,
        rendering_time_ms: float,
        template_length: int,
        rendered_length: Optional[int] = None,
        error: Optional[Exception] = None
    ):
        """Log template rendering event"""
        event_type = (
            TriggerEventType.TEMPLATE_RENDERING_COMPLETED if success
            else TriggerEventType.TEMPLATE_RENDERING_FAILED
        )
        level = TriggerLogLevel.INFO if success else TriggerLogLevel.ERROR
        
        metadata = {
            "template_length": template_length,
            "rendered_length": rendered_length or 0
        }
        
        self.log_trigger_event(
            event_type=event_type,
            level=level,
            hotel_id=hotel_id,
            trigger_id=trigger_id,
            message=f"Template rendering {'completed' if success else 'failed'}",
            metadata=metadata,
            error=error,
            execution_time_ms=rendering_time_ms
        )
    
    def log_message_sending(
        self,
        hotel_id: str,
        trigger_id: str,
        guest_id: str,
        phone_number: str,
        success: bool,
        sending_time_ms: float,
        message_length: int,
        error: Optional[Exception] = None
    ):
        """Log message sending event"""
        event_type = (
            TriggerEventType.MESSAGE_SENDING_COMPLETED if success
            else TriggerEventType.MESSAGE_SENDING_FAILED
        )
        level = TriggerLogLevel.INFO if success else TriggerLogLevel.ERROR
        
        # Mask phone number for privacy (show only last 4 digits)
        masked_phone = f"***{phone_number[-4:]}" if len(phone_number) >= 4 else "***"
        
        metadata = {
            "phone_number": masked_phone,
            "message_length": message_length
        }
        
        self.log_trigger_event(
            event_type=event_type,
            level=level,
            hotel_id=hotel_id,
            trigger_id=trigger_id,
            guest_id=guest_id,
            message=f"Message sending {'completed' if success else 'failed'}",
            metadata=metadata,
            error=error,
            execution_time_ms=sending_time_ms
        )
    
    def log_bulk_operation(
        self,
        hotel_id: str,
        operation: str,
        trigger_count: int,
        successful_count: int,
        failed_count: int,
        execution_time_ms: float,
        user_id: Optional[str] = None
    ):
        """Log bulk operation event"""
        self.log_trigger_event(
            event_type=TriggerEventType.BULK_OPERATION_COMPLETED,
            level=TriggerLogLevel.INFO,
            hotel_id=hotel_id,
            user_id=user_id,
            message=f"Bulk {operation} completed: {successful_count}/{trigger_count} successful",
            metadata={
                "operation": operation,
                "trigger_count": trigger_count,
                "successful_count": successful_count,
                "failed_count": failed_count
            },
            execution_time_ms=execution_time_ms
        )
    
    def log_performance_warning(
        self,
        hotel_id: str,
        operation: str,
        execution_time_ms: float,
        threshold_ms: float,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Log performance warning"""
        metadata = {
            "operation": operation,
            "execution_time_ms": execution_time_ms,
            "threshold_ms": threshold_ms,
            "slowdown_factor": execution_time_ms / threshold_ms
        }
        
        if additional_context:
            metadata.update(additional_context)
        
        self.log_trigger_event(
            event_type=TriggerEventType.PERFORMANCE_WARNING,
            level=TriggerLogLevel.WARNING,
            hotel_id=hotel_id,
            message=f"Performance warning: {operation} took {execution_time_ms:.2f}ms (threshold: {threshold_ms}ms)",
            metadata=metadata,
            execution_time_ms=execution_time_ms
        )
    
    def log_system_error(
        self,
        error: Exception,
        operation: str,
        hotel_id: Optional[str] = None,
        trigger_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Log system error"""
        metadata = {
            "operation": operation
        }
        
        if additional_context:
            metadata.update(additional_context)
        
        self.log_trigger_event(
            event_type=TriggerEventType.SYSTEM_ERROR,
            level=TriggerLogLevel.ERROR,
            hotel_id=hotel_id,
            trigger_id=trigger_id,
            message=f"System error in {operation}: {str(error)}",
            metadata=metadata,
            error=error
        )


class TriggerAuditLogger:
    """Audit logger for trigger system compliance and security"""
    
    def __init__(self):
        """Initialize audit logger"""
        self.logger = get_logger("trigger_audit").bind(
            component="trigger_audit"
        )
    
    def log_audit_event(
        self,
        event_type: str,
        hotel_id: str,
        user_id: str,
        resource_id: Optional[str] = None,
        action: str = "",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log audit event for compliance"""
        audit_data = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "hotel_id": hotel_id,
            "user_id": user_id,
            "action": action,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        if resource_id:
            audit_data["resource_id"] = resource_id
        
        if details:
            audit_data["details"] = details
        
        self.logger.info(
            f"Audit: {action} on {event_type}",
            **audit_data
        )


# Global logger instances
def get_trigger_logger(correlation_id: Optional[str] = None) -> TriggerLogger:
    """Get trigger logger instance"""
    return TriggerLogger(correlation_id)


def get_audit_logger() -> TriggerAuditLogger:
    """Get audit logger instance"""
    return TriggerAuditLogger()


# Export logging components
__all__ = [
    'TriggerLogger',
    'TriggerAuditLogger',
    'TriggerLogLevel',
    'TriggerEventType',
    'get_trigger_logger',
    'get_audit_logger'
]
