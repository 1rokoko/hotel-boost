"""
Celery tasks for reliability system maintenance and monitoring
"""

import asyncio
from typing import Dict, Any, List
from celery import Task
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.tasks.base import BaseTask, CriticalTask
from app.decorators.retry_decorator import retry_celery_tasks

logger = get_logger(__name__)


@celery_app.task(bind=True, base=CriticalTask, name="process_dead_letter_queue_batch")
@retry_celery_tasks(max_retries=3, base_delay=30.0)
def process_dead_letter_queue_batch(self: Task, batch_size: int = 20) -> Dict[str, Any]:
    """
    Process a batch of messages from the dead letter queue
    
    Args:
        batch_size: Number of messages to process in this batch
        
    Returns:
        Processing statistics
    """
    try:
        # Import here to avoid circular imports
        from app.services.failed_message_processor import get_failed_message_processor
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            processor = get_failed_message_processor()
            stats = loop.run_until_complete(
                processor.process_dlq_with_strategies(batch_size=batch_size)
            )
            
            logger.info("DLQ batch processing completed", 
                       task_id=self.request.id,
                       **stats)
            
            return stats
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("DLQ batch processing failed", 
                    task_id=self.request.id,
                    error=str(e))
        raise


@celery_app.task(bind=True, base=BaseTask, name="monitor_circuit_breakers")
def monitor_circuit_breakers(self: Task) -> Dict[str, Any]:
    """
    Monitor circuit breaker health and send alerts if needed
    
    Returns:
        Circuit breaker status summary
    """
    try:
        from app.utils.circuit_breaker import get_all_circuit_breakers
        
        circuit_breakers = get_all_circuit_breakers()
        
        # Collect statistics
        stats = {
            "total": len(circuit_breakers),
            "closed": 0,
            "open": 0,
            "half_open": 0,
            "alerts": []
        }
        
        for name, cb in circuit_breakers.items():
            state = cb.state.value
            stats[state] += 1
            
            metrics = cb.get_metrics()
            
            # Check for alerts
            if state == "open":
                stats["alerts"].append({
                    "type": "circuit_breaker_open",
                    "service": name,
                    "failure_rate": metrics.failure_rate(),
                    "total_requests": metrics.total_requests
                })
            
            elif metrics.failure_rate() > 0.5 and metrics.total_requests > 10:
                stats["alerts"].append({
                    "type": "high_failure_rate",
                    "service": name,
                    "failure_rate": metrics.failure_rate(),
                    "total_requests": metrics.total_requests
                })
        
        # Log alerts
        for alert in stats["alerts"]:
            logger.warning("Circuit breaker alert", 
                          task_id=self.request.id,
                          **alert)
        
        logger.info("Circuit breaker monitoring completed",
                   task_id=self.request.id,
                   **{k: v for k, v in stats.items() if k != "alerts"})
        
        return stats
        
    except Exception as e:
        logger.error("Circuit breaker monitoring failed",
                    task_id=self.request.id,
                    error=str(e))
        raise


@celery_app.task(bind=True, base=BaseTask, name="health_check_monitoring")
def health_check_monitoring(self: Task) -> Dict[str, Any]:
    """
    Perform comprehensive health checks and update system status
    
    Returns:
        Health check results
    """
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.services.health_checker import HealthChecker
            from app.utils.degradation_handler import get_degradation_handler
            
            health_checker = HealthChecker()
            degradation_handler = get_degradation_handler()
            
            # Perform health checks (without DB session for background task)
            system_health = loop.run_until_complete(
                health_checker.check_all_dependencies(db=None)
            )
            
            # Evaluate degradation rules
            loop.run_until_complete(degradation_handler.evaluate_rules())
            
            # Prepare results
            results = {
                "overall_status": system_health.overall_status.value,
                "total_check_time_ms": system_health.total_check_time_ms,
                "checks": {
                    name: {
                        "status": result.status.value,
                        "response_time_ms": result.response_time_ms,
                        "error": result.error
                    }
                    for name, result in system_health.checks.items()
                },
                "circuit_breakers": {
                    "total": len(system_health.circuit_breakers),
                    "open": sum(1 for cb in system_health.circuit_breakers.values() 
                              if cb["state"] == "open")
                }
            }
            
            # Log unhealthy services
            unhealthy_services = [
                name for name, result in system_health.checks.items()
                if result.status.value == "unhealthy"
            ]
            
            if unhealthy_services:
                logger.warning("Unhealthy services detected",
                             task_id=self.request.id,
                             services=unhealthy_services)
            
            logger.info("Health check monitoring completed",
                       task_id=self.request.id,
                       overall_status=system_health.overall_status.value,
                       unhealthy_count=len(unhealthy_services))
            
            return results
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("Health check monitoring failed",
                    task_id=self.request.id,
                    error=str(e))
        raise


