"""
Celery logging configuration and utilities
"""

import logging
import sys
from typing import Dict, Any, Optional
from datetime import datetime
import structlog
from celery.signals import (
    task_prerun, task_postrun, task_retry, task_failure, task_success,
    worker_ready, worker_shutdown, worker_process_init
)

from app.core.config import settings
from app.utils.task_logger import task_logger, task_metrics, task_audit_logger

logger = structlog.get_logger(__name__)


class CeleryLogHandler(logging.Handler):
    """Custom log handler for Celery tasks"""
    
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.structlog_logger = structlog.get_logger("celery.handler")
    
    def emit(self, record):
        """Emit a log record using structlog"""
        try:
            # Convert log record to structured format
            log_data = {
                'level': record.levelname,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Add extra fields if present
            if hasattr(record, 'task_id'):
                log_data['task_id'] = record.task_id
            if hasattr(record, 'task_name'):
                log_data['task_name'] = record.task_name
            if hasattr(record, 'hotel_id'):
                log_data['hotel_id'] = record.hotel_id
            
            # Log with appropriate level
            if record.levelno >= logging.ERROR:
                self.structlog_logger.error("Celery log", **log_data)
            elif record.levelno >= logging.WARNING:
                self.structlog_logger.warning("Celery log", **log_data)
            elif record.levelno >= logging.INFO:
                self.structlog_logger.info("Celery log", **log_data)
            else:
                self.structlog_logger.debug("Celery log", **log_data)
                
        except Exception:
            self.handleError(record)


class CeleryTaskLogger:
    """Enhanced task logger with context awareness"""
    
    def __init__(self):
        self.logger = structlog.get_logger("celery.tasks")
        self.current_context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Set logging context for current task"""
        self.current_context.update(kwargs)
    
    def clear_context(self):
        """Clear logging context"""
        self.current_context.clear()
    
    def log_with_context(self, level: str, message: str, **kwargs):
        """Log message with current context"""
        log_data = self.current_context.copy()
        log_data.update(kwargs)
        log_data['timestamp'] = datetime.utcnow().isoformat()
        
        getattr(self.logger, level)(message, **log_data)
    
    def info(self, message: str, **kwargs):
        """Log info message with context"""
        self.log_with_context('info', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        self.log_with_context('warning', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with context"""
        self.log_with_context('error', message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context"""
        self.log_with_context('debug', message, **kwargs)


# Global task logger instance
celery_task_logger = CeleryTaskLogger()


def setup_celery_logging():
    """Setup Celery logging configuration"""
    
    # Configure Celery logger
    celery_logger = logging.getLogger('celery')
    celery_logger.setLevel(logging.INFO if settings.ENVIRONMENT == 'production' else logging.DEBUG)
    
    # Add custom handler
    handler = CeleryLogHandler()
    formatter = logging.Formatter(
        '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    )
    handler.setFormatter(formatter)
    celery_logger.addHandler(handler)
    
    # Configure task logger
    task_logger_instance = logging.getLogger('celery.task')
    task_logger_instance.setLevel(logging.DEBUG)
    task_logger_instance.addHandler(handler)
    
    # Configure worker logger
    worker_logger = logging.getLogger('celery.worker')
    worker_logger.setLevel(logging.INFO)
    worker_logger.addHandler(handler)
    
    logger.info("Celery logging configured", 
                environment=settings.ENVIRONMENT,
                log_level=celery_logger.level)


# Signal handlers for task lifecycle logging
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task prerun signal"""
    task_name = task.name if task else sender
    hotel_id = kwargs.get('hotel_id') if kwargs else None
    
    # Set logging context
    celery_task_logger.set_context(
        task_id=task_id,
        task_name=task_name,
        hotel_id=hotel_id
    )
    
    # Log task start
    task_logger.log_task_start(
        task_id=task_id,
        task_name=task_name,
        args=args or (),
        kwargs=kwargs or {}
    )
    
    # Record metrics
    queue = getattr(task, 'queue', 'default') if task else 'default'
    task_metrics.record_task_count(task_name, 'started')
    
    celery_task_logger.info(
        "Task started",
        args_count=len(args) if args else 0,
        kwargs_keys=list(kwargs.keys()) if kwargs else [],
        queue=queue
    )


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, 
                        kwargs=None, retval=None, state=None, **kwds):
    """Handle task postrun signal"""
    task_name = task.name if task else sender
    hotel_id = kwargs.get('hotel_id') if kwargs else None
    
    if state == 'SUCCESS':
        task_logger.log_task_success(
            task_id=task_id,
            task_name=task_name,
            result=retval,
            args=args or (),
            kwargs=kwargs or {}
        )
        
        task_metrics.record_task_count(task_name, 'success')
        
        celery_task_logger.info(
            "Task completed successfully",
            state=state,
            result_type=type(retval).__name__ if retval else None
        )
    
    elif state == 'FAILURE':
        error_type = type(retval).__name__ if retval else 'Unknown'
        
        task_logger.log_task_failure(
            task_id=task_id,
            task_name=task_name,
            error=str(retval) if retval else 'Unknown error',
            traceback='',  # Would need to capture from exception info
            args=args or (),
            kwargs=kwargs or {}
        )
        
        task_metrics.record_task_count(task_name, 'failed')
        
        celery_task_logger.error(
            "Task failed",
            state=state,
            error=str(retval) if retval else 'Unknown error',
            error_type=error_type
        )
    
    # Clear logging context
    celery_task_logger.clear_context()


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwds):
    """Handle task retry signal"""
    task_name = sender.name if sender else 'unknown'
    
    task_logger.log_task_retry(
        task_id=task_id,
        task_name=task_name,
        error=str(reason) if reason else 'Unknown reason',
        retry_count=getattr(sender.request, 'retries', 0) if sender else 0,
        args=(),
        kwargs={}
    )
    
    task_metrics.record_task_count(task_name, 'retry')
    
    celery_task_logger.warning(
        "Task retrying",
        reason=str(reason) if reason else 'Unknown reason',
        retry_count=getattr(sender.request, 'retries', 0) if sender else 0
    )


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, 
                        traceback=None, einfo=None, **kwds):
    """Handle task failure signal"""
    task_name = sender.name if sender else 'unknown'
    
    celery_task_logger.error(
        "Task failed with exception",
        exception=str(exception) if exception else 'Unknown exception',
        exception_type=type(exception).__name__ if exception else 'Unknown',
        traceback=str(traceback) if traceback and settings.DEBUG else None
    )
    
    # Log audit trail for critical failures
    if hasattr(sender, 'priority') and getattr(sender, 'priority', 0) >= 8:
        task_audit_logger.log_sensitive_operation(
            task_id=task_id,
            task_name=task_name,
            operation='critical_task_failure',
            details={
                'exception': str(exception) if exception else 'Unknown',
                'exception_type': type(exception).__name__ if exception else 'Unknown'
            }
        )


