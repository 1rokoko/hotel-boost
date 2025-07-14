"""
Structured logging configuration for Green API operations
"""

import time
import json
from typing import Dict, Any, Optional, Union
from datetime import datetime
import structlog
from structlog.processors import JSONRenderer
from structlog.stdlib import LoggerFactory, BoundLogger

from app.core.config import settings


class GreenAPILogProcessor:
    """Custom log processor for Green API operations"""
    
    def __init__(self):
        self.start_time = time.time()
    
    def __call__(self, logger, method_name, event_dict):
        """Process log entry for Green API operations"""
        
        # Add timestamp
        event_dict['timestamp'] = datetime.utcnow().isoformat()
        
        # Add service identifier
        event_dict['service'] = 'green_api'
        
        # Add environment
        event_dict['environment'] = settings.ENVIRONMENT
        
        # Add correlation ID if available
        if hasattr(structlog.contextvars, 'get_context'):
            context = structlog.contextvars.get_context()
            if 'correlation_id' in context:
                event_dict['correlation_id'] = context['correlation_id']
        
        # Format Green API specific fields
        if 'green_api_instance_id' in event_dict:
            event_dict['green_api'] = {
                'instance_id': event_dict.pop('green_api_instance_id'),
                'message_id': event_dict.pop('green_api_message_id', None),
                'chat_id': event_dict.pop('chat_id', None),
                'operation': event_dict.pop('operation', None)
            }
        
        # Format request/response data
        if 'request_data' in event_dict:
            event_dict['request'] = self._sanitize_data(event_dict.pop('request_data'))
        
        if 'response_data' in event_dict:
            event_dict['response'] = self._sanitize_data(event_dict.pop('response_data'))
        
        # Format error information
        if 'error' in event_dict:
            error = event_dict['error']
            if isinstance(error, Exception):
                event_dict['error'] = {
                    'type': error.__class__.__name__,
                    'message': str(error),
                    'module': getattr(error, '__module__', None)
                }
        
        # Add performance metrics
        if 'duration' in event_dict:
            event_dict['performance'] = {
                'duration_ms': event_dict.pop('duration'),
                'slow_query': event_dict.get('duration', 0) > 1000  # Mark as slow if > 1s
            }
        
        return event_dict
    
    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize sensitive data from logs"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if key.lower() in ['token', 'password', 'secret', 'key', 'authorization']:
                    sanitized[key] = '***REDACTED***'
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_data(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        else:
            return data


class GreenAPILogger:
    """Specialized logger for Green API operations"""
    
    def __init__(self, logger_name: str = "green_api"):
        self.logger = structlog.get_logger(logger_name)
        self._context = {}
    
    def bind(self, **kwargs) -> 'GreenAPILogger':
        """Bind context to logger"""
        new_logger = GreenAPILogger()
        new_logger.logger = self.logger.bind(**kwargs)
        new_logger._context = {**self._context, **kwargs}
        return new_logger
    
    def with_hotel(self, hotel_id: str) -> 'GreenAPILogger':
        """Add hotel context"""
        return self.bind(hotel_id=hotel_id)
    
    def with_instance(self, instance_id: str) -> 'GreenAPILogger':
        """Add Green API instance context"""
        return self.bind(green_api_instance_id=instance_id)
    
    def with_message(self, message_id: str, chat_id: Optional[str] = None) -> 'GreenAPILogger':
        """Add message context"""
        context = {'green_api_message_id': message_id}
        if chat_id:
            context['chat_id'] = chat_id
        return self.bind(**context)
    
    def with_operation(self, operation: str) -> 'GreenAPILogger':
        """Add operation context"""
        return self.bind(operation=operation)
    
    def log_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        """Log API request"""
        self.logger.info(
            "Green API request",
            method=method,
            url=url,
            request_data=data,
            headers=self._sanitize_headers(headers) if headers else None
        )
    
    def log_response(
        self,
        status_code: int,
        data: Optional[Dict[str, Any]] = None,
        duration: Optional[float] = None
    ):
        """Log API response"""
        level = "info" if 200 <= status_code < 400 else "error"
        
        log_data = {
            "event": "Green API response",
            "status_code": status_code,
            "response_data": data
        }
        
        if duration is not None:
            log_data["duration"] = duration
        
        getattr(self.logger, level)(**log_data)
    
    def log_webhook(
        self,
        webhook_type: str,
        instance_id: str,
        data: Dict[str, Any]
    ):
        """Log webhook receipt"""
        self.logger.info(
            "Webhook received",
            webhook_type=webhook_type,
            green_api_instance_id=instance_id,
            webhook_data=data
        )
    
    def log_message_sent(
        self,
        message_id: str,
        chat_id: str,
        message_type: str,
        success: bool = True
    ):
        """Log message sending"""
        level = "info" if success else "error"
        
        getattr(self.logger, level)(
            "Message sent" if success else "Message send failed",
            green_api_message_id=message_id,
            chat_id=chat_id,
            message_type=message_type,
            operation="send_message"
        )
    
    def log_message_received(
        self,
        message_id: str,
        chat_id: str,
        sender: str,
        message_type: str
    ):
        """Log message receipt"""
        self.logger.info(
            "Message received",
            green_api_message_id=message_id,
            chat_id=chat_id,
            sender=sender,
            message_type=message_type,
            operation="receive_message"
        )
    
    def log_rate_limit(
        self,
        instance_id: str,
        limit_type: str,
        wait_time: float
    ):
        """Log rate limiting"""
        self.logger.warning(
            "Rate limit applied",
            green_api_instance_id=instance_id,
            limit_type=limit_type,
            wait_time=wait_time,
            operation="rate_limit"
        )
    
    def log_error(
        self,
        error: Exception,
        operation: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log error with context"""
        log_data = {
            "event": "Green API error",
            "error": error,
            "operation": operation
        }
        
        if context:
            log_data.update(context)
        
        self.logger.error(**log_data)
    
    def log_retry(
        self,
        attempt: int,
        max_attempts: int,
        delay: float,
        error: Optional[Exception] = None
    ):
        """Log retry attempt"""
        self.logger.warning(
            "Retrying operation",
            attempt=attempt,
            max_attempts=max_attempts,
            delay=delay,
            error=str(error) if error else None,
            operation="retry"
        )
    
    def log_metrics(self, metrics: Dict[str, Any]):
        """Log performance metrics"""
        self.logger.info(
            "Green API metrics",
            metrics=metrics,
            operation="metrics"
        )
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize sensitive headers"""
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in ['authorization', 'x-api-key', 'x-auth-token']:
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = value
        return sanitized


def configure_green_api_logging():
    """Configure structured logging for Green API"""
    
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        GreenAPILogProcessor(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Add JSON renderer for production
    if settings.ENVIRONMENT == "production":
        processors.append(JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=BoundLogger,
        cache_logger_on_first_use=True,
    )


class LoggingContext:
    """Context manager for logging with correlation ID"""
    
    def __init__(self, correlation_id: Optional[str] = None, **context):
        self.correlation_id = correlation_id or self._generate_correlation_id()
        self.context = context
        self.previous_context = None
    
    def __enter__(self):
        """Enter logging context"""
        if hasattr(structlog.contextvars, 'bind_contextvars'):
            self.previous_context = structlog.contextvars.get_context()
            structlog.contextvars.bind_contextvars(
                correlation_id=self.correlation_id,
                **self.context
            )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit logging context"""
        if hasattr(structlog.contextvars, 'clear_contextvars'):
            structlog.contextvars.clear_contextvars()
            if self.previous_context:
                structlog.contextvars.bind_contextvars(**self.previous_context)
    
    def _generate_correlation_id(self) -> str:
        """Generate unique correlation ID"""
        import uuid
        return str(uuid.uuid4())


# Global logger instance
green_api_logger = GreenAPILogger()


def get_green_api_logger(name: str = "green_api") -> GreenAPILogger:
    """Get Green API logger instance"""
    return GreenAPILogger(name)


def log_green_api_operation(operation: str):
    """Decorator for logging Green API operations"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            logger = get_green_api_logger().with_operation(operation)
            start_time = time.time()
            
            try:
                logger.logger.info(f"Starting {operation}")
                result = await func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                logger.logger.info(f"Completed {operation}", duration=duration)
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.log_error(e, operation, {"duration": duration})
                raise
        
        def sync_wrapper(*args, **kwargs):
            logger = get_green_api_logger().with_operation(operation)
            start_time = time.time()
            
            try:
                logger.logger.info(f"Starting {operation}")
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                logger.logger.info(f"Completed {operation}", duration=duration)
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.log_error(e, operation, {"duration": duration})
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Initialize logging configuration
configure_green_api_logging()


# Export main components
__all__ = [
    'GreenAPILogger',
    'GreenAPILogProcessor',
    'LoggingContext',
    'green_api_logger',
    'get_green_api_logger',
    'log_green_api_operation',
    'configure_green_api_logging'
]
