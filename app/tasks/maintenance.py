"""
Maintenance tasks for system upkeep
"""

from app.utils.periodic_tasks import (
    cleanup_old_results,
    cleanup_old_logs,
    system_health_check,
    optimize_database,
    backup_critical_data,
    cleanup_expired_cache,
    warm_cache
)

# Re-export all maintenance tasks
__all__ = [
    'cleanup_old_results',
    'cleanup_old_logs', 
    'system_health_check',
    'optimize_database',
    'backup_critical_data',
    'cleanup_expired_cache',
    'warm_cache'
]
