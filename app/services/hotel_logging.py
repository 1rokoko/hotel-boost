"""
Hotel operations logging service for WhatsApp Hotel Bot application
"""

import uuid
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog

from app.core.logging import get_logger
from app.core.tenant_context import get_current_hotel_id, get_current_hotel_name
from app.models.hotel import Hotel

logger = get_logger(__name__)


class LogLevel(Enum):
    """Log levels for hotel operations"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(Enum):
    """Categories for hotel operation logs"""
    HOTEL_MANAGEMENT = "hotel_management"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    MESSAGING = "messaging"
    GUEST_INTERACTION = "guest_interaction"
    SYSTEM = "system"
    SECURITY = "security"
    PERFORMANCE = "performance"
    INTEGRATION = "integration"


class HotelOperationLogger:
    """Service for logging hotel operations with structured data"""
    
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize hotel operation logger
        
        Args:
            db: Optional database session for enhanced logging
        """
        self.db = db
        self.logger = logger.bind(service="hotel_operation_logger")
    
    def log_operation(
        self,
        operation: str,
        category: LogCategory,
        level: LogLevel = LogLevel.INFO,
        hotel_id: Optional[uuid.UUID] = None,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Log a hotel operation with structured data
        
        Args:
            operation: Operation name/description
            category: Log category
            level: Log level
            hotel_id: Hotel UUID (uses current context if not provided)
            user_id: User identifier
            details: Operation details
            metadata: Additional metadata
            correlation_id: Correlation ID for tracking
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
                    hotel = self.db.query(Hotel).filter(Hotel.id == hotel_id).first()
                    if hotel:
                        hotel_name = hotel.name
            
            # Prepare log data
            log_data = {
                "operation": operation,
                "category": category.value,
                "level": level.value,
                "timestamp": datetime.utcnow().isoformat(),
                "hotel_id": str(hotel_id) if hotel_id else None,
                "hotel_name": hotel_name,
                "user_id": user_id,
                "correlation_id": correlation_id,
                "details": details or {},
                "metadata": metadata or {}
            }
            
            # Log using structlog
            log_method = getattr(self.logger, level.value)
            log_method(
                f"Hotel Operation: {operation}",
                **log_data
            )
            
        except Exception as e:
            # Fallback logging if structured logging fails
            self.logger.error(
                "Failed to log hotel operation",
                operation=operation,
                error=str(e)
            )
    
    def log_hotel_created(
        self,
        hotel_id: uuid.UUID,
        hotel_name: str,
        created_by: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log hotel creation"""
        self.log_operation(
            operation="hotel_created",
            category=LogCategory.HOTEL_MANAGEMENT,
            level=LogLevel.INFO,
            hotel_id=hotel_id,
            user_id=created_by,
            details={
                "hotel_name": hotel_name,
                **(details or {})
            }
        )
    
    def log_hotel_updated(
        self,
        hotel_id: uuid.UUID,
        updated_fields: List[str],
        updated_by: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log hotel update"""
        self.log_operation(
            operation="hotel_updated",
            category=LogCategory.HOTEL_MANAGEMENT,
            level=LogLevel.INFO,
            hotel_id=hotel_id,
            user_id=updated_by,
            details={
                "updated_fields": updated_fields,
                "old_values": old_values or {},
                "new_values": new_values or {}
            }
        )
    
    def log_hotel_deleted(
        self,
        hotel_id: uuid.UUID,
        hotel_name: str,
        deleted_by: Optional[str] = None,
        reason: Optional[str] = None
    ) -> None:
        """Log hotel deletion"""
        self.log_operation(
            operation="hotel_deleted",
            category=LogCategory.HOTEL_MANAGEMENT,
            level=LogLevel.WARNING,
            hotel_id=hotel_id,
            user_id=deleted_by,
            details={
                "hotel_name": hotel_name,
                "reason": reason
            }
        )
    
    def log_configuration_changed(
        self,
        hotel_id: uuid.UUID,
        config_section: str,
        changed_by: Optional[str] = None,
        old_config: Optional[Dict[str, Any]] = None,
        new_config: Optional[Dict[str, Any]] = None,
        merge_operation: bool = True
    ) -> None:
        """Log configuration changes"""
        self.log_operation(
            operation="configuration_changed",
            category=LogCategory.CONFIGURATION,
            level=LogLevel.INFO,
            hotel_id=hotel_id,
            user_id=changed_by,
            details={
                "config_section": config_section,
                "merge_operation": merge_operation,
                "old_config": old_config or {},
                "new_config": new_config or {}
            }
        )
    
    def log_validation_result(
        self,
        hotel_id: uuid.UUID,
        validation_type: str,
        is_valid: bool,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        validated_by: Optional[str] = None
    ) -> None:
        """Log validation results"""
        level = LogLevel.INFO if is_valid else LogLevel.WARNING
        
        self.log_operation(
            operation="validation_performed",
            category=LogCategory.VALIDATION,
            level=level,
            hotel_id=hotel_id,
            user_id=validated_by,
            details={
                "validation_type": validation_type,
                "is_valid": is_valid,
                "errors": errors or [],
                "warnings": warnings or []
            }
        )
    
    def log_authentication_event(
        self,
        hotel_id: uuid.UUID,
        event_type: str,
        success: bool,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None
    ) -> None:
        """Log authentication events"""
        level = LogLevel.INFO if success else LogLevel.WARNING
        
        self.log_operation(
            operation=f"authentication_{event_type}",
            category=LogCategory.AUTHENTICATION,
            level=level,
            hotel_id=hotel_id,
            user_id=user_id,
            details={
                "event_type": event_type,
                "success": success,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "failure_reason": failure_reason
            }
        )
    
    def log_message_event(
        self,
        hotel_id: uuid.UUID,
        event_type: str,
        message_id: Optional[str] = None,
        guest_phone: Optional[str] = None,
        message_type: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """Log messaging events"""
        level = LogLevel.INFO if success else LogLevel.ERROR
        
        self.log_operation(
            operation=f"message_{event_type}",
            category=LogCategory.MESSAGING,
            level=level,
            hotel_id=hotel_id,
            details={
                "event_type": event_type,
                "message_id": message_id,
                "guest_phone": guest_phone,
                "message_type": message_type,
                "success": success,
                "error_message": error_message
            }
        )
    
    def log_guest_interaction(
        self,
        hotel_id: uuid.UUID,
        interaction_type: str,
        guest_id: Optional[uuid.UUID] = None,
        guest_phone: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log guest interactions"""
        self.log_operation(
            operation=f"guest_{interaction_type}",
            category=LogCategory.GUEST_INTERACTION,
            level=LogLevel.INFO,
            hotel_id=hotel_id,
            details={
                "interaction_type": interaction_type,
                "guest_id": str(guest_id) if guest_id else None,
                "guest_phone": guest_phone,
                **(details or {})
            }
        )
    
    def log_system_event(
        self,
        event_type: str,
        level: LogLevel = LogLevel.INFO,
        hotel_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Log system events"""
        self.log_operation(
            operation=f"system_{event_type}",
            category=LogCategory.SYSTEM,
            level=level,
            hotel_id=hotel_id,
            details={
                "event_type": event_type,
                "error_message": error_message,
                **(details or {})
            }
        )
    
    def log_security_event(
        self,
        hotel_id: uuid.UUID,
        event_type: str,
        severity: LogLevel = LogLevel.WARNING,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log security events"""
        self.log_operation(
            operation=f"security_{event_type}",
            category=LogCategory.SECURITY,
            level=severity,
            hotel_id=hotel_id,
            user_id=user_id,
            details={
                "event_type": event_type,
                "ip_address": ip_address,
                **(details or {})
            }
        )
    
    def log_performance_metric(
        self,
        hotel_id: uuid.UUID,
        metric_name: str,
        metric_value: Union[int, float],
        metric_unit: str,
        operation: Optional[str] = None,
        threshold_exceeded: bool = False
    ) -> None:
        """Log performance metrics"""
        level = LogLevel.WARNING if threshold_exceeded else LogLevel.INFO
        
        self.log_operation(
            operation=f"performance_{metric_name}",
            category=LogCategory.PERFORMANCE,
            level=level,
            hotel_id=hotel_id,
            details={
                "metric_name": metric_name,
                "metric_value": metric_value,
                "metric_unit": metric_unit,
                "operation": operation,
                "threshold_exceeded": threshold_exceeded
            }
        )
    
    def log_integration_event(
        self,
        hotel_id: uuid.UUID,
        integration_name: str,
        event_type: str,
        success: bool = True,
        response_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> None:
        """Log integration events"""
        level = LogLevel.INFO if success else LogLevel.ERROR
        
        self.log_operation(
            operation=f"integration_{integration_name}_{event_type}",
            category=LogCategory.INTEGRATION,
            level=level,
            hotel_id=hotel_id,
            details={
                "integration_name": integration_name,
                "event_type": event_type,
                "success": success,
                "response_time_ms": response_time_ms,
                "error_message": error_message,
                "request_id": request_id
            }
        )


class HotelLogAnalyzer:
    """Analyzer for hotel operation logs"""
    
    def __init__(self):
        """Initialize log analyzer"""
        self.logger = logger.bind(service="hotel_log_analyzer")
    
    def analyze_hotel_activity(
        self,
        hotel_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        categories: Optional[List[LogCategory]] = None
    ) -> Dict[str, Any]:
        """
        Analyze hotel activity for a time period
        
        Args:
            hotel_id: Hotel UUID
            start_time: Start of analysis period
            end_time: End of analysis period
            categories: Optional list of categories to analyze
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        # This would typically query a log storage system
        # For now, return a placeholder structure
        return {
            "hotel_id": str(hotel_id),
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "summary": {
                "total_operations": 0,
                "operations_by_category": {},
                "operations_by_level": {},
                "error_rate": 0.0,
                "most_common_operations": []
            },
            "trends": {
                "hourly_activity": [],
                "error_patterns": [],
                "performance_metrics": {}
            },
            "alerts": []
        }


# Global logger instance
_hotel_logger_instance = None


def get_hotel_logger(db: Optional[Session] = None) -> HotelOperationLogger:
    """
    Get hotel operation logger instance
    
    Args:
        db: Optional database session
        
    Returns:
        HotelOperationLogger: Logger instance
    """
    global _hotel_logger_instance
    if _hotel_logger_instance is None or db is not None:
        _hotel_logger_instance = HotelOperationLogger(db)
    return _hotel_logger_instance


# Convenience functions for common logging operations
def log_hotel_operation(
    operation: str,
    category: LogCategory,
    level: LogLevel = LogLevel.INFO,
    **kwargs
) -> None:
    """Log hotel operation (convenience function)"""
    logger_instance = get_hotel_logger()
    logger_instance.log_operation(operation, category, level, **kwargs)


def log_hotel_created(hotel_id: uuid.UUID, hotel_name: str, **kwargs) -> None:
    """Log hotel creation (convenience function)"""
    logger_instance = get_hotel_logger()
    logger_instance.log_hotel_created(hotel_id, hotel_name, **kwargs)


def log_hotel_updated(hotel_id: uuid.UUID, updated_fields: List[str], **kwargs) -> None:
    """Log hotel update (convenience function)"""
    logger_instance = get_hotel_logger()
    logger_instance.log_hotel_updated(hotel_id, updated_fields, **kwargs)


def log_configuration_changed(hotel_id: uuid.UUID, config_section: str, **kwargs) -> None:
    """Log configuration change (convenience function)"""
    logger_instance = get_hotel_logger()
    logger_instance.log_configuration_changed(hotel_id, config_section, **kwargs)
