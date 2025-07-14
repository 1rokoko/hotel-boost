"""
Advanced logging configuration for the WhatsApp Hotel Bot.

This module provides comprehensive logging setup with multiple handlers,
formatters, and filters for different types of logs.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import structlog
from structlog.typing import Processor

from app.core.config import settings
from app.utils.log_formatters import (
    get_formatter,
    create_structlog_processors,
    JSONFormatter,
    ConsoleFormatter
)
from app.utils.log_filters import (
    create_default_filters,
    create_security_filters,
    create_audit_filters,
    create_error_filters,
    SensitiveDataFilter
)


class AdvancedLoggingConfig:
    """Advanced logging configuration manager"""
    
    def __init__(self):
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self.handlers: Dict[str, logging.Handler] = {}
        self.loggers: Dict[str, logging.Logger] = {}
        
    def setup_logging(self) -> None:
        """Setup comprehensive logging configuration"""
        # Clear existing handlers
        logging.getLogger().handlers.clear()
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        
        # Create handlers
        self._create_console_handler()
        self._create_file_handlers()
        self._create_specialized_handlers()
        
        # Setup structlog
        self._setup_structlog()
        
        # Create specialized loggers
        self._create_specialized_loggers()
        
        logging.info("Advanced logging configuration completed")
        
    def _create_console_handler(self) -> None:
        """Create console handler for development"""
        if settings.ENVIRONMENT == 'development' or settings.DEBUG:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            
            # Use console formatter for development
            formatter = ConsoleFormatter(use_colors=True)
            handler.setFormatter(formatter)
            
            # Add default filters
            for filter_obj in create_default_filters():
                handler.addFilter(filter_obj)
                
            self.handlers['console'] = handler
            logging.getLogger().addHandler(handler)
            
    def _create_file_handlers(self) -> None:
        """Create file handlers for different log types"""
        # Main application log
        self._create_rotating_file_handler(
            name='app',
            filename='app.log',
            level=logging.INFO,
            formatter_type='json'
        )
        
        # Error log
        self._create_rotating_file_handler(
            name='error',
            filename='error.log',
            level=logging.ERROR,
            formatter_type='error',
            filters=create_error_filters()
        )
        
        # Debug log (only in development)
        if settings.DEBUG:
            self._create_rotating_file_handler(
                name='debug',
                filename='debug.log',
                level=logging.DEBUG,
                formatter_type='json'
            )
            
    def _create_specialized_handlers(self) -> None:
        """Create specialized handlers for specific log types"""
        # Security log
        self._create_rotating_file_handler(
            name='security',
            filename='security.log',
            level=logging.WARNING,
            formatter_type='security',
            filters=create_security_filters()
        )
        
        # Audit log
        self._create_rotating_file_handler(
            name='audit',
            filename='audit.log',
            level=logging.INFO,
            formatter_type='audit',
            filters=create_audit_filters()
        )
        
        # API access log
        self._create_rotating_file_handler(
            name='api',
            filename='api.log',
            level=logging.INFO,
            formatter_type='api'
        )
        
        # Database log
        self._create_rotating_file_handler(
            name='database',
            filename='database.log',
            level=logging.INFO,
            formatter_type='database'
        )
        
        # Task log
        self._create_rotating_file_handler(
            name='task',
            filename='task.log',
            level=logging.INFO,
            formatter_type='task'
        )
        
        # Performance log
        self._create_rotating_file_handler(
            name='performance',
            filename='performance.log',
            level=logging.INFO,
            formatter_type='performance'
        )
        
    def _create_rotating_file_handler(
        self,
        name: str,
        filename: str,
        level: int,
        formatter_type: str = 'json',
        filters: Optional[List[logging.Filter]] = None
    ) -> None:
        """Create a rotating file handler"""
        file_path = self.log_dir / filename
        
        handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        handler.setLevel(level)
        
        # Set formatter
        formatter = get_formatter(formatter_type)
        handler.setFormatter(formatter)
        
        # Add filters
        if filters:
            for filter_obj in filters:
                handler.addFilter(filter_obj)
        else:
            # Add default filters
            for filter_obj in create_default_filters():
                handler.addFilter(filter_obj)
                
        self.handlers[name] = handler
        
        # Add to root logger for general logs
        if name in ['app', 'error', 'debug']:
            logging.getLogger().addHandler(handler)
            
    def _setup_structlog(self) -> None:
        """Setup structlog configuration"""
        use_json = settings.LOG_FORMAT == 'json'
        processors = create_structlog_processors(use_json=use_json)
        
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            context_class=dict,
            cache_logger_on_first_use=True,
        )
        
    def _create_specialized_loggers(self) -> None:
        """Create specialized loggers for different components"""
        # Security logger
        security_logger = logging.getLogger('security')
        security_logger.addHandler(self.handlers['security'])
        security_logger.setLevel(logging.WARNING)
        self.loggers['security'] = security_logger
        
        # Audit logger
        audit_logger = logging.getLogger('audit')
        audit_logger.addHandler(self.handlers['audit'])
        audit_logger.setLevel(logging.INFO)
        self.loggers['audit'] = audit_logger
        
        # API logger
        api_logger = logging.getLogger('api')
        api_logger.addHandler(self.handlers['api'])
        api_logger.setLevel(logging.INFO)
        self.loggers['api'] = api_logger
        
        # Database logger
        db_logger = logging.getLogger('database')
        db_logger.addHandler(self.handlers['database'])
        db_logger.setLevel(logging.INFO)
        self.loggers['database'] = db_logger
        
        # Task logger
        task_logger = logging.getLogger('task')
        task_logger.addHandler(self.handlers['task'])
        task_logger.setLevel(logging.INFO)
        self.loggers['task'] = task_logger
        
        # Performance logger
        perf_logger = logging.getLogger('performance')
        perf_logger.addHandler(self.handlers['performance'])
        perf_logger.setLevel(logging.INFO)
        self.loggers['performance'] = perf_logger
        
    def get_logger(self, name: str) -> logging.Logger:
        """Get a specialized logger by name"""
        return self.loggers.get(name, logging.getLogger(name))
        
    def get_structlog_logger(self, name: str) -> structlog.BoundLogger:
        """Get a structlog logger"""
        return structlog.get_logger(name)


# Global instance
_logging_config: Optional[AdvancedLoggingConfig] = None


def setup_advanced_logging() -> AdvancedLoggingConfig:
    """Setup advanced logging and return config instance"""
    global _logging_config
    
    if _logging_config is None:
        _logging_config = AdvancedLoggingConfig()
        _logging_config.setup_logging()
        
    return _logging_config


def get_advanced_logger(name: str) -> logging.Logger:
    """Get an advanced logger instance"""
    if _logging_config is None:
        setup_advanced_logging()
    return _logging_config.get_logger(name)


def get_structlog_logger(name: str) -> structlog.BoundLogger:
    """Get a structlog logger instance"""
    if _logging_config is None:
        setup_advanced_logging()
    return _logging_config.get_structlog_logger(name)


# Convenience functions for different log types
def log_security_event(message: str, **kwargs) -> None:
    """Log a security event"""
    logger = get_advanced_logger('security')
    logger.warning(message, extra={**kwargs, 'log_type': 'security'})


def log_audit_event(message: str, user_id: str, action: str, resource: str, **kwargs) -> None:
    """Log an audit event"""
    logger = get_advanced_logger('audit')
    logger.info(message, extra={
        'log_type': 'audit',
        'user_id': user_id,
        'action': action,
        'resource': resource,
        **kwargs
    })


def log_api_request(method: str, path: str, status_code: int, response_time: float, **kwargs) -> None:
    """Log an API request"""
    logger = get_advanced_logger('api')
    logger.info(f"{method} {path}", extra={
        'log_type': 'api',
        'method': method,
        'path': path,
        'status_code': status_code,
        'response_time': response_time,
        **kwargs
    })


def log_database_operation(operation: str, table: str, query_time: float, **kwargs) -> None:
    """Log a database operation"""
    logger = get_advanced_logger('database')
    logger.info(f"Database {operation} on {table}", extra={
        'log_type': 'database',
        'operation': operation,
        'table': table,
        'query_time': query_time,
        **kwargs
    })


def log_task_execution(task_name: str, task_id: str, execution_time: float, **kwargs) -> None:
    """Log a task execution"""
    logger = get_advanced_logger('task')
    logger.info(f"Task {task_name} executed", extra={
        'log_type': 'task',
        'task_name': task_name,
        'task_id': task_id,
        'execution_time': execution_time,
        **kwargs
    })


def log_performance_metric(operation: str, duration: float, **kwargs) -> None:
    """Log a performance metric"""
    logger = get_advanced_logger('performance')
    logger.info(f"Performance: {operation}", extra={
        'log_type': 'performance',
        'operation': operation,
        'duration': duration,
        **kwargs
    })