@celery_app.task(bind=True, base=BaseTask, name="cleanup_old_dlq_messages")
def cleanup_old_dlq_messages(self: Task, max_age_days: int = 7) -> Dict[str, Any]:
    """
    Clean up old messages from dead letter queue
    
    Args:
        max_age_days: Maximum age of messages to keep
        
    Returns:
        Cleanup statistics
    """
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.tasks.dead_letter_handler import dlq_handler
            
            # Get all messages
            messages = loop.run_until_complete(dlq_handler.get_dlq_messages(limit=1000))
            
            # Find old messages
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            old_messages = [
                msg for msg in messages 
                if msg.first_failed_at < cutoff_date
            ]
            
            # Remove old messages (this would need to be implemented in DLQ handler)
            # For now, just log what would be removed
            stats = {
                "total_messages": len(messages),
                "old_messages": len(old_messages),
                "cutoff_date": cutoff_date.isoformat(),
                "removed": 0  # Would be actual count after implementation
            }
            
            if old_messages:
                logger.info("Old DLQ messages found for cleanup",
                           task_id=self.request.id,
                           count=len(old_messages),
                           cutoff_date=cutoff_date.isoformat())
            
            logger.info("DLQ cleanup completed",
                       task_id=self.request.id,
                       **stats)
            
            return stats
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("DLQ cleanup failed",
                    task_id=self.request.id,
                    error=str(e))
        raise


@celery_app.task(bind=True, base=BaseTask, name="generate_reliability_report")
def generate_reliability_report(self: Task) -> Dict[str, Any]:
    """
    Generate comprehensive reliability report
    
    Returns:
        Reliability report data
    """
    try:
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            from app.utils.circuit_breaker import get_all_circuit_breakers
            from app.services.fallback_service import fallback_service
            from app.utils.degradation_handler import get_degradation_handler
            from app.services.failed_message_processor import get_failed_message_processor
            
            # Collect data from all reliability components
            circuit_breakers = get_all_circuit_breakers()
            degradation_handler = get_degradation_handler()
            processor = get_failed_message_processor()
            
            # Circuit breaker summary
            cb_summary = {}
            for name, cb in circuit_breakers.items():
                metrics = cb.get_metrics()
                cb_summary[name] = {
                    "state": cb.state.value,
                    "total_requests": metrics.total_requests,
                    "success_rate": round(metrics.success_rate(), 3),
                    "failure_rate": round(metrics.failure_rate(), 3),
                    "circuit_open_count": metrics.circuit_open_count
                }
            
            # Degradation status
            degradation_status = degradation_handler.get_status()
            
            # DLQ analysis
            dlq_analysis = loop.run_until_complete(processor.analyze_failure_patterns())
            
            # Processing stats
            processing_stats = loop.run_until_complete(processor.get_processing_stats())
            
            report = {
                "timestamp": datetime.now().isoformat(),
                "circuit_breakers": cb_summary,
                "degradation": {
                    "current_level": degradation_status["current_level"],
                    "active_rules": degradation_status["active_rules"],
                    "recent_events": len(degradation_status.get("recent_events", []))
                },
                "dlq_analysis": dlq_analysis,
                "processing_stats": processing_stats,
                "fallback_status": fallback_service.get_degradation_status()
            }
            
            logger.info("Reliability report generated",
                       task_id=self.request.id,
                       circuit_breakers_count=len(cb_summary),
                       degradation_level=degradation_status["current_level"])
            
            return report
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error("Reliability report generation failed",
                    task_id=self.request.id,
                    error=str(e))
        raise


# Periodic task schedules
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic reliability tasks"""
    
    # Process DLQ every 5 minutes
    sender.add_periodic_task(
        300.0,  # 5 minutes
        process_dead_letter_queue_batch.s(batch_size=20),
        name='process-dlq-batch'
    )
    
    # Monitor circuit breakers every 2 minutes
    sender.add_periodic_task(
        120.0,  # 2 minutes
        monitor_circuit_breakers.s(),
        name='monitor-circuit-breakers'
    )
    
    # Health check monitoring every 1 minute
    sender.add_periodic_task(
        60.0,  # 1 minute
        health_check_monitoring.s(),
        name='health-check-monitoring'
    )
    
    # Generate reliability report every hour
    sender.add_periodic_task(
        3600.0,  # 1 hour
        generate_reliability_report.s(),
        name='reliability-report'
    )
    
    # Cleanup old DLQ messages daily
    sender.add_periodic_task(
        86400.0,  # 24 hours
        cleanup_old_dlq_messages.s(max_age_days=7),
        name='cleanup-old-dlq'
    )
