"""
Custom log formatters for structured logging.

This module provides various log formatters for different output formats
and use cases, including JSON, console, and specialized formatters.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import structlog
from pythonjsonlogger import jsonlogger

from app.core.config import settings


class JSONFormatter(jsonlogger.JsonFormatter):
    """Enhanced JSON formatter with additional fields"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to log record"""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp if not present
        if 'timestamp' not in log_record:
            log_record['timestamp'] = datetime.utcnow().isoformat()
            
        # Add service information
        log_record['service'] = 'whatsapp-hotel-bot'
        log_record['version'] = settings.VERSION
        log_record['environment'] = settings.ENVIRONMENT
        
        # Add log level
        if 'level' not in log_record:
            log_record['level'] = record.levelname
            
        # Add logger name
        if 'logger' not in log_record:
            log_record['logger'] = record.name
            
        # Add thread and process info
        log_record['thread_id'] = record.thread
        log_record['process_id'] = record.process
        
        # Add filename and line number for debugging
        if settings.DEBUG:
            log_record['filename'] = record.filename
            log_record['line_number'] = record.lineno
            log_record['function_name'] = record.funcName


class ConsoleFormatter(logging.Formatter):
    """Enhanced console formatter with colors and structured output"""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors and sys.stdout.isatty()
        super().__init__()
        
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output"""
        # Create timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Get color for level
        color = self.COLORS.get(record.levelname, '') if self.use_colors else ''
        reset = self.COLORS['RESET'] if self.use_colors else ''
        
        # Format basic message
        message = f"{timestamp} | {color}{record.levelname:8}{reset} | {record.name} | {record.getMessage()}"
        
        # Add extra fields if present
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'stack_info', 'exc_info', 'exc_text']:
                extra_fields[key] = value
                
        if extra_fields:
            extra_str = ' | '.join(f"{k}={v}" for k, v in extra_fields.items())
            message += f" | {extra_str}"
            
        # Add exception info if present
        if record.exc_info:
            message += '\n' + self.formatException(record.exc_info)
            
        return message


class StructlogFormatter:
    """Structlog processor for consistent formatting"""
    
    def __init__(self, serializer=None):
        self.serializer = serializer or json.dumps
        
    def __call__(self, logger, method_name, event_dict):
        """Process structlog event dictionary"""
        # Ensure timestamp is present
        if 'timestamp' not in event_dict:
            event_dict['timestamp'] = datetime.utcnow().isoformat()
            
        # Add service metadata
        event_dict.setdefault('service', 'whatsapp-hotel-bot')
        event_dict.setdefault('version', settings.VERSION)
        event_dict.setdefault('environment', settings.ENVIRONMENT)
        
        # Add log level
        event_dict.setdefault('level', method_name.upper())
        
        # Add logger name
        event_dict.setdefault('logger', logger.name)
        
        return event_dict


class AuditFormatter(JSONFormatter):
    """Specialized formatter for audit logs"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add audit-specific fields"""
        super().add_fields(log_record, record, message_dict)
        
        # Mark as audit log
        log_record['log_type'] = 'audit'
        
        # Ensure required audit fields
        required_fields = ['user_id', 'action', 'resource']
        for field in required_fields:
            if field not in log_record:
                log_record[field] = getattr(record, field, 'unknown')


class SecurityFormatter(JSONFormatter):
    """Specialized formatter for security logs"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add security-specific fields"""
        super().add_fields(log_record, record, message_dict)
        
        # Mark as security log
        log_record['log_type'] = 'security'
        
        # Add security context
        log_record['security_event'] = True
        
        # Add IP address if available
        if hasattr(record, 'client_ip'):
            log_record['client_ip'] = record.client_ip
            
        # Add user agent if available
        if hasattr(record, 'user_agent'):
            log_record['user_agent'] = record.user_agent


class PerformanceFormatter(JSONFormatter):
    """Specialized formatter for performance logs"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add performance-specific fields"""
        super().add_fields(log_record, record, message_dict)
        
        # Mark as performance log
        log_record['log_type'] = 'performance'
        
        # Add performance metrics
        performance_fields = ['duration', 'memory_usage', 'cpu_usage', 'request_size', 'response_size']
        for field in performance_fields:
            if hasattr(record, field):
                log_record[field] = getattr(record, field)


class ErrorFormatter(JSONFormatter):
    """Specialized formatter for error logs"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add error-specific fields"""
        super().add_fields(log_record, record, message_dict)
        
        # Mark as error log
        log_record['log_type'] = 'error'
        
        # Add error context
        error_fields = ['error_code', 'error_type', 'stack_trace', 'user_id', 'request_id']
        for field in error_fields:
            if hasattr(record, field):
                log_record[field] = getattr(record, field)
                
        # Add exception information
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info) if settings.DEBUG else None
            }


class APIFormatter(JSONFormatter):
    """Specialized formatter for API request/response logs"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add API-specific fields"""
        super().add_fields(log_record, record, message_dict)
        
        # Mark as API log
        log_record['log_type'] = 'api'
        
        # Add API context
        api_fields = [
            'method', 'path', 'status_code', 'response_time', 
            'request_size', 'response_size', 'user_id', 'hotel_id',
            'client_ip', 'user_agent', 'request_id'
        ]
        for field in api_fields:
            if hasattr(record, field):
                log_record[field] = getattr(record, field)


class DatabaseFormatter(JSONFormatter):
    """Specialized formatter for database operation logs"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add database-specific fields"""
        super().add_fields(log_record, record, message_dict)
        
        # Mark as database log
        log_record['log_type'] = 'database'
        
        # Add database context
        db_fields = [
            'operation', 'table', 'query_time', 'rows_affected',
            'connection_id', 'transaction_id', 'hotel_id'
        ]
        for field in db_fields:
            if hasattr(record, field):
                log_record[field] = getattr(record, field)


class TaskFormatter(JSONFormatter):
    """Specialized formatter for Celery task logs"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add task-specific fields"""
        super().add_fields(log_record, record, message_dict)
        
        # Mark as task log
        log_record['log_type'] = 'task'
        
        # Add task context
        task_fields = [
            'task_id', 'task_name', 'task_state', 'retry_count',
            'execution_time', 'queue_name', 'worker_id', 'hotel_id'
        ]
        for field in task_fields:
            if hasattr(record, field):
                log_record[field] = getattr(record, field)


def get_formatter(formatter_type: str = "json", **kwargs) -> logging.Formatter:
    """
    Get a formatter instance by type
    
    Args:
        formatter_type: Type of formatter to create
        **kwargs: Additional arguments for formatter
        
    Returns:
        Formatter instance
    """
    formatters = {
        'json': JSONFormatter,
        'console': ConsoleFormatter,
        'audit': AuditFormatter,
        'security': SecurityFormatter,
        'performance': PerformanceFormatter,
        'error': ErrorFormatter,
        'api': APIFormatter,
        'database': DatabaseFormatter,
        'task': TaskFormatter
    }
    
    formatter_class = formatters.get(formatter_type, JSONFormatter)
    return formatter_class(**kwargs)


def create_structlog_processors(use_json: bool = True) -> list:
    """
    Create structlog processors based on configuration
    
    Args:
        use_json: Whether to use JSON output
        
    Returns:
        List of structlog processors
    """
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        StructlogFormatter(),
    ]
    
    if use_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
        
    return processors
