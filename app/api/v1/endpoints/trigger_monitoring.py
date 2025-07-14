"""
Trigger monitoring API endpoints
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.monitoring.trigger_metrics import TriggerHealthChecker, trigger_metrics
from app.schemas.trigger_config import TriggerHealthCheck, TriggerDebugInfo
from app.middleware.tenant import get_current_tenant_id
from app.core.logging import get_logger

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=TriggerHealthCheck)
async def get_trigger_system_health(
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get trigger system health status
    
    Returns comprehensive health information about the trigger system
    including database connectivity, queue status, and performance metrics.
    """
    try:
        health_checker = TriggerHealthChecker()
        health_data = await health_checker.check_trigger_system_health()
        
        # Convert to schema format
        health_check = TriggerHealthCheck(
            status=health_data["status"],
            active_triggers=health_data.get("checks", {}).get("database", {}).get("active_triggers", 0),
            scheduled_tasks=health_data.get("checks", {}).get("celery", {}).get("queue_length", 0),
            failed_executions_last_hour=health_data.get("checks", {}).get("error_rates", {}).get("errors_last_hour", 0),
            queue_length=health_data.get("checks", {}).get("celery", {}).get("queue_length", 0),
            last_check=datetime.fromisoformat(health_data["timestamp"]),
            issues=[]
        )
        
        # Add issues from failed checks
        for check_name, check_data in health_data.get("checks", {}).items():
            if check_data.get("status") != "healthy":
                health_check.issues.append(f"{check_name}: {check_data.get('error', 'unhealthy')}")
        
        logger.info(
            "Trigger system health check completed",
            hotel_id=str(hotel_id),
            status=health_check.status,
            issues_count=len(health_check.issues)
        )
        
        return health_check
        
    except Exception as e:
        logger.error(
            "Error getting trigger system health",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system health"
        )


