"""
Task logging utilities for Celery tasks
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, Optional, Union
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class TaskLogger:
    """Utility class for logging task execution details"""
    
    def __init__(self):
        self.logger = structlog.get_logger("celery.tasks")
    
    def log_task_start(self, task_id: str, task_name: str, args: tuple, kwargs: dict) -> None:
        """Log task start"""
        self.logger.info(
            "Task started",
            task_id=task_id,
            task_name=task_name,
            args=self._sanitize_args(args),
            kwargs=self._sanitize_kwargs(kwargs),
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_task_success(self, task_id: str, task_name: str, result: Any, 
                        args: tuple, kwargs: dict) -> None:
        """Log task success"""
        self.logger.info(
            "Task completed successfully",
            task_id=task_id,
            task_name=task_name,
            result_type=type(result).__name__,
            result_size=len(str(result)) if result else 0,
            args=self._sanitize_args(args),
            kwargs=self._sanitize_kwargs(kwargs),
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_task_failure(self, task_id: str, task_name: str, error: str, 
                        traceback: str, args: tuple, kwargs: dict) -> None:
        """Log task failure"""
        self.logger.error(
            "Task failed",
            task_id=task_id,
            task_name=task_name,
            error=error,
            traceback=traceback if settings.DEBUG else None,
            args=self._sanitize_args(args),
            kwargs=self._sanitize_kwargs(kwargs),
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_task_retry(self, task_id: str, task_name: str, error: str, 
                      retry_count: int, args: tuple, kwargs: dict) -> None:
        """Log task retry"""
        self.logger.warning(
            "Task retrying",
            task_id=task_id,
            task_name=task_name,
            error=error,
            retry_count=retry_count,
            args=self._sanitize_args(args),
            kwargs=self._sanitize_kwargs(kwargs),
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_task_timing(self, task_id: str, task_name: str, execution_time: float) -> None:
        """Log task execution timing"""
        self.logger.info(
            "Task execution timing",
            task_id=task_id,
            task_name=task_name,
            execution_time=execution_time,
            execution_time_ms=execution_time * 1000,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_task_progress(self, task_id: str, task_name: str, progress: int, 
                         total: int, message: str = None) -> None:
        """Log task progress"""
        self.logger.info(
            "Task progress",
            task_id=task_id,
            task_name=task_name,
            progress=progress,
            total=total,
            percentage=round((progress / total) * 100, 2) if total > 0 else 0,
            message=message,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_task_custom(self, task_id: str, task_name: str, event: str, 
                       data: Dict[str, Any] = None) -> None:
        """Log custom task event"""
        log_data = {
            "task_id": task_id,
            "task_name": task_name,
            "event": event,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if data:
            log_data.update(self._sanitize_kwargs(data))
        
        self.logger.info("Task custom event", **log_data)
    
    def _sanitize_args(self, args: tuple) -> list:
        """Sanitize task arguments for logging"""
        if not args:
            return []
        
        sanitized = []
        for arg in args:
            sanitized.append(self._sanitize_value(arg))
        
        return sanitized
    
    def _sanitize_kwargs(self, kwargs: dict) -> dict:
        """Sanitize task keyword arguments for logging"""
        if not kwargs:
            return {}
        
        sanitized = {}
        sensitive_keys = {
            'password', 'token', 'api_key', 'secret', 'auth', 'authorization',
            'green_api_token', 'deepseek_api_key', 'smtp_password'
        }
        
        for key, value in kwargs.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = self._sanitize_value(value)
        
        return sanitized
    
    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize individual values for logging"""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        elif isinstance(value, dict):
            return self._sanitize_kwargs(value)
        elif isinstance(value, (list, tuple)):
            return [self._sanitize_value(item) for item in value]
        else:
            # For complex objects, just return their type
            return f"<{type(value).__name__}>"


