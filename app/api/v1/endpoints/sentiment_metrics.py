"""
API endpoints for sentiment analysis metrics and monitoring
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.monitoring.sentiment_metrics import get_sentiment_metrics, SentimentMetricsCollector
from app.utils.sentiment_logging import get_sentiment_logger
from app.core.tenant import require_tenant_context
from app.middleware.tenant import get_current_tenant_id

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/prometheus", response_class=PlainTextResponse)
def get_prometheus_metrics(
    hotel_id: Optional[str] = Query(None, description="Filter metrics by hotel ID"),
    metrics_collector: SentimentMetricsCollector = Depends(get_sentiment_metrics)
):
    """
    Get sentiment analysis metrics in Prometheus format
    
    Args:
        hotel_id: Optional hotel ID filter
        metrics_collector: Metrics collector instance
        
    Returns:
        Prometheus formatted metrics
    """
    try:
        logger.info("Retrieving Prometheus metrics",
                   hotel_id=hotel_id)
        
        # Get all metrics
        metrics_data = metrics_collector.get_metrics()
        
        # Return with appropriate content type
        return Response(
            content=metrics_data,
            media_type=metrics_collector.get_metrics_content_type()
        )
        
    except Exception as e:
        logger.error("Failed to retrieve Prometheus metrics",
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@router.get("/health")
async def get_sentiment_system_health(
    hotel_id: str = Query(..., description="Hotel ID"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get sentiment system health status
    
    Args:
        hotel_id: Hotel ID
        db: Database session
        tenant_id: Current tenant ID
        
    Returns:
        System health status
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        logger.info("Getting sentiment system health",
                   hotel_id=hotel_id,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Check various system components
        health_status = _check_system_health(hotel_id, db, correlation_id)
        
        logger.info("Sentiment system health retrieved",
                   hotel_id=hotel_id,
                   overall_health=health_status["overall_health"],
                   correlation_id=correlation_id)
        
        return health_status
        
    except Exception as e:
        logger.error("Failed to get sentiment system health",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system health"
        )


@router.get("/performance")
async def get_sentiment_performance_metrics(
    hotel_id: str = Query(..., description="Hotel ID"),
    period: str = Query("24h", description="Time period (1h, 24h, 7d, 30d)"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get sentiment analysis performance metrics
    
    Args:
        hotel_id: Hotel ID
        period: Time period for metrics
        db: Database session
        tenant_id: Current tenant ID
        
    Returns:
        Performance metrics
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        logger.info("Getting sentiment performance metrics",
                   hotel_id=hotel_id,
                   period=period,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Get performance metrics
        performance_metrics = _get_performance_metrics(hotel_id, period, db, correlation_id)
        
        logger.info("Sentiment performance metrics retrieved",
                   hotel_id=hotel_id,
                   period=period,
                   correlation_id=correlation_id)
        
        return performance_metrics
        
    except Exception as e:
        logger.error("Failed to get sentiment performance metrics",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance metrics"
        )


@router.get("/alerts/metrics")
async def get_alert_metrics(
    hotel_id: str = Query(..., description="Hotel ID"),
    period: str = Query("24h", description="Time period (1h, 24h, 7d, 30d)"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get staff alert metrics
    
    Args:
        hotel_id: Hotel ID
        period: Time period for metrics
        db: Database session
        tenant_id: Current tenant ID
        
    Returns:
        Alert metrics
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        logger.info("Getting alert metrics",
                   hotel_id=hotel_id,
                   period=period,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Get alert metrics
        alert_metrics = _get_alert_metrics(hotel_id, period, db, correlation_id)
        
        logger.info("Alert metrics retrieved",
                   hotel_id=hotel_id,
                   period=period,
                   correlation_id=correlation_id)
        
        return alert_metrics
        
    except Exception as e:
        logger.error("Failed to get alert metrics",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alert metrics"
        )


@router.get("/ai-model/performance")
def get_ai_model_performance(
    hotel_id: str = Query(..., description="Hotel ID"),
    model_type: str = Query("deepseek", description="AI model type"),
    period: str = Query("24h", description="Time period (1h, 24h, 7d, 30d)"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get AI model performance metrics
    
    Args:
        hotel_id: Hotel ID
        model_type: Type of AI model
        period: Time period for metrics
        db: Database session
        tenant_id: Current tenant ID
        
    Returns:
        AI model performance metrics
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        logger.info("Getting AI model performance metrics",
                   hotel_id=hotel_id,
                   model_type=model_type,
                   period=period,
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Get AI model performance
        model_performance = _get_ai_model_performance(
            hotel_id, model_type, period, db, correlation_id
        )
        
        logger.info("AI model performance metrics retrieved",
                   hotel_id=hotel_id,
                   model_type=model_type,
                   correlation_id=correlation_id)
        
        return model_performance
        
    except Exception as e:
        logger.error("Failed to get AI model performance metrics",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve AI model performance"
        )


@router.post("/record")
def record_custom_metric(
    hotel_id: str = Query(..., description="Hotel ID"),
    metric_data: Dict[str, Any] = ...,
    metrics_collector: SentimentMetricsCollector = Depends(get_sentiment_metrics),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Record custom sentiment metric
    
    Args:
        hotel_id: Hotel ID
        metric_data: Metric data to record
        metrics_collector: Metrics collector instance
        tenant_id: Current tenant ID
        
    Returns:
        Success status
    """
    correlation_id = str(uuid.uuid4())
    
    try:
        logger.info("Recording custom sentiment metric",
                   hotel_id=hotel_id,
                   metric_type=metric_data.get("type"),
                   correlation_id=correlation_id)
        
        # Validate hotel access
        require_tenant_context(hotel_id, tenant_id)
        
        # Record metric based on type
        metric_type = metric_data.get("type")
        
        if metric_type == "sentiment_analysis":
            metrics_collector.record_sentiment_analysis(
                hotel_id=hotel_id,
                analysis_type=metric_data.get("analysis_type", "realtime"),
                status=metric_data.get("status", "success"),
                duration_seconds=metric_data.get("duration_seconds", 0.0),
                sentiment_score=metric_data.get("sentiment_score", 0.0),
                confidence_score=metric_data.get("confidence_score", 0.0)
            )
        elif metric_type == "staff_alert":
            metrics_collector.record_staff_alert(
                hotel_id=hotel_id,
                alert_type=metric_data.get("alert_type", "sentiment"),
                priority=metric_data.get("priority", "medium"),
                urgency_level=metric_data.get("urgency_level", 3)
            )
        elif metric_type == "notification":
            metrics_collector.record_notification(
                hotel_id=hotel_id,
                channel=metric_data.get("channel", "email"),
                status=metric_data.get("status", "success"),
                delivery_time_seconds=metric_data.get("delivery_time_seconds", 0.0)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown metric type: {metric_type}"
            )
        
        logger.info("Custom sentiment metric recorded",
                   hotel_id=hotel_id,
                   metric_type=metric_type,
                   correlation_id=correlation_id)
        
        return {"status": "success", "message": "Metric recorded successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to record custom sentiment metric",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record metric"
        )


