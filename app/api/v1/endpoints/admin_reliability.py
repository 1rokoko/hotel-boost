"""
Administrative endpoints for reliability system management
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.api.v1.endpoints.admin_auth import get_current_admin_user
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/reliability", tags=["admin", "reliability"])


@router.get("/circuit-breakers")
def get_circuit_breakers_admin(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get detailed circuit breaker information for admin
    """
    from app.utils.circuit_breaker import get_all_circuit_breakers
    
    circuit_breakers = get_all_circuit_breakers()
    detailed_info = {}
    
    for name, cb in circuit_breakers.items():
        metrics = cb.get_metrics()
        detailed_info[name] = {
            "name": name,
            "state": cb.state.value,
            "config": {
                "failure_threshold": cb.config.failure_threshold,
                "recovery_timeout": cb.config.recovery_timeout,
                "success_threshold": cb.config.success_threshold,
                "timeout": cb.config.timeout,
                "window_size": cb.config.window_size,
                "minimum_requests": cb.config.minimum_requests
            },
            "metrics": {
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": round(metrics.success_rate(), 3),
                "failure_rate": round(metrics.failure_rate(), 3),
                "circuit_open_count": metrics.circuit_open_count,
                "last_failure_time": metrics.last_failure_time.isoformat() if metrics.last_failure_time else None,
                "last_success_time": metrics.last_success_time.isoformat() if metrics.last_success_time else None
            },
            "request_window_size": len(cb.request_window)
        }
    
    return {
        "circuit_breakers": detailed_info,
        "summary": {
            "total": len(circuit_breakers),
            "closed": sum(1 for cb in circuit_breakers.values() if cb.state.value == "closed"),
            "open": sum(1 for cb in circuit_breakers.values() if cb.state.value == "open"),
            "half_open": sum(1 for cb in circuit_breakers.values() if cb.state.value == "half_open")
        }
    }