@task_success.connect
def task_success_handler(sender=None, result=None, **kwds):
    """Handle task success signal"""
    task_name = sender.name if sender else 'unknown'
    
    celery_task_logger.info(
        "Task succeeded",
        result_size=len(str(result)) if result else 0,
        result_type=type(result).__name__ if result else None
    )


@worker_ready.connect
def worker_ready_handler(sender=None, **kwds):
    """Handle worker ready signal"""
    worker_name = sender.hostname if sender else 'unknown'
    
    logger.info("Celery worker ready", 
                worker_name=worker_name,
                timestamp=datetime.utcnow().isoformat())


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwds):
    """Handle worker shutdown signal"""
    worker_name = sender.hostname if sender else 'unknown'
    
    logger.info("Celery worker shutting down", 
                worker_name=worker_name,
                timestamp=datetime.utcnow().isoformat())


@worker_process_init.connect
def worker_process_init_handler(sender=None, **kwds):
    """Handle worker process init signal"""
    logger.info("Celery worker process initialized",
                timestamp=datetime.utcnow().isoformat())


def configure_task_logging(task_instance, **context):
    """Configure logging for a specific task instance"""
    if hasattr(task_instance, 'request'):
        celery_task_logger.set_context(
            task_id=task_instance.request.id,
            task_name=task_instance.name,
            **context
        )


def log_task_performance(task_name: str, duration: float, **context):
    """Log task performance metrics"""
    task_metrics.record_task_duration(task_name, duration)
    
    celery_task_logger.info(
        "Task performance",
        task_name=task_name,
        duration=duration,
        duration_ms=duration * 1000,
        **context
    )


def log_task_business_event(task_name: str, event: str, **data):
    """Log business-specific task events"""
    celery_task_logger.info(
        f"Task business event: {event}",
        task_name=task_name,
        event=event,
        **data
    )


# Export components
__all__ = [
    'CeleryLogHandler',
    'CeleryTaskLogger',
    'celery_task_logger',
    'setup_celery_logging',
    'configure_task_logging',
    'log_task_performance',
    'log_task_business_event'
]
