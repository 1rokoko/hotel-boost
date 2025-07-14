"""
Task monitoring service for Celery tasks
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import structlog

from celery import Celery
from celery.events.state import State
from celery.events import Events
from app.core.celery_app import celery_app
from app.core.config import settings
from app.utils.task_logger import task_metrics

logger = structlog.get_logger(__name__)


@dataclass
class TaskStats:
    """Task statistics data class"""
    task_name: str
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    retry_count: int = 0
    avg_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    last_execution: Optional[datetime] = None


@dataclass
class QueueStats:
    """Queue statistics data class"""
    queue_name: str
    pending_count: int = 0
    active_count: int = 0
    processed_count: int = 0
    failed_count: int = 0


@dataclass
class WorkerStats:
    """Worker statistics data class"""
    worker_name: str
    status: str = "unknown"
    active_tasks: int = 0
    processed_tasks: int = 0
    load_avg: List[float] = None
    last_heartbeat: Optional[datetime] = None


class TaskMonitor:
    """Service for monitoring Celery task execution"""
    
    def __init__(self):
        self.celery_app = celery_app
        self.state = State()
        self.task_stats: Dict[str, TaskStats] = {}
        self.queue_stats: Dict[str, QueueStats] = {}
        self.worker_stats: Dict[str, WorkerStats] = {}
        self.monitoring_active = False
    
    async def start_monitoring(self) -> None:
        """Start task monitoring"""
        if self.monitoring_active:
            logger.warning("Task monitoring already active")
            return
        
        self.monitoring_active = True
        logger.info("Starting task monitoring")
        
        try:
            # Start event monitoring in background
            asyncio.create_task(self._monitor_events())
            
            # Start periodic stats collection
            asyncio.create_task(self._collect_periodic_stats())
            
        except Exception as exc:
            logger.error("Failed to start task monitoring", error=str(exc))
            self.monitoring_active = False
            raise
    
    async def stop_monitoring(self) -> None:
        """Stop task monitoring"""
        self.monitoring_active = False
        logger.info("Task monitoring stopped")
    
    async def _monitor_events(self) -> None:
        """Monitor Celery events"""
        try:
            with self.celery_app.events.default_dispatcher() as dispatcher:
                while self.monitoring_active:
                    try:
                        # Process events
                        events = dispatcher.capture(limit=100, timeout=1.0, wakeup=True)
                        for event in events:
                            await self._process_event(event)
                    except Exception as exc:
                        logger.error("Error processing events", error=str(exc))
                        await asyncio.sleep(1)
        except Exception as exc:
            logger.error("Event monitoring failed", error=str(exc))
    
    async def _process_event(self, event: Dict[str, Any]) -> None:
        """Process individual Celery event"""
        event_type = event.get('type')
        task_name = event.get('name', 'unknown')
        task_id = event.get('uuid')
        
        if event_type == 'task-sent':
            await self._handle_task_sent(task_name, task_id, event)
        elif event_type == 'task-started':
            await self._handle_task_started(task_name, task_id, event)
        elif event_type == 'task-succeeded':
            await self._handle_task_succeeded(task_name, task_id, event)
        elif event_type == 'task-failed':
            await self._handle_task_failed(task_name, task_id, event)
        elif event_type == 'task-retried':
            await self._handle_task_retried(task_name, task_id, event)
        elif event_type == 'worker-heartbeat':
            await self._handle_worker_heartbeat(event)
    
    async def _handle_task_sent(self, task_name: str, task_id: str, event: Dict[str, Any]) -> None:
        """Handle task sent event"""
        stats = self._get_or_create_task_stats(task_name)
        stats.total_count += 1
        
        # Record queue stats
        queue_name = event.get('queue', 'default')
        queue_stats = self._get_or_create_queue_stats(queue_name)
        queue_stats.pending_count += 1
        
        task_metrics.record_task_count(task_name, 'sent')
        
        logger.debug("Task sent", task_name=task_name, task_id=task_id, queue=queue_name)
    
    async def _handle_task_started(self, task_name: str, task_id: str, event: Dict[str, Any]) -> None:
        """Handle task started event"""
        # Update queue stats
        queue_name = event.get('queue', 'default')
        queue_stats = self._get_or_create_queue_stats(queue_name)
        queue_stats.pending_count = max(0, queue_stats.pending_count - 1)
        queue_stats.active_count += 1
        
        task_metrics.record_task_count(task_name, 'started')
        
        logger.debug("Task started", task_name=task_name, task_id=task_id)
    
    async def _handle_task_succeeded(self, task_name: str, task_id: str, event: Dict[str, Any]) -> None:
        """Handle task succeeded event"""
        stats = self._get_or_create_task_stats(task_name)
        stats.success_count += 1
        stats.last_execution = datetime.utcnow()
        
        # Calculate duration if available
        runtime = event.get('runtime')
        if runtime:
            stats.min_duration = min(stats.min_duration, runtime)
            stats.max_duration = max(stats.max_duration, runtime)
            
            # Update average duration
            total_successful = stats.success_count
            if total_successful > 1:
                stats.avg_duration = ((stats.avg_duration * (total_successful - 1)) + runtime) / total_successful
            else:
                stats.avg_duration = runtime
            
            task_metrics.record_task_duration(task_name, runtime)
        
        # Update queue stats
        queue_name = event.get('queue', 'default')
        queue_stats = self._get_or_create_queue_stats(queue_name)
        queue_stats.active_count = max(0, queue_stats.active_count - 1)
        queue_stats.processed_count += 1
        
        task_metrics.record_task_count(task_name, 'success')
        
        logger.debug("Task succeeded", task_name=task_name, task_id=task_id, runtime=runtime)
    
    async def _handle_task_failed(self, task_name: str, task_id: str, event: Dict[str, Any]) -> None:
        """Handle task failed event"""
        stats = self._get_or_create_task_stats(task_name)
        stats.failure_count += 1
        stats.last_execution = datetime.utcnow()
        
        # Update queue stats
        queue_name = event.get('queue', 'default')
        queue_stats = self._get_or_create_queue_stats(queue_name)
        queue_stats.active_count = max(0, queue_stats.active_count - 1)
        queue_stats.failed_count += 1
        
        task_metrics.record_task_count(task_name, 'failed')
        
        exception = event.get('exception')
        traceback = event.get('traceback')
        
        logger.warning("Task failed", 
                      task_name=task_name, 
                      task_id=task_id,
                      exception=exception,
                      traceback=traceback if settings.DEBUG else None)
    
    async def _handle_task_retried(self, task_name: str, task_id: str, event: Dict[str, Any]) -> None:
        """Handle task retried event"""
        stats = self._get_or_create_task_stats(task_name)
        stats.retry_count += 1
        
        task_metrics.record_task_count(task_name, 'retry')
        
        reason = event.get('reason')
        logger.info("Task retried", task_name=task_name, task_id=task_id, reason=reason)
    
    async def _handle_worker_heartbeat(self, event: Dict[str, Any]) -> None:
        """Handle worker heartbeat event"""
        hostname = event.get('hostname', 'unknown')
        
        worker_stats = self._get_or_create_worker_stats(hostname)
        worker_stats.status = 'online'
        worker_stats.last_heartbeat = datetime.utcnow()
        worker_stats.active_tasks = event.get('active', 0)
        worker_stats.processed_tasks = event.get('processed', 0)
        worker_stats.load_avg = event.get('loadavg', [])
        
        task_metrics.record_worker_count(len([w for w in self.worker_stats.values() if w.status == 'online']))
        
        logger.debug("Worker heartbeat", hostname=hostname, active_tasks=worker_stats.active_tasks)
    
    async def _collect_periodic_stats(self) -> None:
        """Collect periodic statistics"""
        while self.monitoring_active:
            try:
                await self._collect_queue_sizes()
                await self._check_worker_health()
                await asyncio.sleep(60)  # Collect stats every minute
            except Exception as exc:
                logger.error("Error collecting periodic stats", error=str(exc))
                await asyncio.sleep(60)
    
    async def _collect_queue_sizes(self) -> None:
        """Collect current queue sizes"""
        try:
            inspect = self.celery_app.control.inspect()
            active_queues = inspect.active_queues()
            
            if active_queues:
                for worker, queues in active_queues.items():
                    for queue_info in queues:
                        queue_name = queue_info.get('name', 'unknown')
                        task_metrics.record_queue_size(queue_name, 0)  # Placeholder
        except Exception as exc:
            logger.error("Failed to collect queue sizes", error=str(exc))
    
    async def _check_worker_health(self) -> None:
        """Check worker health and mark offline workers"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)
        
        for worker_name, worker_stats in self.worker_stats.items():
            if worker_stats.last_heartbeat and worker_stats.last_heartbeat < cutoff_time:
                worker_stats.status = 'offline'
                logger.warning("Worker marked as offline", worker_name=worker_name)
    
    def _get_or_create_task_stats(self, task_name: str) -> TaskStats:
        """Get or create task statistics"""
        if task_name not in self.task_stats:
            self.task_stats[task_name] = TaskStats(task_name=task_name)
        return self.task_stats[task_name]
    
    def _get_or_create_queue_stats(self, queue_name: str) -> QueueStats:
        """Get or create queue statistics"""
        if queue_name not in self.queue_stats:
            self.queue_stats[queue_name] = QueueStats(queue_name=queue_name)
        return self.queue_stats[queue_name]
    
    def _get_or_create_worker_stats(self, worker_name: str) -> WorkerStats:
        """Get or create worker statistics"""
        if worker_name not in self.worker_stats:
            self.worker_stats[worker_name] = WorkerStats(worker_name=worker_name)
        return self.worker_stats[worker_name]
    
    def get_task_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get current task statistics"""
        return {
            name: {
                'total_count': stats.total_count,
                'success_count': stats.success_count,
                'failure_count': stats.failure_count,
                'retry_count': stats.retry_count,
                'success_rate': (stats.success_count / stats.total_count * 100) if stats.total_count > 0 else 0,
                'avg_duration': stats.avg_duration,
                'min_duration': stats.min_duration if stats.min_duration != float('inf') else 0,
                'max_duration': stats.max_duration,
                'last_execution': stats.last_execution.isoformat() if stats.last_execution else None
            }
            for name, stats in self.task_stats.items()
        }
    
    def get_queue_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get current queue statistics"""
        return {
            name: {
                'pending_count': stats.pending_count,
                'active_count': stats.active_count,
                'processed_count': stats.processed_count,
                'failed_count': stats.failed_count
            }
            for name, stats in self.queue_stats.items()
        }
    
    def get_worker_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get current worker statistics"""
        return {
            name: {
                'status': stats.status,
                'active_tasks': stats.active_tasks,
                'processed_tasks': stats.processed_tasks,
                'load_avg': stats.load_avg,
                'last_heartbeat': stats.last_heartbeat.isoformat() if stats.last_heartbeat else None
            }
            for name, stats in self.worker_stats.items()
        }


# Global task monitor instance
task_monitor = TaskMonitor()

# Export components
__all__ = [
    'TaskMonitor',
    'TaskStats',
    'QueueStats', 
    'WorkerStats',
    'task_monitor'
]
