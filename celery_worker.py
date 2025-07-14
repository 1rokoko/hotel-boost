"""
Celery worker entry point for WhatsApp Hotel Bot
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.celery_app import celery_app

if __name__ == '__main__':
    celery_app.start()
