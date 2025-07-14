"""
Celery Beat configuration for periodic tasks
"""

from datetime import timedelta
from celery.schedules import crontab
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class CeleryBeatConfig:
    """Celery Beat schedule configuration"""
    
    # Default timezone
    timezone = 'UTC'
    
    # Beat schedule configuration
    beat_schedule = {
        # System maintenance tasks
        'cleanup-old-results': {
            'task': 'app.tasks.maintenance.cleanup_old_results',
            'schedule': timedelta(hours=1),  # Every hour
            'options': {
                'queue': 'maintenance',
                'priority': 1
            }
        },
        
        'cleanup-old-logs': {
            'task': 'app.tasks.maintenance.cleanup_old_logs',
            'schedule': timedelta(hours=6),  # Every 6 hours
            'options': {
                'queue': 'maintenance',
                'priority': 1
            }
        },
        
        'system-health-check': {
            'task': 'app.tasks.maintenance.system_health_check',
            'schedule': timedelta(minutes=15),  # Every 15 minutes
            'options': {
                'queue': 'monitoring',
                'priority': 5
            }
        },
        
        # External API health checks
        'health-check-green-api': {
            'task': 'app.tasks.monitoring.health_check_green_api',
            'schedule': timedelta(minutes=5),  # Every 5 minutes
            'options': {
                'queue': 'monitoring',
                'priority': 7
            }
        },
        
        'health-check-deepseek-api': {
            'task': 'app.tasks.monitoring.health_check_deepseek_api',
            'schedule': timedelta(minutes=10),  # Every 10 minutes
            'options': {
                'queue': 'monitoring',
                'priority': 6
            }
        },
        
        # Trigger management
        'cleanup-expired-triggers': {
            'task': 'app.tasks.execute_triggers.cleanup_expired_scheduled_triggers_task',
            'schedule': timedelta(minutes=30),  # Every 30 minutes
            'options': {
                'queue': 'maintenance',
                'priority': 3
            }
        },
        
        'process-scheduled-triggers': {
            'task': 'app.tasks.execute_triggers.process_scheduled_triggers',
            'schedule': timedelta(minutes=1),  # Every minute
            'options': {
                'queue': 'trigger_execution',
                'priority': 8
            }
        },
        
        # Alert management
        'check-overdue-alerts': {
            'task': 'app.tasks.send_staff_alert.check_overdue_alerts_task',
            'schedule': timedelta(minutes=10),  # Every 10 minutes
            'options': {
                'queue': 'high_priority',
                'priority': 9
            }
        },
        
        'escalate-unresponded-alerts': {
            'task': 'app.tasks.send_staff_alert.escalate_unresponded_alerts',
            'schedule': timedelta(hours=1),  # Every hour
            'options': {
                'queue': 'high_priority',
                'priority': 8
            }
        },
        
        # Sentiment analysis cleanup
        'cleanup-old-sentiment-data': {
            'task': 'app.tasks.analyze_message_sentiment.cleanup_old_sentiment_data_task',
            'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
            'options': {
                'queue': 'maintenance',
                'priority': 2
            }
        },
        
        # Email tasks
        'send-daily-reports': {
            'task': 'app.tasks.email_tasks.send_daily_report',
            'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
            'options': {
                'queue': 'email_notifications',
                'priority': 6
            }
        },
        
        'send-weekly-summary': {
            'task': 'app.tasks.email_tasks.send_weekly_summary',
            'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday at 9 AM
            'options': {
                'queue': 'email_notifications',
                'priority': 5
            }
        },
        
        'cleanup-old-email-logs': {
            'task': 'app.tasks.email_tasks.cleanup_old_email_logs',
            'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
            'options': {
                'queue': 'maintenance',
                'priority': 1
            }
        },
        
        # Database maintenance
        'optimize-database': {
            'task': 'app.tasks.maintenance.optimize_database',
            'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
            'options': {
                'queue': 'maintenance',
                'priority': 1
            }
        },
        
        'backup-critical-data': {
            'task': 'app.tasks.maintenance.backup_critical_data',
            'schedule': crontab(hour=0, minute=0),  # Daily at midnight
            'options': {
                'queue': 'maintenance',
                'priority': 2
            }
        },
        
        # Metrics collection
        'collect-system-metrics': {
            'task': 'app.tasks.monitoring.collect_system_metrics',
            'schedule': timedelta(minutes=5),  # Every 5 minutes
            'options': {
                'queue': 'monitoring',
                'priority': 4
            }
        },
        
        'generate-metrics-report': {
            'task': 'app.tasks.monitoring.generate_metrics_report',
            'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
            'options': {
                'queue': 'monitoring',
                'priority': 3
            }
        },
        
        # Cache management
        'cleanup-expired-cache': {
            'task': 'app.tasks.maintenance.cleanup_expired_cache',
            'schedule': timedelta(hours=2),  # Every 2 hours
            'options': {
                'queue': 'maintenance',
                'priority': 2
            }
        },
        
        'warm-cache': {
            'task': 'app.tasks.maintenance.warm_cache',
            'schedule': crontab(hour=7, minute=0),  # Daily at 7 AM
            'options': {
                'queue': 'maintenance',
                'priority': 3
            }
        },
        
        # Security tasks
        'rotate-api-keys': {
            'task': 'app.tasks.security.rotate_api_keys',
            'schedule': crontab(hour=4, minute=0, day_of_week=0),  # Weekly on Sunday at 4 AM
            'options': {
                'queue': 'maintenance',
                'priority': 8
            }
        },
        
        'security-audit': {
            'task': 'app.tasks.security.security_audit',
            'schedule': crontab(hour=5, minute=0),  # Daily at 5 AM
            'options': {
                'queue': 'monitoring',
                'priority': 7
            }
        }
    }


