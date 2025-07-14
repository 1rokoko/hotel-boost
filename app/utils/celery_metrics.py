"""
Prometheus metrics for Celery tasks
"""

from typing import Dict, Optional
import time
from prometheus_client import Counter, Histogram, Gauge, Info
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class CeleryMetrics:
    """Prometheus metrics collector for Celery tasks"""
    
    def __init__(self):
        # Task execution metrics
        self.task_total = Counter(
            'celery_task_total',
            'Total number of Celery tasks',
            ['task_name', 'status', 'queue']
        )
        
        self.task_duration = Histogram(
            'celery_task_duration_seconds',
            'Task execution duration in seconds',
            ['task_name', 'queue'],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, float('inf')]
        )
        
        self.task_retry_total = Counter(
            'celery_task_retry_total',
            'Total number of task retries',
            ['task_name', 'queue']
        )
        
        # Queue metrics
        self.queue_size = Gauge(
            'celery_queue_size',
            'Number of tasks in queue',
            ['queue_name']
        )
        
        self.queue_active_tasks = Gauge(
            'celery_queue_active_tasks',
            'Number of active tasks in queue',
            ['queue_name']
        )
        
        self.queue_processed_total = Counter(
            'celery_queue_processed_total',
            'Total number of processed tasks per queue',
            ['queue_name']
        )
        
        # Worker metrics
        self.worker_active = Gauge(
            'celery_worker_active',
            'Number of active workers',
            ['worker_name']
        )
        
        self.worker_tasks_active = Gauge(
            'celery_worker_tasks_active',
            'Number of active tasks per worker',
            ['worker_name']
        )
        
        self.worker_tasks_processed = Counter(
            'celery_worker_tasks_processed',
            'Total number of tasks processed by worker',
            ['worker_name']
        )
        
        self.worker_load_avg = Gauge(
            'celery_worker_load_avg',
            'Worker load average',
            ['worker_name', 'period']
        )
        
        # System metrics
        self.celery_up = Gauge(
            'celery_up',
            'Celery system status (1 = up, 0 = down)'
        )
        
        self.celery_info = Info(
            'celery_info',
            'Celery system information'
        )
        
        # Hotel-specific metrics
        self.hotel_task_total = Counter(
            'celery_hotel_task_total',
            'Total number of tasks per hotel',
            ['hotel_id', 'task_name', 'status']
        )
        
        self.hotel_message_processing_duration = Histogram(
            'celery_hotel_message_processing_duration_seconds',
            'Message processing duration per hotel',
            ['hotel_id'],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float('inf')]
        )
        
        # Error metrics
        self.task_errors_total = Counter(
            'celery_task_errors_total',
            'Total number of task errors',
            ['task_name', 'error_type', 'queue']
        )
        
        # Initialize system status
        self.celery_up.set(1)
        self.celery_info.info({
            'version': '1.0.0',
            'environment': settings.ENVIRONMENT,
            'broker': 'redis'
        })
    
    def record_task_start(self, task_name: str, queue: str = 'default', 
                         hotel_id: Optional[int] = None) -> None:
        """Record task start"""
        self.task_total.labels(task_name=task_name, status='started', queue=queue).inc()
        
        if hotel_id:
            self.hotel_task_total.labels(
                hotel_id=str(hotel_id), 
                task_name=task_name, 
                status='started'
            ).inc()
        
        logger.debug("Recorded task start metric", 
                    task_name=task_name, 
                    queue=queue, 
                    hotel_id=hotel_id)
    
    def record_task_success(self, task_name: str, duration: float, 
                           queue: str = 'default', hotel_id: Optional[int] = None) -> None:
        """Record successful task completion"""
        self.task_total.labels(task_name=task_name, status='success', queue=queue).inc()
        self.task_duration.labels(task_name=task_name, queue=queue).observe(duration)
        
        if hotel_id:
            self.hotel_task_total.labels(
                hotel_id=str(hotel_id), 
                task_name=task_name, 
                status='success'
            ).inc()
            
            # Record message processing duration for WhatsApp tasks
            if 'message' in task_name.lower() or 'whatsapp' in task_name.lower():
                self.hotel_message_processing_duration.labels(
                    hotel_id=str(hotel_id)
                ).observe(duration)
        
        logger.debug("Recorded task success metric", 
                    task_name=task_name, 
                    duration=duration, 
                    queue=queue, 
                    hotel_id=hotel_id)
    
    def record_task_failure(self, task_name: str, error_type: str, 
                           queue: str = 'default', hotel_id: Optional[int] = None) -> None:
        """Record task failure"""
        self.task_total.labels(task_name=task_name, status='failed', queue=queue).inc()
        self.task_errors_total.labels(
            task_name=task_name, 
            error_type=error_type, 
            queue=queue
        ).inc()
        
        if hotel_id:
            self.hotel_task_total.labels(
                hotel_id=str(hotel_id), 
                task_name=task_name, 
                status='failed'
            ).inc()
        
        logger.debug("Recorded task failure metric", 
                    task_name=task_name, 
                    error_type=error_type, 
                    queue=queue, 
                    hotel_id=hotel_id)
    
    def record_task_retry(self, task_name: str, queue: str = 'default', 
                         hotel_id: Optional[int] = None) -> None:
        """Record task retry"""
        self.task_retry_total.labels(task_name=task_name, queue=queue).inc()
        
        if hotel_id:
            self.hotel_task_total.labels(
                hotel_id=str(hotel_id), 
                task_name=task_name, 
                status='retry'
            ).inc()
        
        logger.debug("Recorded task retry metric", 
                    task_name=task_name, 
                    queue=queue, 
                    hotel_id=hotel_id)
    
    def update_queue_size(self, queue_name: str, size: int) -> None:
        """Update queue size metric"""
        self.queue_size.labels(queue_name=queue_name).set(size)
        logger.debug("Updated queue size metric", queue_name=queue_name, size=size)
    
    def update_queue_active_tasks(self, queue_name: str, active_count: int) -> None:
        """Update active tasks in queue"""
        self.queue_active_tasks.labels(queue_name=queue_name).set(active_count)
        logger.debug("Updated queue active tasks metric", 
                    queue_name=queue_name, 
                    active_count=active_count)
    
    def record_queue_processed(self, queue_name: str) -> None:
        """Record processed task in queue"""
        self.queue_processed_total.labels(queue_name=queue_name).inc()
        logger.debug("Recorded queue processed metric", queue_name=queue_name)
    
    def update_worker_status(self, worker_name: str, is_active: bool) -> None:
        """Update worker status"""
        self.worker_active.labels(worker_name=worker_name).set(1 if is_active else 0)
        logger.debug("Updated worker status metric", 
                    worker_name=worker_name, 
                    is_active=is_active)
    
    def update_worker_active_tasks(self, worker_name: str, active_tasks: int) -> None:
        """Update worker active tasks count"""
        self.worker_tasks_active.labels(worker_name=worker_name).set(active_tasks)
        logger.debug("Updated worker active tasks metric", 
                    worker_name=worker_name, 
                    active_tasks=active_tasks)
    
    def record_worker_task_processed(self, worker_name: str) -> None:
        """Record task processed by worker"""
        self.worker_tasks_processed.labels(worker_name=worker_name).inc()
        logger.debug("Recorded worker task processed metric", worker_name=worker_name)
    
    def update_worker_load_avg(self, worker_name: str, load_avg: list) -> None:
        """Update worker load average"""
        if load_avg and len(load_avg) >= 3:
            self.worker_load_avg.labels(worker_name=worker_name, period='1m').set(load_avg[0])
            self.worker_load_avg.labels(worker_name=worker_name, period='5m').set(load_avg[1])
            self.worker_load_avg.labels(worker_name=worker_name, period='15m').set(load_avg[2])
            
            logger.debug("Updated worker load avg metric", 
                        worker_name=worker_name, 
                        load_avg=load_avg)
    
    def set_celery_status(self, is_up: bool) -> None:
        """Set Celery system status"""
        self.celery_up.set(1 if is_up else 0)
        logger.info("Updated Celery status metric", is_up=is_up)
    
    def get_metrics_summary(self) -> Dict[str, float]:
        """Get summary of key metrics"""
        # This would typically collect current metric values
        # For now, return a placeholder summary
        return {
            'total_tasks': 0,  # Would be calculated from counters
            'successful_tasks': 0,
            'failed_tasks': 0,
            'active_workers': 0,
            'queue_sizes': 0
        }