@router.post("/circuit-breakers/{service_name}/reset")
def reset_circuit_breaker(
    service_name: str,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Reset a specific circuit breaker
    """
    from app.utils.circuit_breaker import get_all_circuit_breakers
    
    circuit_breakers = get_all_circuit_breakers()
    
    if service_name not in circuit_breakers:
        raise HTTPException(status_code=404, detail=f"Circuit breaker '{service_name}' not found")
    
    cb = circuit_breakers[service_name]
    old_state = cb.state.value
    cb.reset()
    
    logger.info("Circuit breaker reset by admin",
               service=service_name,
               admin_user=current_user.email,
               old_state=old_state)
    
    return {
        "message": f"Circuit breaker '{service_name}' reset successfully",
        "old_state": old_state,
        "new_state": cb.state.value
    }


@router.post("/circuit-breakers/reset-all")
def reset_all_circuit_breakers(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Reset all circuit breakers
    """
    from app.utils.circuit_breaker import reset_all_circuit_breakers
    
    reset_all_circuit_breakers()
    
    logger.warning("All circuit breakers reset by admin",
                  admin_user=current_user.email)
    
    return {"message": "All circuit breakers reset successfully"}


@router.get("/degradation")
def get_degradation_status_admin(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get detailed degradation status for admin
    """
    from app.services.fallback_service import fallback_service
    from app.utils.degradation_handler import get_degradation_handler
    
    degradation_handler = get_degradation_handler()
    
    return {
        "current_status": fallback_service.get_degradation_status(),
        "handler_status": degradation_handler.get_status(),
        "recent_events": degradation_handler.get_recent_events(50),
        "rules": [
            {
                "name": rule.name,
                "priority": rule.priority,
                "target_level": rule.target_level.value,
                "description": rule.description,
                "cooldown_seconds": rule.cooldown_seconds
            }
            for rule in degradation_handler.rules
        ]
    }


@router.post("/degradation/set-level")
def set_degradation_level(
    level: str,
    reason: str,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Manually set degradation level
    """
    from app.services.fallback_service import fallback_service, DegradationLevel
    
    try:
        fallback_service = fallbackService(db)
        degradation_level = DegradationLevel(level)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid degradation level. Must be one of: {[l.value for l in DegradationLevel]}"
        )
    
    old_level = fallback_service.current_degradation_level
    fallback_service.set_degradation_level(degradation_level, f"Manual override by admin: {reason}")
    
    logger.warning("Degradation level manually set by admin",
                  admin_user=current_user.email,
                  old_level=old_level.value,
                  new_level=level,
                  reason=reason)
    
    return {
        "message": f"Degradation level set to {level}",
        "old_level": old_level.value,
        "new_level": level,
        "reason": reason
    }


@router.get("/dlq")
async def get_dlq_status_admin(
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get dead letter queue status and messages for admin
    """
    from app.tasks.dead_letter_handler import dlq_handler
    from app.services.failed_message_processor import get_failed_message_processor
    
    processor = get_failed_message_processor()
    
    # Get DLQ messages
    messages = await dlq_handler.get_dlq_messages(limit=limit)
    
    # Get statistics
    dlq_stats = await dlq_handler.get_stats()
    processing_stats = await processor.get_processing_stats()
    failure_analysis = await processor.analyze_failure_patterns()
    
    # Convert messages to dict format
    message_list = []
    for msg in messages:
        message_list.append({
            "id": msg.id,
            "failure_reason": msg.failure_reason.value,
            "error_message": msg.error_message,
            "retry_count": msg.retry_count,
            "max_retries": msg.max_retries,
            "first_failed_at": msg.first_failed_at.isoformat(),
            "last_failed_at": msg.last_failed_at.isoformat(),
            "metadata": msg.metadata,
            "original_data_preview": str(msg.original_data)[:200] + "..." if len(str(msg.original_data)) > 200 else str(msg.original_data)
        })
    
    return {
        "messages": message_list,
        "stats": dlq_stats,
        "processing_stats": processing_stats,
        "failure_analysis": failure_analysis,
        "total_messages": len(messages)
    }


@router.post("/dlq/{message_id}/retry")
async def retry_dlq_message(
    message_id: str,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Manually retry a specific DLQ message
    """
    from app.tasks.dead_letter_handler import dlq_handler
    
    success = await dlq_handler.retry_message(message_id)
    
    logger.info("DLQ message retry initiated by admin",
               message_id=message_id,
               admin_user=current_user.email,
               success=success)
    
    return {
        "message_id": message_id,
        "retry_success": success,
        "message": "Retry successful" if success else "Retry failed"
    }


@router.post("/dlq/process-batch")
async def process_dlq_batch_admin(
    batch_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Manually process a batch of DLQ messages
    """
    from app.services.failed_message_processor import get_failed_message_processor
    
    processor = get_failed_message_processor()
    stats = await processor.process_dlq_with_strategies(batch_size=batch_size)
    
    logger.info("DLQ batch processing initiated by admin",
               batch_size=batch_size,
               admin_user=current_user.email,
               **stats)
    
    return {
        "batch_size": batch_size,
        "processing_stats": stats,
        "message": f"Processed {stats.get('processed', 0)} messages"
    }


@router.delete("/dlq/clear")
async def clear_dlq_admin(
    confirm: bool = Query(False),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Clear all messages from DLQ (DANGEROUS OPERATION)
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Must confirm DLQ clearing with confirm=true query parameter"
        )
    
    from app.tasks.dead_letter_handler import dlq_handler
    
    cleared_count = await dlq_handler.clear_dlq(confirm=True)
    
    logger.critical("DLQ cleared by admin",
                   admin_user=current_user.email,
                   messages_cleared=cleared_count)
    
    return {
        "message": f"DLQ cleared successfully",
        "messages_cleared": cleared_count,
        "warning": "This action cannot be undone"
    }


@router.get("/health-monitoring")
async def get_health_monitoring_admin(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get health monitoring status for admin
    """
    from app.utils.dependency_checker import dependency_monitor
    
    return {
        "dependency_summary": dependency_monitor.get_dependency_summary(),
        "monitoring_status": {
            "is_monitoring": dependency_monitor._monitoring,
            "registered_dependencies": len(dependency_monitor.dependencies)
        }
    }


@router.post("/health-monitoring/check-all")
async def check_all_dependencies_admin(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Manually trigger health check for all dependencies
    """
    from app.utils.dependency_checker import dependency_monitor
    
    status_map = await dependency_monitor.check_all_dependencies()
    
    logger.info("Manual health check triggered by admin",
               admin_user=current_user.email,
               dependencies_checked=len(status_map))
    
    return {
        "dependencies": {
            name: status.value for name, status in status_map.items()
        },
        "summary": dependency_monitor.get_dependency_summary()
    }


@router.get("/reports/reliability")
def generate_reliability_report_admin(
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Generate comprehensive reliability report for admin
    """
    from app.tasks.reliability_tasks import generate_reliability_report
    
    # Trigger report generation task
    task = generate_reliability_report.delay()
    
    logger.info("Reliability report generation triggered by admin",
               admin_user=current_user.email,
               task_id=task.id)
    
    return {
        "message": "Reliability report generation started",
        "task_id": task.id,
        "note": "Report will be available in task results"
    }