class DevelopmentBeatConfig(CeleryBeatConfig):
    """Development-specific Beat configuration"""
    
    # Override some schedules for development
    beat_schedule = CeleryBeatConfig.beat_schedule.copy()
    
    # More frequent health checks in development
    beat_schedule.update({
        'health-check-green-api': {
            'task': 'app.tasks.monitoring.health_check_green_api',
            'schedule': timedelta(minutes=2),  # Every 2 minutes
            'options': {
                'queue': 'monitoring',
                'priority': 7
            }
        },
        
        # Less frequent cleanup in development
        'cleanup-old-results': {
            'task': 'app.tasks.maintenance.cleanup_old_results',
            'schedule': timedelta(hours=6),  # Every 6 hours
            'options': {
                'queue': 'maintenance',
                'priority': 1
            }
        }
    })


class ProductionBeatConfig(CeleryBeatConfig):
    """Production-specific Beat configuration"""
    
    # Override some schedules for production
    beat_schedule = CeleryBeatConfig.beat_schedule.copy()
    
    # More conservative schedules for production
    beat_schedule.update({
        'system-health-check': {
            'task': 'app.tasks.maintenance.system_health_check',
            'schedule': timedelta(minutes=30),  # Every 30 minutes
            'options': {
                'queue': 'monitoring',
                'priority': 5
            }
        },
        
        # More frequent trigger processing in production
        'process-scheduled-triggers': {
            'task': 'app.tasks.execute_triggers.process_scheduled_triggers',
            'schedule': timedelta(seconds=30),  # Every 30 seconds
            'options': {
                'queue': 'trigger_execution',
                'priority': 8
            }
        }
    })


class TestingBeatConfig(CeleryBeatConfig):
    """Testing-specific Beat configuration"""
    
    # Minimal schedule for testing
    beat_schedule = {
        'test-health-check': {
            'task': 'app.tasks.maintenance.system_health_check',
            'schedule': timedelta(minutes=60),  # Every hour
            'options': {
                'queue': 'monitoring',
                'priority': 5
            }
        }
    }


def get_beat_config():
    """Get Beat configuration based on environment"""
    if settings.ENVIRONMENT == 'testing':
        return TestingBeatConfig
    elif settings.ENVIRONMENT == 'production':
        return ProductionBeatConfig
    else:
        return DevelopmentBeatConfig


def setup_beat_schedule(celery_app):
    """Setup beat schedule on Celery app"""
    config_class = get_beat_config()
    
    # Apply beat schedule
    celery_app.conf.beat_schedule = config_class.beat_schedule
    celery_app.conf.timezone = config_class.timezone
    
    logger.info("Celery Beat schedule configured", 
                environment=settings.ENVIRONMENT,
                task_count=len(config_class.beat_schedule))
    
    return celery_app


# Export components
__all__ = [
    'CeleryBeatConfig',
    'DevelopmentBeatConfig',
    'ProductionBeatConfig',
    'TestingBeatConfig',
    'get_beat_config',
    'setup_beat_schedule'
]
