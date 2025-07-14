"""
Celery application configuration for WhatsApp Hotel Bot
"""

from celery import Celery
import structlog

from app.core.config import settings
from app.core.celery_config import get_celery_config
from app.core.celery_beat import setup_beat_schedule
from app.core.celery_logging import setup_celery_logging

logger = structlog.get_logger(__name__)


def create_celery_app() -> Celery:
    """Create and configure Celery application"""

    # Get configuration based on environment
    config_class = get_celery_config()

    celery_app = Celery(
        "hotel_bot",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            'app.tasks.process_incoming',
            'app.tasks.send_message',
            'app.tasks.analyze_sentiment',
            'app.tasks.generate_response',
            'app.tasks.deepseek_monitoring',
            'app.tasks.execute_triggers',
            'app.tasks.analyze_message_sentiment',
            'app.tasks.send_staff_alert',
            'app.tasks.email_tasks',
            'app.tasks.maintenance'
        ]
    )

    # Apply configuration from config class
    celery_app.config_from_object(config_class)

    # Setup Beat schedule
    setup_beat_schedule(celery_app)

    # Setup logging
    setup_celery_logging()

    logger.info("Celery application created and configured",
                broker=settings.CELERY_BROKER_URL,
                backend=settings.CELERY_RESULT_BACKEND,
                environment=settings.ENVIRONMENT)
    
    return celery_app


# Create global Celery instance
celery_app = create_celery_app()


# Task decorators for different priorities
def high_priority_task(*args, **kwargs):
    """Decorator for high priority tasks"""
    kwargs.setdefault('queue', 'high_priority')
    return celery_app.task(*args, **kwargs)


def incoming_message_task(*args, **kwargs):
    """Decorator for incoming message tasks"""
    kwargs.setdefault('queue', 'incoming_messages')
    return celery_app.task(*args, **kwargs)


def outgoing_message_task(*args, **kwargs):
    """Decorator for outgoing message tasks"""
    kwargs.setdefault('queue', 'outgoing_messages')
    return celery_app.task(*args, **kwargs)


def sentiment_analysis_task(*args, **kwargs):
    """Decorator for sentiment analysis tasks"""
    kwargs.setdefault('queue', 'sentiment_analysis')
    return celery_app.task(*args, **kwargs)


def email_notification_task(*args, **kwargs):
    """Decorator for email notification tasks"""
    kwargs.setdefault('queue', 'email_notifications')
    return celery_app.task(*args, **kwargs)


def maintenance_task(*args, **kwargs):
    """Decorator for maintenance tasks"""
    kwargs.setdefault('queue', 'maintenance')
    kwargs.setdefault('priority', 1)
    return celery_app.task(*args, **kwargs)


# Health check task
@celery_app.task
def health_check():
    """Simple health check task"""
    return {"status": "healthy", "message": "Celery is working"}


# Export main components
__all__ = [
    'celery_app',
    'create_celery_app',
    'high_priority_task',
    'incoming_message_task',
    'outgoing_message_task',
    'sentiment_analysis_task',
    'email_notification_task',
    'maintenance_task',
    'health_check'
]
