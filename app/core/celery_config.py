"""
Celery configuration settings for WhatsApp Hotel Bot
"""

from kombu import Queue
from app.core.config import settings


class CeleryConfig:
    """Celery configuration class"""
    
    # Broker settings
    broker_url = settings.CELERY_BROKER_URL
    result_backend = settings.CELERY_RESULT_BACKEND
    
    # Task routing configuration
    task_routes = {
        'app.tasks.process_incoming.*': {'queue': 'incoming_messages'},
        'app.tasks.send_message.*': {'queue': 'outgoing_messages'},
        'app.tasks.analyze_sentiment.*': {'queue': 'sentiment_analysis'},
        'app.tasks.generate_response.*': {'queue': 'response_generation'},
        'app.tasks.deepseek_monitoring.*': {'queue': 'monitoring'},
        'app.tasks.execute_triggers.*': {'queue': 'trigger_execution'},
        'app.tasks.analyze_message_sentiment.*': {'queue': 'sentiment_analysis'},
        'app.tasks.send_staff_alert.*': {'queue': 'high_priority'},
        'app.tasks.email_tasks.*': {'queue': 'email_notifications'},
        'app.tasks.maintenance.*': {'queue': 'maintenance'},
    }
    
    # Queue configuration
    task_default_queue = 'default'
    task_queues = (
        Queue('default'),
        Queue('incoming_messages'),
        Queue('outgoing_messages'),
        Queue('sentiment_analysis'),
        Queue('response_generation'),
        Queue('monitoring'),
        Queue('trigger_execution'),
        Queue('high_priority'),
        Queue('email_notifications'),
        Queue('maintenance'),
    )
    
    # Task execution settings
    task_serializer = 'json'
    accept_content = ['json']
    result_serializer = 'json'
    timezone = 'UTC'
    enable_utc = True
    
    # Task retry configuration
    task_acks_late = True
    task_reject_on_worker_lost = True
    task_default_retry_delay = 60  # seconds
    task_max_retries = 3
    
    # Worker configuration
    worker_prefetch_multiplier = 1
    worker_max_tasks_per_child = 1000
    worker_disable_rate_limits = False
    
    # Result backend configuration
    result_expires = 3600  # 1 hour
    result_persistent = True
    result_compression = 'gzip'
    
    # Monitoring and events
    worker_send_task_events = True
    task_send_sent_event = True
    
    # Security settings
    task_always_eager = False  # Set to True for testing
    
    # Task time limits
    task_soft_time_limit = 300  # 5 minutes
    task_time_limit = 600  # 10 minutes
    
    # Beat schedule for periodic tasks
    beat_schedule = {
        'cleanup-old-results': {
            'task': 'app.tasks.maintenance.cleanup_old_results',
            'schedule': 3600.0,  # Every hour
            'options': {'queue': 'maintenance'}
        },
        'health-check-green-api': {
            'task': 'app.tasks.monitoring.health_check_green_api',
            'schedule': 300.0,  # Every 5 minutes
            'options': {'queue': 'monitoring'}
        },
        'cleanup-expired-triggers': {
            'task': 'app.tasks.execute_triggers.cleanup_expired_scheduled_triggers_task',
            'schedule': 1800.0,  # Every 30 minutes
            'options': {'queue': 'maintenance'}
        },
        'check-overdue-alerts': {
            'task': 'app.tasks.send_staff_alert.check_overdue_alerts_task',
            'schedule': 600.0,  # Every 10 minutes
            'options': {'queue': 'high_priority'}
        },
        'cleanup-old-sentiment-data': {
            'task': 'app.tasks.analyze_message_sentiment.cleanup_old_sentiment_data_task',
            'schedule': 86400.0,  # Every 24 hours
            'options': {'queue': 'maintenance'}
        },
        'generate-daily-reports': {
            'task': 'app.tasks.email_tasks.send_daily_report',
            'schedule': 86400.0,  # Every 24 hours at midnight
            'options': {'queue': 'email_notifications'}
        },
        'system-health-check': {
            'task': 'app.tasks.maintenance.system_health_check',
            'schedule': 900.0,  # Every 15 minutes
            'options': {'queue': 'monitoring'}
        },
    }
    
    # Task annotations for specific configurations
    task_annotations = {
        'app.tasks.send_staff_alert.*': {
            'rate_limit': '10/m',  # 10 per minute
            'priority': 9
        },
        'app.tasks.email_tasks.*': {
            'rate_limit': '30/m',  # 30 per minute
            'priority': 7
        },
        'app.tasks.analyze_sentiment.*': {
            'rate_limit': '100/m',  # 100 per minute
            'priority': 5
        },
        'app.tasks.maintenance.*': {
            'priority': 1
        },
    }
    
    # Error handling
    task_reject_on_worker_lost = True
    task_ignore_result = False
    
    # Logging
    worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'
    
    # Redis specific settings (if using Redis as broker)
    broker_transport_options = {
        'visibility_timeout': 3600,  # 1 hour
        'fanout_prefix': True,
        'fanout_patterns': True
    }
    
    # Result backend transport options
    result_backend_transport_options = {
        'master_name': 'mymaster'
    }


# Configuration for different environments
class DevelopmentCeleryConfig(CeleryConfig):
    """Development-specific Celery configuration"""
    task_always_eager = False
    task_eager_propagates = True
    worker_log_level = 'DEBUG'


class TestingCeleryConfig(CeleryConfig):
    """Testing-specific Celery configuration"""
    task_always_eager = True
    task_eager_propagates = True
    broker_url = 'memory://'
    result_backend = 'cache+memory://'


class ProductionCeleryConfig(CeleryConfig):
    """Production-specific Celery configuration"""
    task_always_eager = False
    worker_log_level = 'INFO'
    # Increase retry delays for production
    task_default_retry_delay = 120
    task_max_retries = 5
    # Longer time limits for production
    task_soft_time_limit = 600  # 10 minutes
    task_time_limit = 1200  # 20 minutes


def get_celery_config():
    """Get Celery configuration based on environment"""
    if settings.ENVIRONMENT == 'testing':
        return TestingCeleryConfig
    elif settings.ENVIRONMENT == 'production':
        return ProductionCeleryConfig
    else:
        return DevelopmentCeleryConfig