class TaskMetrics:
    """Utility class for collecting task metrics"""
    
    def __init__(self):
        self.logger = structlog.get_logger("celery.metrics")
    
    def record_task_duration(self, task_name: str, duration: float) -> None:
        """Record task execution duration"""
        self.logger.info(
            "Task duration metric",
            task_name=task_name,
            duration=duration,
            metric_type="duration",
            timestamp=datetime.utcnow().isoformat()
        )
    
    def record_task_count(self, task_name: str, status: str) -> None:
        """Record task count by status"""
        self.logger.info(
            "Task count metric",
            task_name=task_name,
            status=status,
            metric_type="count",
            timestamp=datetime.utcnow().isoformat()
        )
    
    def record_queue_size(self, queue_name: str, size: int) -> None:
        """Record queue size"""
        self.logger.info(
            "Queue size metric",
            queue_name=queue_name,
            size=size,
            metric_type="queue_size",
            timestamp=datetime.utcnow().isoformat()
        )
    
    def record_worker_count(self, worker_count: int) -> None:
        """Record active worker count"""
        self.logger.info(
            "Worker count metric",
            worker_count=worker_count,
            metric_type="worker_count",
            timestamp=datetime.utcnow().isoformat()
        )


class TaskAuditLogger:
    """Audit logger for sensitive task operations"""
    
    def __init__(self):
        self.logger = structlog.get_logger("celery.audit")
    
    def log_sensitive_operation(self, task_id: str, task_name: str, 
                               operation: str, hotel_id: Optional[int] = None,
                               user_id: Optional[int] = None, 
                               details: Optional[Dict[str, Any]] = None) -> None:
        """Log sensitive task operations for audit purposes"""
        audit_data = {
            "task_id": task_id,
            "task_name": task_name,
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat(),
            "audit_type": "task_operation"
        }
        
        if hotel_id:
            audit_data["hotel_id"] = hotel_id
        
        if user_id:
            audit_data["user_id"] = user_id
        
        if details:
            audit_data["details"] = self._sanitize_audit_details(details)
        
        self.logger.info("Task audit log", **audit_data)
    
    def _sanitize_audit_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize audit details"""
        sanitized = {}
        sensitive_keys = {'password', 'token', 'api_key', 'secret'}
        
        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = str(value)[:100]  # Limit length
        
        return sanitized


# Global instances
task_logger = TaskLogger()
task_metrics = TaskMetrics()
task_audit_logger = TaskAuditLogger()

class TaskPerformanceLogger:
    """Logger for task performance analysis"""

    def __init__(self):
        self.logger = structlog.get_logger("celery.performance")

    def log_slow_task(self, task_name: str, duration: float,
                     threshold: float = 30.0, **context) -> None:
        """Log slow task execution"""
        if duration > threshold:
            self.logger.warning(
                "Slow task detected",
                task_name=task_name,
                duration=duration,
                threshold=threshold,
                performance_issue=True,
                **context,
                timestamp=datetime.utcnow().isoformat()
            )

    def log_memory_usage(self, task_name: str, memory_mb: float,
                        peak_memory_mb: float = None, **context) -> None:
        """Log task memory usage"""
        self.logger.info(
            "Task memory usage",
            task_name=task_name,
            memory_mb=memory_mb,
            peak_memory_mb=peak_memory_mb,
            **context,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_resource_usage(self, task_name: str, cpu_percent: float = None,
                          memory_mb: float = None, io_operations: int = None,
                          **context) -> None:
        """Log comprehensive resource usage"""
        resource_data = {
            "task_name": task_name,
            "timestamp": datetime.utcnow().isoformat()
        }

        if cpu_percent is not None:
            resource_data["cpu_percent"] = cpu_percent
        if memory_mb is not None:
            resource_data["memory_mb"] = memory_mb
        if io_operations is not None:
            resource_data["io_operations"] = io_operations

        resource_data.update(context)

        self.logger.info("Task resource usage", **resource_data)


class TaskBusinessLogger:
    """Logger for business-specific task events"""

    def __init__(self):
        self.logger = structlog.get_logger("celery.business")

    def log_hotel_operation(self, task_name: str, hotel_id: int,
                           operation: str, **details) -> None:
        """Log hotel-specific operations"""
        self.logger.info(
            "Hotel operation",
            task_name=task_name,
            hotel_id=hotel_id,
            operation=operation,
            **details,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_guest_interaction(self, task_name: str, hotel_id: int,
                             guest_phone: str, interaction_type: str,
                             **details) -> None:
        """Log guest interaction events"""
        # Mask phone number for privacy
        masked_phone = guest_phone[:3] + "****" + guest_phone[-2:] if len(guest_phone) > 5 else "****"

        self.logger.info(
            "Guest interaction",
            task_name=task_name,
            hotel_id=hotel_id,
            guest_phone_masked=masked_phone,
            interaction_type=interaction_type,
            **details,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_sentiment_analysis(self, task_name: str, hotel_id: int,
                              sentiment_score: float, confidence: float,
                              **details) -> None:
        """Log sentiment analysis results"""
        self.logger.info(
            "Sentiment analysis",
            task_name=task_name,
            hotel_id=hotel_id,
            sentiment_score=sentiment_score,
            confidence=confidence,
            sentiment_category=self._categorize_sentiment(sentiment_score),
            **details,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_trigger_execution(self, task_name: str, hotel_id: int,
                             trigger_id: int, trigger_type: str,
                             execution_result: str, **details) -> None:
        """Log trigger execution events"""
        self.logger.info(
            "Trigger execution",
            task_name=task_name,
            hotel_id=hotel_id,
            trigger_id=trigger_id,
            trigger_type=trigger_type,
            execution_result=execution_result,
            **details,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_notification_sent(self, task_name: str, hotel_id: int,
                             notification_type: str, recipient: str,
                             success: bool, **details) -> None:
        """Log notification sending events"""
        # Mask email/phone for privacy
        if "@" in recipient:
            masked_recipient = recipient.split("@")[0][:3] + "***@" + recipient.split("@")[1]
        else:
            masked_recipient = recipient[:3] + "****" + recipient[-2:] if len(recipient) > 5 else "****"

        self.logger.info(
            "Notification sent",
            task_name=task_name,
            hotel_id=hotel_id,
            notification_type=notification_type,
            recipient_masked=masked_recipient,
            success=success,
            **details,
            timestamp=datetime.utcnow().isoformat()
        )

    def _categorize_sentiment(self, score: float) -> str:
        """Categorize sentiment score"""
        if score >= 0.5:
            return "positive"
        elif score <= -0.5:
            return "negative"
        else:
            return "neutral"


class TaskErrorLogger:
    """Specialized logger for task errors and debugging"""

    def __init__(self):
        self.logger = structlog.get_logger("celery.errors")

    def log_api_error(self, task_name: str, api_name: str, error_code: str,
                     error_message: str, **context) -> None:
        """Log external API errors"""
        self.logger.error(
            "External API error",
            task_name=task_name,
            api_name=api_name,
            error_code=error_code,
            error_message=error_message,
            **context,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_database_error(self, task_name: str, operation: str,
                          error_type: str, error_message: str,
                          **context) -> None:
        """Log database operation errors"""
        self.logger.error(
            "Database error",
            task_name=task_name,
            operation=operation,
            error_type=error_type,
            error_message=error_message,
            **context,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_validation_error(self, task_name: str, field: str,
                           value: str, validation_rule: str,
                           **context) -> None:
        """Log validation errors"""
        self.logger.warning(
            "Validation error",
            task_name=task_name,
            field=field,
            value=value[:50] + "..." if len(str(value)) > 50 else str(value),
            validation_rule=validation_rule,
            **context,
            timestamp=datetime.utcnow().isoformat()
        )

    def log_configuration_error(self, task_name: str, config_key: str,
                               error_message: str, **context) -> None:
        """Log configuration errors"""
        self.logger.error(
            "Configuration error",
            task_name=task_name,
            config_key=config_key,
            error_message=error_message,
            **context,
            timestamp=datetime.utcnow().isoformat()
        )


# Global instances
task_logger = TaskLogger()
task_metrics = TaskMetrics()
task_audit_logger = TaskAuditLogger()
task_performance_logger = TaskPerformanceLogger()
task_business_logger = TaskBusinessLogger()
task_error_logger = TaskErrorLogger()

# Export all components
__all__ = [
    'TaskLogger',
    'TaskMetrics',
    'TaskAuditLogger',
    'TaskPerformanceLogger',
    'TaskBusinessLogger',
    'TaskErrorLogger',
    'task_logger',
    'task_metrics',
    'task_audit_logger',
    'task_performance_logger',
    'task_business_logger',
    'task_error_logger'
]