def _check_system_health(
    hotel_id: str,
    db: Session,
    correlation_id: str
) -> Dict[str, Any]:
    """Check sentiment system health"""
    try:
        from app.models.sentiment import SentimentAnalysis
        from app.models.staff_alert import StaffAlert
        
        # Check recent sentiment analyses
        recent_analyses = db.query(SentimentAnalysis).filter(
            SentimentAnalysis.hotel_id == hotel_id,
            SentimentAnalysis.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).count()
        
        # Check pending alerts
        pending_alerts = db.query(StaffAlert).filter(
            StaffAlert.hotel_id == hotel_id,
            StaffAlert.status == "pending"
        ).count()
        
        # Calculate health scores
        analysis_health = min(1.0, recent_analyses / 10.0)  # Expect at least 10 analyses per hour
        alert_health = max(0.0, 1.0 - (pending_alerts / 20.0))  # Penalize too many pending alerts
        
        overall_health = (analysis_health + alert_health) / 2
        
        return {
            "overall_health": round(overall_health, 2),
            "components": {
                "sentiment_analysis": {
                    "health_score": round(analysis_health, 2),
                    "recent_analyses": recent_analyses,
                    "status": "healthy" if analysis_health > 0.7 else "degraded" if analysis_health > 0.3 else "unhealthy"
                },
                "alert_system": {
                    "health_score": round(alert_health, 2),
                    "pending_alerts": pending_alerts,
                    "status": "healthy" if alert_health > 0.7 else "degraded" if alert_health > 0.3 else "unhealthy"
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to check system health",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        return {
            "overall_health": 0.0,
            "components": {},
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


def _get_performance_metrics(
    hotel_id: str,
    period: str,
    db: Session,
    correlation_id: str
) -> Dict[str, Any]:
    """Get performance metrics for sentiment analysis"""
    try:
        # Parse period
        period_hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(period, 24)
        start_time = datetime.utcnow() - timedelta(hours=period_hours)
        
        from app.models.sentiment import SentimentAnalysis
        
        # Get sentiment analyses for period
        analyses = db.query(SentimentAnalysis).filter(
            SentimentAnalysis.hotel_id == hotel_id,
            SentimentAnalysis.created_at >= start_time
        ).all()
        
        if not analyses:
            return {
                "period": period,
                "total_analyses": 0,
                "average_processing_time_ms": 0,
                "success_rate": 0,
                "average_confidence": 0
            }
        
        # Calculate metrics
        total_analyses = len(analyses)
        processing_times = [a.processing_time_ms for a in analyses if a.processing_time_ms]
        confidence_scores = [a.confidence_score for a in analyses if a.confidence_score]
        
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        return {
            "period": period,
            "total_analyses": total_analyses,
            "average_processing_time_ms": round(avg_processing_time, 2),
            "success_rate": 1.0,  # Simplified - would calculate based on error logs
            "average_confidence": round(avg_confidence, 3),
            "analyses_per_hour": round(total_analyses / period_hours, 2)
        }
        
    except Exception as e:
        logger.error("Failed to get performance metrics",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        return {"error": str(e)}


def _get_alert_metrics(
    hotel_id: str,
    period: str,
    db: Session,
    correlation_id: str
) -> Dict[str, Any]:
    """Get alert metrics"""
    try:
        # Parse period
        period_hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(period, 24)
        start_time = datetime.utcnow() - timedelta(hours=period_hours)
        
        from app.models.staff_alert import StaffAlert
        
        # Get alerts for period
        alerts = db.query(StaffAlert).filter(
            StaffAlert.hotel_id == hotel_id,
            StaffAlert.created_at >= start_time
        ).all()
        
        if not alerts:
            return {
                "period": period,
                "total_alerts": 0,
                "pending_alerts": 0,
                "acknowledged_alerts": 0,
                "average_response_time_minutes": 0
            }
        
        # Calculate metrics
        total_alerts = len(alerts)
        pending_alerts = len([a for a in alerts if a.status == "pending"])
        acknowledged_alerts = len([a for a in alerts if a.acknowledged_at is not None])
        
        response_times = [a.response_time_minutes for a in alerts if a.response_time_minutes]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            "period": period,
            "total_alerts": total_alerts,
            "pending_alerts": pending_alerts,
            "acknowledged_alerts": acknowledged_alerts,
            "average_response_time_minutes": round(avg_response_time, 1),
            "acknowledgment_rate": round(acknowledged_alerts / total_alerts * 100, 1) if total_alerts > 0 else 0
        }
        
    except Exception as e:
        logger.error("Failed to get alert metrics",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        return {"error": str(e)}


def _get_ai_model_performance(
    hotel_id: str,
    model_type: str,
    period: str,
    db: Session,
    correlation_id: str
) -> Dict[str, Any]:
    """Get AI model performance metrics"""
    try:
        # This would typically query AI model performance logs
        # For now, return mock data
        return {
            "model_type": model_type,
            "period": period,
            "accuracy_score": 0.87,
            "average_latency_ms": 1250,
            "total_requests": 1543,
            "error_rate": 0.02,
            "tokens_used": 45670,
            "cost_estimate_usd": 12.45
        }
        
    except Exception as e:
        logger.error("Failed to get AI model performance",
                    hotel_id=hotel_id,
                    error=str(e),
                    correlation_id=correlation_id)
        return {"error": str(e)}