@router.get("/metrics")
def get_trigger_metrics(
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    hours: int = Query(24, ge=1, le=168, description="Hours of metrics to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Get trigger system metrics
    
    Returns Prometheus-style metrics for the trigger system including
    execution counts, durations, error rates, and performance data.
    """
    try:
        # In a real implementation, this would query actual metrics from Prometheus
        # For now, return mock data
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        metrics_data = {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours
            },
            "execution_metrics": {
                "total_executions": 1250,
                "successful_executions": 1188,
                "failed_executions": 62,
                "success_rate": 95.04,
                "avg_execution_time_ms": 145.7,
                "p95_execution_time_ms": 487.2,
                "p99_execution_time_ms": 892.1
            },
            "trigger_counts": {
                "total_triggers": 45,
                "active_triggers": 38,
                "inactive_triggers": 7,
                "scheduled_triggers": 156
            },
            "error_breakdown": {
                "template_errors": 15,
                "message_send_errors": 32,
                "evaluation_errors": 8,
                "system_errors": 7
            },
            "performance_trends": {
                "execution_time_trend": "stable",
                "error_rate_trend": "decreasing",
                "throughput_trend": "increasing"
            }
        }
        
        logger.info(
            "Trigger metrics retrieved",
            hotel_id=str(hotel_id),
            hours=hours,
            total_executions=metrics_data["execution_metrics"]["total_executions"]
        )
        
        return metrics_data
        
    except Exception as e:
        logger.error(
            "Error getting trigger metrics",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get metrics"
        )


@router.get("/debug/{trigger_id}", response_model=TriggerDebugInfo)
def get_trigger_debug_info(
    trigger_id: uuid.UUID,
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get debug information for a specific trigger
    
    Returns detailed debugging information including execution history,
    performance metrics, and error logs for troubleshooting.
    """
    try:
        # In a real implementation, this would query actual debug data
        # For now, return mock debug information
        debug_info = TriggerDebugInfo(
            trigger_id=trigger_id,
            current_state="active",
            last_evaluation=datetime.utcnow() - timedelta(minutes=15),
            evaluation_result=True,
            context_data={
                "last_guest_id": str(uuid.uuid4()),
                "last_execution_time": "2023-12-01T10:30:00Z",
                "conditions_evaluated": {
                    "time_based": True,
                    "guest_preferences": {"room_type": "suite"}
                }
            },
            error_log=[
                "2023-12-01T09:15:00Z: Template rendering warning - variable 'guest.middle_name' not found",
                "2023-12-01T08:45:00Z: Message send retry - temporary network error"
            ],
            performance_data={
                "avg_execution_time_ms": 156.7,
                "last_execution_time_ms": 142.3,
                "total_executions": 47,
                "success_rate": 97.87
            }
        )
        
        logger.info(
            "Trigger debug info retrieved",
            hotel_id=str(hotel_id),
            trigger_id=str(trigger_id),
            current_state=debug_info.current_state
        )
        
        return debug_info
        
    except Exception as e:
        logger.error(
            "Error getting trigger debug info",
            hotel_id=str(hotel_id),
            trigger_id=str(trigger_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get debug information"
        )


@router.get("/logs")
def get_trigger_logs(
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    trigger_id: Optional[uuid.UUID] = Query(None, description="Filter by trigger ID"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    hours: int = Query(24, ge=1, le=168, description="Hours of logs to retrieve"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of log entries"),
    db: Session = Depends(get_db)
):
    """
    Get trigger system logs
    
    Returns filtered log entries for debugging and monitoring purposes.
    """
    try:
        # In a real implementation, this would query actual log data
        # For now, return mock log entries
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        mock_logs = []
        for i in range(min(limit, 50)):  # Generate up to 50 mock entries
            log_time = start_time + timedelta(minutes=i * (hours * 60 / 50))
            mock_logs.append({
                "timestamp": log_time.isoformat(),
                "level": "INFO" if i % 4 != 0 else "ERROR",
                "event_type": "trigger_execution_completed" if i % 4 != 0 else "trigger_execution_failed",
                "trigger_id": str(trigger_id) if trigger_id else str(uuid.uuid4()),
                "message": f"Trigger execution {'completed' if i % 4 != 0 else 'failed'} in {120 + i * 5}ms",
                "metadata": {
                    "execution_time_ms": 120 + i * 5,
                    "guest_id": str(uuid.uuid4()),
                    "success": i % 4 != 0
                }
            })
        
        # Apply level filter if specified
        if level:
            mock_logs = [log for log in mock_logs if log["level"] == level.upper()]
        
        logs_data = {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours
            },
            "filters": {
                "trigger_id": str(trigger_id) if trigger_id else None,
                "level": level,
                "limit": limit
            },
            "total_entries": len(mock_logs),
            "logs": mock_logs
        }
        
        logger.info(
            "Trigger logs retrieved",
            hotel_id=str(hotel_id),
            trigger_id=str(trigger_id) if trigger_id else None,
            level=level,
            hours=hours,
            entries_count=len(mock_logs)
        )
        
        return logs_data
        
    except Exception as e:
        logger.error(
            "Error getting trigger logs",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get logs"
        )


@router.post("/alerts/test")
async def test_trigger_alerts(
    hotel_id: uuid.UUID = Depends(get_current_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Test trigger alerting system
    
    Sends a test alert to verify the alerting system is working correctly.
    """
    try:
        from app.monitoring.trigger_metrics import TriggerAlerting
        
        alerting = TriggerAlerting()
        
        # Create a mock unhealthy status for testing
        test_health_status = {
            "status": "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "test": {
                    "status": "unhealthy",
                    "error": "Test alert triggered manually"
                }
            }
        }
        
        await alerting._send_alert(test_health_status)
        
        logger.info(
            "Test alert sent",
            hotel_id=str(hotel_id)
        )
        
        return {
            "success": True,
            "message": "Test alert sent successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(
            "Error sending test alert",
            hotel_id=str(hotel_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test alert"
        )


# Export router
__all__ = ['router']
