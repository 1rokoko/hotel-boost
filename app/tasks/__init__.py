"""
Celery tasks for WhatsApp Hotel Bot
"""

# Import all task modules to register them with Celery
from . import process_incoming
from . import send_message
from . import email_tasks
from . import maintenance
from . import monitoring
from . import base

__all__ = [
    'process_incoming',
    'send_message',
    'email_tasks',
    'maintenance',
    'monitoring',
    'base'
]