class CeleryMetricsMiddleware:
    """Middleware to automatically collect metrics from task execution"""
    
    def __init__(self, metrics: CeleryMetrics):
        self.metrics = metrics
        self.task_start_times: Dict[str, float] = {}
    
    def on_task_prerun(self, sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
        """Called before task execution"""
        task_name = task.name if task else 'unknown'
        queue = getattr(task, 'queue', 'default') if task else 'default'
        hotel_id = kwargs.get('hotel_id') if kwargs else None
        
        self.task_start_times[task_id] = time.time()
        self.metrics.record_task_start(task_name, queue, hotel_id)
    
    def on_task_postrun(self, sender=None, task_id=None, task=None, args=None, 
                       kwargs=None, retval=None, state=None, **kwds):
        """Called after task execution"""
        task_name = task.name if task else 'unknown'
        queue = getattr(task, 'queue', 'default') if task else 'default'
        hotel_id = kwargs.get('hotel_id') if kwargs else None
        
        start_time = self.task_start_times.pop(task_id, time.time())
        duration = time.time() - start_time
        
        if state == 'SUCCESS':
            self.metrics.record_task_success(task_name, duration, queue, hotel_id)
        elif state == 'FAILURE':
            error_type = type(retval).__name__ if retval else 'Unknown'
            self.metrics.record_task_failure(task_name, error_type, queue, hotel_id)
    
    def on_task_retry(self, sender=None, task_id=None, reason=None, 
                     einfo=None, **kwds):
        """Called when task is retried"""
        task_name = sender.name if sender else 'unknown'
        queue = getattr(sender, 'queue', 'default') if sender else 'default'
        
        self.metrics.record_task_retry(task_name, queue)


# Global metrics instance
celery_metrics = CeleryMetrics()
metrics_middleware = CeleryMetricsMiddleware(celery_metrics)

# Export components
__all__ = [
    'CeleryMetrics',
    'CeleryMetricsMiddleware',
    'celery_metrics',
    'metrics_middleware'
]
