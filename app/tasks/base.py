"""
Base task classes and utilities for Celery tasks
"""

import time
import traceback
from typing import Any, Dict, Optional, Union
from celery import Task
from celery.exceptions import Retry, MaxRetriesExceededError
import structlog

from app.core.celery_app import celery_app
from app.core.tenant import TenantContext
from app.utils.task_logger import TaskLogger

logger = structlog.get_logger(__name__)


class BaseTask(Task):
    """Base task class with common functionality"""
    
    # Task configuration
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True
    
    def __init__(self):
        self.task_logger = TaskLogger()
    
    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """Called when task succeeds"""
        self.task_logger.log_task_success(
            task_id=task_id,
            task_name=self.name,
            result=retval,
            args=args,
            kwargs=kwargs
        )
        logger.info("Task completed successfully", 
                   task_id=task_id, 
                   task_name=self.name,
                   result_type=type(retval).__name__)
    
    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo) -> None:
        """Called when task fails"""
        self.task_logger.log_task_failure(
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            traceback=traceback.format_exc(),
            args=args,
            kwargs=kwargs
        )
        logger.error("Task failed", 
                    task_id=task_id, 
                    task_name=self.name,
                    error=str(exc),
                    exc_info=exc)
    
    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo) -> None:
        """Called when task is retried"""
        self.task_logger.log_task_retry(
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            retry_count=self.request.retries,
            args=args,
            kwargs=kwargs
        )
        logger.warning("Task retrying", 
                      task_id=task_id, 
                      task_name=self.name,
                      error=str(exc),
                      retry_count=self.request.retries)
    
    def apply_async(self, args=None, kwargs=None, **options):
        """Override apply_async to add logging"""
        task_id = options.get('task_id')
        self.task_logger.log_task_start(
            task_id=task_id,
            task_name=self.name,
            args=args or (),
            kwargs=kwargs or {}
        )
        return super().apply_async(args, kwargs, **options)


class TenantAwareTask(BaseTask):
    """Base task class with tenant awareness"""
    
    def __call__(self, *args, **kwargs):
        """Execute task with tenant context"""
        hotel_id = kwargs.get('hotel_id') or (args[0] if args else None)
        
        if hotel_id:
            with TenantContext(hotel_id):
                return self.run(*args, **kwargs)
        else:
            logger.warning("Task executed without hotel_id", task_name=self.name)
            return self.run(*args, **kwargs)


class TimedTask(BaseTask):
    """Base task class with execution timing"""
    
    def __call__(self, *args, **kwargs):
        """Execute task with timing"""
        start_time = time.time()
        try:
            result = self.run(*args, **kwargs)
            execution_time = time.time() - start_time
            
            self.task_logger.log_task_timing(
                task_id=self.request.id,
                task_name=self.name,
                execution_time=execution_time
            )
            
            logger.info("Task execution timed", 
                       task_id=self.request.id,
                       task_name=self.name,
                       execution_time=execution_time)
            
            return result
        except Exception as exc:
            execution_time = time.time() - start_time
            logger.error("Task failed with timing", 
                        task_id=self.request.id,
                        task_name=self.name,
                        execution_time=execution_time,
                        error=str(exc))
            raise


class CriticalTask(BaseTask):
    """Base task class for critical tasks with enhanced error handling"""
    
    # More aggressive retry settings for critical tasks
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 5, 'countdown': 30}
    retry_backoff = True
    retry_backoff_max = 300  # 5 minutes
    retry_jitter = True
    
    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo) -> None:
        """Enhanced failure handling for critical tasks"""
        super().on_failure(exc, task_id, args, kwargs, einfo)
        
        # Send alert for critical task failures
        logger.critical("Critical task failed", 
                       task_id=task_id, 
                       task_name=self.name,
                       error=str(exc),
                       args=args,
                       kwargs=kwargs)
        
        # TODO: Implement alerting mechanism (email, Slack, etc.)


