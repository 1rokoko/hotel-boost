"""
Admin monitoring endpoints
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.api.v1.endpoints.admin_auth import get_current_admin_user
from app.schemas.admin_monitoring import (
    SystemHealthResponse,
    AlertResponse,
    AlertListResponse,
    PerformanceMetricsResponse,
    ServiceStatusResponse
)
from app.services.admin_monitoring_service import (
    AdminMonitoringService,
    get_admin_monitoring_service
)
from app.models.admin_user import AdminPermission
from app.core.admin_security import AdminSecurity, AdminAuthorizationError

logger = structlog.get_logger(__name__)

router = APIRouter()


def require_permission(permission: AdminPermission):
    """Dependency to require specific permission"""
    async def check_permission(
        current_user = Depends(get_current_admin_user)
    ):
        try:
        monitoring_service = monitoringService(db)
            AdminSecurity.validate_admin_access(current_user, permission)
            return current_user
        except AdminAuthorizationError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
    return check_permission


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user = Depends(require_permission(AdminPermission.VIEW_MONITORING)),
    db: Session = Depends(get_db)
):
    """
    Get overall system health status
    
    Returns comprehensive system health information including:
    - Overall health score
    - Service status
    - Resource utilization
    - Recent issues
    """
    try:
        health_status = await monitoring_service.get_system_health()
        
        logger.info(
            "System health retrieved",
            user_id=str(current_user.id),
            health_score=health_status.overall_health_score
        )
        
        return health_status
        
    except Exception as e:
        logger.error("Error getting system health", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system health"
        )


@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$", description="Filter by severity"),
    status: Optional[str] = Query(None, regex="^(active|acknowledged|resolved)$", description="Filter by status"),
    hotel_id: Optional[uuid.UUID] = Query(None, description="Filter by hotel ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user = Depends(require_permission(AdminPermission.VIEW_MONITORING)),
    db: Session = Depends(get_db)
):
    """
    List system alerts with filtering and pagination
    """
    try:
        # Validate hotel access if hotel_id is specified
        if hotel_id and not current_user.can_access_hotel(hotel_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this hotel"
            )
        
        alerts, total = await monitoring_service.list_alerts(
            requesting_user=current_user,
            severity=severity,
            status=status,
            hotel_id=hotel_id,
            page=page,
            per_page=per_page
        )
        
        total_pages = (total + per_page - 1) // per_page
        
        return AlertListResponse(
            alerts=alerts,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing alerts", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list alerts"
        )


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.VIEW_MONITORING)),
    db: Session = Depends(get_db)
):
    """
    Get alert by ID
    """
    try:
        alert = await monitoring_service.get_alert(
            alert_id=alert_id,
            requesting_user=current_user
        )
        
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        return alert
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting alert", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get alert"
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: uuid.UUID,
    current_user = Depends(require_permission(AdminPermission.MANAGE_ALERTS)),
    db: Session = Depends(get_db)
):
    """
    Acknowledge an alert
    """
    try:
        success = await monitoring_service.acknowledge_alert(
            alert_id=alert_id,
            acknowledging_user=current_user
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        logger.info(
            "Alert acknowledged",
            user_id=str(current_user.id),
            alert_id=str(alert_id)
        )
        
        return {"message": "Alert acknowledged successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error acknowledging alert", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge alert"
        )


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: uuid.UUID,
    resolution_notes: Optional[str] = None,
    current_user = Depends(require_permission(AdminPermission.MANAGE_ALERTS)),
    db: Session = Depends(get_db)
):
    """
    Resolve an alert
    """
    try:
        success = await monitoring_service.resolve_alert(
            alert_id=alert_id,
            resolving_user=current_user,
            resolution_notes=resolution_notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        logger.info(
            "Alert resolved",
            user_id=str(current_user.id),
            alert_id=str(alert_id)
        )
        
        return {"message": "Alert resolved successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error resolving alert", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve alert"
        )


@router.get("/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    time_range: str = Query("1h", regex="^(1h|6h|24h|7d|30d)$", description="Time range for metrics"),
    current_user = Depends(require_permission(AdminPermission.VIEW_MONITORING)),
    db: Session = Depends(get_db)
):
    """
    Get system performance metrics
    
    Returns performance data including:
    - API response times
    - Database performance
    - Resource utilization
    - Throughput metrics
    """
    try:
        performance_metrics = await monitoring_service.get_performance_metrics(
            time_range=time_range
        )
        
        logger.info(
            "Performance metrics retrieved",
            user_id=str(current_user.id),
            time_range=time_range
        )
        
        return performance_metrics
        
    except Exception as e:
        logger.error("Error getting performance metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance metrics"
        )


@router.get("/services", response_model=ServiceStatusResponse)
async def get_service_status(
    current_user = Depends(require_permission(AdminPermission.VIEW_MONITORING)),
    db: Session = Depends(get_db)
):
    """
    Get status of all system services
    
    Returns status information for:
    - Core application services
    - External APIs (Green API, DeepSeek)
    - Database connections
    - Background workers
    """
    try:
        service_status = await monitoring_service.get_service_status()
        
        logger.info(
            "Service status retrieved",
            user_id=str(current_user.id)
        )
        
        return service_status
        
    except Exception as e:
        logger.error("Error getting service status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve service status"
        )


@router.get("/logs")
async def get_system_logs(
    level: str = Query("INFO", regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$", description="Log level filter"),
    service: Optional[str] = Query(None, description="Filter by service name"),
    start_time: Optional[datetime] = Query(None, description="Start time for log search"),
    end_time: Optional[datetime] = Query(None, description="End time for log search"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of log entries"),
    current_user = Depends(require_permission(AdminPermission.VIEW_MONITORING)),
    db: Session = Depends(get_db)
):
    """
    Get system logs with filtering
    """
    try:
        logs = await monitoring_service.get_system_logs(
            level=level,
            service=service,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        logger.info(
            "System logs retrieved",
            user_id=str(current_user.id),
            level=level,
            service=service,
            count=len(logs)
        )
        
        return {
            "logs": logs,
            "total": len(logs),
            "filters": {
                "level": level,
                "service": service,
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None
            }
        }
        
    except Exception as e:
        logger.error("Error getting system logs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system logs"
        )


@router.get("/metrics/realtime")
async def get_realtime_metrics(
    current_user = Depends(require_permission(AdminPermission.VIEW_MONITORING)),
    db: Session = Depends(get_db)
):
    """
    Get real-time system metrics
    
    Returns current system metrics including:
    - Active connections
    - Current load
    - Memory usage
    - Active processes
    """
    try:
        realtime_metrics = await monitoring_service.get_realtime_metrics()
        
        return realtime_metrics
        
    except Exception as e:
        logger.error("Error getting realtime metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve realtime metrics"
        )


@router.post("/test-alert")
async def create_test_alert(
    severity: str = Query("low", regex="^(low|medium|high|critical)$", description="Alert severity"),
    current_user = Depends(require_permission(AdminPermission.MANAGE_ALERTS)),
    db: Session = Depends(get_db)
):
    """
    Create a test alert for testing monitoring system
    """
    try:
        test_alert = await monitoring_service.create_test_alert(
            severity=severity,
            creating_user=current_user
        )
        
        logger.info(
            "Test alert created",
            user_id=str(current_user.id),
            alert_id=str(test_alert["id"]),
            severity=severity
        )
        
        return test_alert
        
    except Exception as e:
        logger.error("Error creating test alert", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create test alert"
        )
