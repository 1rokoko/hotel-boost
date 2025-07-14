"""
Structured logging configuration for WhatsApp Hotel Bot
"""

import logging
import logging.config
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings

# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

def add_correlation_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add correlation ID to log entries"""
    corr_id = correlation_id.get()
    if corr_id:
        event_dict['correlation_id'] = corr_id
    return event_dict

def add_service_info(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add service information to log entries"""
    event_dict.update({
        'service': 'whatsapp-hotel-bot',
        'version': settings.VERSION,
        'environment': settings.ENVIRONMENT
    })
    return event_dict

def add_timestamp(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add ISO timestamp to log entries"""
    import datetime
    event_dict['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
    return event_dict

def setup_logging() -> None:
    """Configure structured logging"""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper())
    )
    
    # Configure structlog processors
    processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        add_service_info,
        add_correlation_id,
        add_timestamp,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Add appropriate renderer based on environment
    if settings.LOG_FORMAT == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a configured logger instance"""
    return structlog.get_logger(name)

def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """Set correlation ID for request tracing"""
    if corr_id is None:
        corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    return corr_id

def get_correlation_id() -> Optional[str]:
    """Get current correlation ID"""
    return correlation_id.get()

class LoggerMixin:
    """Mixin to add logging capabilities to classes"""
    
    @property
    def logger(self) -> structlog.BoundLogger:
        """Get logger for this class"""
        return get_logger(self.__class__.__name__)

# Database logging configuration
DATABASE_LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'database': {
            'level': 'DEBUG' if settings.DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'sqlalchemy.engine': {
            'handlers': ['database'],
            'level': 'DEBUG' if settings.DEBUG else 'WARNING',
            'propagate': False,
        },
        'sqlalchemy.pool': {
            'handlers': ['database'],
            'level': 'DEBUG' if settings.DEBUG else 'WARNING',
            'propagate': False,
        },
    }
}

def setup_database_logging() -> None:
    """Setup database-specific logging"""
    logging.config.dictConfig(DATABASE_LOG_CONFIG)

# Performance logging utilities
class PerformanceLogger:
    """Logger for performance metrics"""
    
    def __init__(self, operation: str):
        self.operation = operation
        self.logger = get_logger("performance")
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        self.logger.debug("Operation started", operation=self.operation)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        if self.start_time:
            duration = (time.time() - self.start_time) * 1000  # Convert to ms
            self.logger.info(
                "Operation completed",
                operation=self.operation,
                duration_ms=round(duration, 2),
                success=exc_type is None
            )
            if exc_type:
                self.logger.error(
                    "Operation failed",
                    operation=self.operation,
                    error=str(exc_val),
                    error_type=exc_type.__name__
                )

# Initialize logging on module import
setup_logging()
setup_database_logging()