class WhatsAppTask(TenantAwareTask, TimedTask):
    """Base task class for WhatsApp-related operations"""
    
    # WhatsApp specific retry settings
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 120}  # 2 minutes
    
    def validate_whatsapp_params(self, **kwargs) -> bool:
        """Validate WhatsApp-specific parameters"""
        required_params = ['hotel_id']
        for param in required_params:
            if param not in kwargs:
                logger.error("Missing required WhatsApp parameter", 
                           task_name=self.name,
                           missing_param=param)
                return False
        return True


class AITask(BaseTask):
    """Base task class for AI-related operations (DeepSeek, etc.)"""
    
    # AI specific retry settings with longer delays
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 180}  # 3 minutes
    retry_backoff = True
    retry_backoff_max = 900  # 15 minutes
    
    def validate_ai_params(self, **kwargs) -> bool:
        """Validate AI-specific parameters"""
        required_params = ['text', 'hotel_id']
        for param in required_params:
            if param not in kwargs:
                logger.error("Missing required AI parameter", 
                           task_name=self.name,
                           missing_param=param)
                return False
        return True


class EmailTask(BaseTask):
    """Base task class for email operations"""
    
    # Email specific retry settings
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 5, 'countdown': 300}  # 5 minutes
    retry_backoff = True
    
    def validate_email_params(self, **kwargs) -> bool:
        """Validate email-specific parameters"""
        required_params = ['to_email', 'subject']
        for param in required_params:
            if param not in kwargs:
                logger.error("Missing required email parameter", 
                           task_name=self.name,
                           missing_param=param)
                return False
        return True


class MaintenanceTask(BaseTask):
    """Base task class for maintenance operations"""
    
    # Maintenance tasks should not retry aggressively
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 1, 'countdown': 3600}  # 1 hour
    
    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo) -> None:
        """Log maintenance task failures"""
        super().on_failure(exc, task_id, args, kwargs, einfo)
        logger.warning("Maintenance task failed", 
                      task_id=task_id, 
                      task_name=self.name,
                      error=str(exc))


# Task decorators using base classes
def base_task(*args, **kwargs):
    """Decorator for basic tasks"""
    kwargs.setdefault('base', BaseTask)
    return celery_app.task(*args, **kwargs)


def tenant_aware_task(*args, **kwargs):
    """Decorator for tenant-aware tasks"""
    kwargs.setdefault('base', TenantAwareTask)
    return celery_app.task(*args, **kwargs)


def timed_task(*args, **kwargs):
    """Decorator for timed tasks"""
    kwargs.setdefault('base', TimedTask)
    return celery_app.task(*args, **kwargs)


def critical_task(*args, **kwargs):
    """Decorator for critical tasks"""
    kwargs.setdefault('base', CriticalTask)
    return celery_app.task(*args, **kwargs)


def whatsapp_task(*args, **kwargs):
    """Decorator for WhatsApp tasks"""
    kwargs.setdefault('base', WhatsAppTask)
    kwargs.setdefault('queue', 'incoming_messages')
    return celery_app.task(*args, **kwargs)


def ai_task(*args, **kwargs):
    """Decorator for AI tasks"""
    kwargs.setdefault('base', AITask)
    kwargs.setdefault('queue', 'sentiment_analysis')
    return celery_app.task(*args, **kwargs)


def email_task(*args, **kwargs):
    """Decorator for email tasks"""
    kwargs.setdefault('base', EmailTask)
    kwargs.setdefault('queue', 'email_notifications')
    return celery_app.task(*args, **kwargs)


def maintenance_task(*args, **kwargs):
    """Decorator for maintenance tasks"""
    kwargs.setdefault('base', MaintenanceTask)
    kwargs.setdefault('queue', 'maintenance')
    return celery_app.task(*args, **kwargs)


# Export all components
__all__ = [
    'BaseTask',
    'TenantAwareTask', 
    'TimedTask',
    'CriticalTask',
    'WhatsAppTask',
    'AITask',
    'EmailTask',
    'MaintenanceTask',
    'base_task',
    'tenant_aware_task',
    'timed_task',
    'critical_task',
    'whatsapp_task',
    'ai_task',
    'email_task',
    'maintenance_task'
]
