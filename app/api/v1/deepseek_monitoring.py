"""
API endpoints for DeepSeek monitoring and metrics
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.services.deepseek_monitoring import get_monitoring_service
from app.core.deepseek_logging import get_deepseek_metrics, get_deepseek_recent_logs
from app.models.hotel import Hotel
from app.api.v1.endpoints.auth import get_current_user
from app.utils.permission_checker import require_permission
from app.models.user import User
from app.models.role import UserPermission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/deepseek", tags=["DeepSeek Monitoring"])


@router.get("/health", response_model=Dict[str, Any])
async def get_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive system health report for DeepSeek AI services
    
    Returns real-time metrics, performance alerts, and system status.
    """
    try:
        monitoring_service = get_monitoring_service(db)
        health_report = await monitoring_service.get_system_health_report()
        
        logger.info("System health report requested",
                   user_id=str(current_user.id),
                   system_status=health_report.get('system_status'))
        
        return health_report
        
    except Exception as e:
        logger.error("Failed to get system health report", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve system health")


@router.get("/metrics", response_model=Dict[str, Any])
async def get_real_time_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get real-time DeepSeek API metrics
    
    Returns current performance metrics including:
    - Requests per minute
    - Average response time
    - Error rate
    - Token usage
    - Sentiment distribution
    """
    try:
        monitoring_service = get_monitoring_service(db)
        metrics = monitoring_service.get_real_time_metrics()
        
        # Add global metrics
        global_metrics = get_deepseek_metrics()
        
        response = {
            'real_time': metrics,
            'global': global_metrics,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return response
        
    except Exception as e:
        logger.error("Failed to get real-time metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_performance_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current performance alerts
    
    Returns list of active alerts for:
    - High response times
    - High error rates
    - High token usage
    - Low confidence scores
    """
    try:
        monitoring_service = get_monitoring_service(db)
        alerts = monitoring_service.check_performance_alerts()
        
        logger.info("Performance alerts requested",
                   user_id=str(current_user.id),
                   alert_count=len(alerts))
        
        return alerts
        
    except Exception as e:
        logger.error("Failed to get performance alerts", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.get("/hotels/{hotel_id}/sentiment-metrics", response_model=Dict[str, Any])
async def get_hotel_sentiment_metrics(
    hotel_id: str = Path(..., description="Hotel ID"),
    days_back: int = Query(7, ge=1, le=30, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get sentiment analysis metrics for a specific hotel
    
    Returns:
    - Sentiment distribution
    - Average sentiment and confidence scores
    - Messages requiring attention
    - Trends over time
    """
    try:
        # Validate hotel exists and user has access
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        # TODO: Add proper authorization check for hotel access
        
        monitoring_service = get_monitoring_service(db)
        metrics = await monitoring_service.get_hotel_sentiment_metrics(hotel_id, days_back)
        
        if not metrics:
            raise HTTPException(status_code=404, detail="No sentiment data found for hotel")
        
        logger.info("Hotel sentiment metrics requested",
                   hotel_id=hotel_id,
                   days_back=days_back,
                   user_id=str(current_user.id))
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get hotel sentiment metrics",
                    hotel_id=hotel_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve hotel metrics")


@router.get("/logs", response_model=List[Dict[str, Any]])
async def get_operation_logs(
    limit: int = Query(50, ge=1, le=500, description="Number of logs to retrieve"),
    operation_type: Optional[str] = Query(None, description="Filter by operation type"),
    hotel_id: Optional[str] = Query(None, description="Filter by hotel ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(UserPermission.VIEW_MONITORING))
):
    """
    Get DeepSeek operation logs
    
    Requires admin or support permissions.
    Returns recent operation logs with optional filtering.
    """
    try:
        logs = get_deepseek_recent_logs(limit)
        
        # Apply filters
        if operation_type:
            logs = [log for log in logs if log.operation_type == operation_type]
        
        if hotel_id:
            logs = [log for log in logs if log.hotel_id == hotel_id]
        
        # Convert to dict format
        log_data = []
        for log in logs:
            log_dict = {
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'operation_type': log.operation_type,
                'hotel_id': log.hotel_id,
                'guest_id': log.guest_id,
                'message_id': log.message_id,
                'model_used': log.model_used,
                'tokens_used': log.tokens_used,
                'api_response_time_ms': log.api_response_time_ms,
                'success': log.success,
                'error_message': log.error_message,
                'correlation_id': log.correlation_id
            }
            log_data.append(log_dict)
        
        logger.info("Operation logs requested",
                   user_id=str(current_user.id),
                   limit=limit,
                   operation_type=operation_type,
                   hotel_id=hotel_id,
                   returned_count=len(log_data))
        
        return log_data
        
    except Exception as e:
        logger.error("Failed to get operation logs", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve logs")


@router.get("/export", response_model=Dict[str, str])
async def export_metrics(
    include_logs: bool = Query(False, description="Include operation logs in export"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(UserPermission.EXPORT_DATA))
):
    """
    Export all metrics and logs as JSON
    
    Requires admin permissions.
    Returns comprehensive data export for analysis or backup.
    """
    try:
        monitoring_service = get_monitoring_service(db)
        export_data = monitoring_service.export_metrics_json(include_logs=include_logs)
        
        logger.info("Metrics export requested",
                   user_id=str(current_user.id),
                   include_logs=include_logs)
        
        return {
            'export_data': export_data,
            'timestamp': datetime.utcnow().isoformat(),
            'exported_by': str(current_user.id)
        }
        
    except Exception as e:
        logger.error("Failed to export metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to export metrics")


@router.post("/hotels/{hotel_id}/generate-summary")
async def generate_daily_sentiment_summary(
    hotel_id: str = Path(..., description="Hotel ID"),
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (defaults to yesterday)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(UserPermission.GENERATE_REPORTS))
):
    """
    Generate daily sentiment summary for a hotel
    
    Creates or updates daily sentiment summary with aggregated metrics.
    """
    try:
        # Validate hotel exists
        hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
        if not hotel:
            raise HTTPException(status_code=404, detail="Hotel not found")
        
        # Parse date or use yesterday
        if date:
            try:
                summary_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            summary_date = datetime.utcnow() - timedelta(days=1)
        
        monitoring_service = get_monitoring_service(db)
        summary = await monitoring_service.generate_daily_sentiment_summary(hotel_id, summary_date)
        
        if not summary:
            raise HTTPException(status_code=404, detail="No sentiment data found for the specified date")
        
        logger.info("Daily sentiment summary generated",
                   hotel_id=hotel_id,
                   date=summary_date.date(),
                   user_id=str(current_user.id))
        
        return {
            'summary_id': str(summary.id),
            'hotel_id': hotel_id,
            'date': summary_date.date().isoformat(),
            'total_messages': summary.total_messages,
            'positive_percentage': summary.positive_percentage,
            'negative_percentage': summary.negative_percentage,
            'attention_percentage': summary.attention_percentage,
            'average_sentiment_score': summary.average_sentiment_score,
            'average_confidence_score': summary.average_confidence_score
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate daily sentiment summary",
                    hotel_id=hotel_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate summary")


@router.get("/performance/trends")
async def get_performance_trends(
    hours_back: int = Query(24, ge=1, le=168, description="Hours to look back (max 7 days)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get performance trends over time
    
    Returns historical performance data for trend analysis.
    """
    try:
        # This would typically query a time-series database or aggregated metrics
        # For now, return current metrics as a placeholder
        monitoring_service = get_monitoring_service(db)
        current_metrics = monitoring_service.get_real_time_metrics()
        
        # TODO: Implement actual trend data collection and storage
        trends = {
            'period_hours': hours_back,
            'current_metrics': current_metrics,
            'trend_data': {
                'response_time_trend': 'stable',  # Would be calculated from historical data
                'error_rate_trend': 'improving',
                'token_usage_trend': 'increasing',
                'sentiment_trend': 'stable'
            },
            'recommendations': [
                "Monitor token usage growth",
                "Consider implementing additional caching",
                "Review error patterns for optimization opportunities"
            ]
        }
        
        logger.info("Performance trends requested",
                   user_id=str(current_user.id),
                   hours_back=hours_back)
        
        return trends
        
    except Exception as e:
        logger.error("Failed to get performance trends", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve trends")


# Export router
__all__ = ["router"]
