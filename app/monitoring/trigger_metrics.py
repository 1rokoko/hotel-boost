"""
Trigger system metrics and monitoring
"""

import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from functools import wraps
from contextlib import contextmanager
import structlog

from prometheus_client import Counter, Histogram, Gauge, Summary
from app.core.logging import get_logger

logger = get_logger(__name__)

# Prometheus metrics for trigger system
trigger_executions_total = Counter(
    'trigger_executions_total',
    'Total number of trigger executions',
    ['hotel_id', 'trigger_type', 'status']
)

trigger_execution_duration = Histogram(
    'trigger_execution_duration_seconds',
    'Time spent executing triggers',
    ['hotel_id', 'trigger_type'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

trigger_evaluation_duration = Histogram(
    'trigger_evaluation_duration_seconds',
    'Time spent evaluating trigger conditions',
    ['hotel_id', 'trigger_type'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

trigger_template_rendering_duration = Histogram(
    'trigger_template_rendering_duration_seconds',
    'Time spent rendering trigger templates',
    ['hotel_id'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
)

trigger_scheduling_duration = Histogram(
    'trigger_scheduling_duration_seconds',
    'Time spent scheduling triggers',
    ['hotel_id'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
)

active_triggers_gauge = Gauge(
    'active_triggers_total',
    'Number of active triggers',
    ['hotel_id', 'trigger_type']
)

scheduled_triggers_gauge = Gauge(
    'scheduled_triggers_total',
    'Number of scheduled triggers',
    ['hotel_id']
)

trigger_errors_total = Counter(
    'trigger_errors_total',
    'Total number of trigger errors',
    ['hotel_id', 'trigger_type', 'error_type']
)

trigger_queue_size = Gauge(
    'trigger_queue_size',
    'Number of triggers in execution queue'
)

trigger_success_rate = Summary(
    'trigger_success_rate',
    'Success rate of trigger executions',
    ['hotel_id', 'trigger_type']
)


class TriggerMetrics:
    """Centralized metrics collection for trigger system"""
    
    def __init__(self):
        """Initialize metrics collector"""
        self.logger = logger.bind(component="trigger_metrics")
    
    @contextmanager
    def measure_execution_time(self, hotel_id: str, trigger_type: str):
        """Context manager to measure trigger execution time"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            trigger_execution_duration.labels(
                hotel_id=hotel_id,
                trigger_type=trigger_type
            ).observe(duration)
    
    @contextmanager
    def measure_evaluation_time(self, hotel_id: str, trigger_type: str):
        """Context manager to measure trigger evaluation time"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            trigger_evaluation_duration.labels(
                hotel_id=hotel_id,
                trigger_type=trigger_type
            ).observe(duration)
    
    @contextmanager
    def measure_template_rendering_time(self, hotel_id: str):
        """Context manager to measure template rendering time"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            trigger_template_rendering_duration.labels(
                hotel_id=hotel_id
            ).observe(duration)
    
    @contextmanager
    def measure_scheduling_time(self, hotel_id: str):
        """Context manager to measure trigger scheduling time"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            trigger_scheduling_duration.labels(
                hotel_id=hotel_id
            ).observe(duration)
    
    def record_trigger_execution(
        self,
        hotel_id: str,
        trigger_type: str,
        success: bool,
        execution_time: float,
        error_type: Optional[str] = None
    ):
        """Record trigger execution metrics"""
        status = "success" if success else "failure"
        
        # Increment execution counter
        trigger_executions_total.labels(
            hotel_id=hotel_id,
            trigger_type=trigger_type,
            status=status
        ).inc()
        
        # Record execution duration
        trigger_execution_duration.labels(
            hotel_id=hotel_id,
            trigger_type=trigger_type
        ).observe(execution_time)
        
        # Record error if applicable
        if not success and error_type:
            trigger_errors_total.labels(
                hotel_id=hotel_id,
                trigger_type=trigger_type,
                error_type=error_type
            ).inc()
        
        # Update success rate
        trigger_success_rate.labels(
            hotel_id=hotel_id,
            trigger_type=trigger_type
        ).observe(1.0 if success else 0.0)
        
        self.logger.info(
            "Trigger execution recorded",
            hotel_id=hotel_id,
            trigger_type=trigger_type,
            success=success,
            execution_time=execution_time,
            error_type=error_type
        )
    
    def update_active_triggers_count(self, hotel_id: str, trigger_type: str, count: int):
        """Update active triggers gauge"""
        active_triggers_gauge.labels(
            hotel_id=hotel_id,
            trigger_type=trigger_type
        ).set(count)
    
    def update_scheduled_triggers_count(self, hotel_id: str, count: int):
        """Update scheduled triggers gauge"""
        scheduled_triggers_gauge.labels(hotel_id=hotel_id).set(count)
    
    def update_queue_size(self, size: int):
        """Update trigger queue size gauge"""
        trigger_queue_size.set(size)
    
    def record_trigger_error(
        self,
        hotel_id: str,
        trigger_type: str,
        error_type: str,
        error_details: Optional[Dict[str, Any]] = None
    ):
        """Record trigger error"""
        trigger_errors_total.labels(
            hotel_id=hotel_id,
            trigger_type=trigger_type,
            error_type=error_type
        ).inc()
        
        self.logger.error(
            "Trigger error recorded",
            hotel_id=hotel_id,
            trigger_type=trigger_type,
            error_type=error_type,
            error_details=error_details
        )


def monitor_trigger_execution(func):
    """Decorator to monitor trigger execution"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        metrics = TriggerMetrics()
        
        # Extract hotel_id and trigger_type from arguments
        hotel_id = kwargs.get('hotel_id', 'unknown')
        trigger_type = kwargs.get('trigger_type', 'unknown')
        
        start_time = time.time()
        success = False
        error_type = None
        
        try:
            result = await func(*args, **kwargs)
            success = True
            return result
        except Exception as e:
            error_type = type(e).__name__
            raise
        finally:
            execution_time = time.time() - start_time
            metrics.record_trigger_execution(
                hotel_id=str(hotel_id),
                trigger_type=str(trigger_type),
                success=success,
                execution_time=execution_time,
                error_type=error_type
            )
    
    return wrapper


def monitor_trigger_evaluation(func):
    """Decorator to monitor trigger evaluation"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        metrics = TriggerMetrics()
        
        # Extract parameters
        hotel_id = kwargs.get('hotel_id', 'unknown')
        trigger_type = kwargs.get('trigger_type', 'unknown')
        
        with metrics.measure_evaluation_time(str(hotel_id), str(trigger_type)):
            return await func(*args, **kwargs)
    
    return wrapper


class TriggerHealthChecker:
    """Health checker for trigger system"""
    
    def __init__(self):
        """Initialize health checker"""
        self.logger = logger.bind(component="trigger_health_checker")
    
    async def check_trigger_system_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check of trigger system"""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        try:
            # Check database connectivity
            health_status["checks"]["database"] = await self._check_database_health()
            
            # Check Celery connectivity
            health_status["checks"]["celery"] = await self._check_celery_health()
            
            # Check trigger execution performance
            health_status["checks"]["performance"] = await self._check_performance_health()
            
            # Check error rates
            health_status["checks"]["error_rates"] = await self._check_error_rates()
            
            # Determine overall status
            failed_checks = [
                check for check in health_status["checks"].values()
                if check["status"] != "healthy"
            ]
            
            if failed_checks:
                health_status["status"] = "degraded" if len(failed_checks) == 1 else "unhealthy"
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            
            self.logger.error(
                "Health check failed",
                error=str(e)
            )
        
        return health_status
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            # This would normally check actual database connectivity
            # For now, return a mock healthy status
            return {
                "status": "healthy",
                "response_time_ms": 10,
                "active_connections": 5
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def _check_celery_health(self) -> Dict[str, Any]:
        """Check Celery worker connectivity and queue status"""
        try:
            # This would normally check actual Celery status
            # For now, return a mock healthy status
            return {
                "status": "healthy",
                "active_workers": 3,
                "queue_length": 5
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def _check_performance_health(self) -> Dict[str, Any]:
        """Check trigger execution performance metrics"""
        try:
            # This would normally check actual performance metrics
            # For now, return a mock healthy status
            return {
                "status": "healthy",
                "avg_execution_time_ms": 150,
                "p95_execution_time_ms": 500
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def _check_error_rates(self) -> Dict[str, Any]:
        """Check trigger error rates"""
        try:
            # This would normally check actual error rates
            # For now, return a mock healthy status
            return {
                "status": "healthy",
                "error_rate_percent": 2.5,
                "errors_last_hour": 3
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


class TriggerAlerting:
    """Alerting system for trigger issues"""
    
    def __init__(self):
        """Initialize alerting system"""
        self.logger = logger.bind(component="trigger_alerting")
    
    async def check_and_alert(self):
        """Check trigger system and send alerts if needed"""
        try:
            health_checker = TriggerHealthChecker()
            health_status = await health_checker.check_trigger_system_health()
            
            if health_status["status"] != "healthy":
                await self._send_alert(health_status)
            
        except Exception as e:
            self.logger.error(
                "Error in alerting system",
                error=str(e)
            )
    
    async def _send_alert(self, health_status: Dict[str, Any]):
        """Send alert for unhealthy trigger system"""
        alert_message = f"Trigger system health: {health_status['status']}"
        
        # Log the alert
        self.logger.warning(
            "Trigger system alert",
            status=health_status["status"],
            checks=health_status["checks"]
        )
        
        # In a real implementation, this would send alerts via:
        # - Email
        # - Slack
        # - PagerDuty
        # - SMS
        # etc.


# Global metrics instance
trigger_metrics = TriggerMetrics()

# Export all monitoring components
__all__ = [
    'TriggerMetrics',
    'TriggerHealthChecker',
    'TriggerAlerting',
    'trigger_metrics',
    'monitor_trigger_execution',
    'monitor_trigger_evaluation',
    # Prometheus metrics
    'trigger_executions_total',
    'trigger_execution_duration',
    'trigger_evaluation_duration',
    'trigger_template_rendering_duration',
    'trigger_scheduling_duration',
    'active_triggers_gauge',
    'scheduled_triggers_gauge',
    'trigger_errors_total',
    'trigger_queue_size',
    'trigger_success_rate'
]
