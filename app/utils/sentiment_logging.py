"""
Sentiment analysis logging utilities with structured logging and correlation tracking
"""

import uuid
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager
from functools import wraps

import structlog
from prometheus_client import Counter, Histogram, Gauge, Summary

from app.schemas.deepseek import SentimentAnalysisResult, SentimentType

# Configure structured logger
logger = structlog.get_logger(__name__)

# Prometheus metrics for sentiment analysis
SENTIMENT_ANALYSIS_TOTAL = Counter(
    'sentiment_analysis_total',
    'Total number of sentiment analyses performed',
    ['hotel_id', 'sentiment_type', 'requires_attention']
)

SENTIMENT_ANALYSIS_DURATION = Histogram(
    'sentiment_analysis_duration_seconds',
    'Time spent on sentiment analysis',
    ['hotel_id', 'analysis_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

SENTIMENT_SCORE_DISTRIBUTION = Histogram(
    'sentiment_score_distribution',
    'Distribution of sentiment scores',
    ['hotel_id'],
    buckets=[-1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
)

SENTIMENT_CONFIDENCE_DISTRIBUTION = Histogram(
    'sentiment_confidence_distribution',
    'Distribution of sentiment confidence scores',
    ['hotel_id'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

STAFF_ALERTS_TOTAL = Counter(
    'staff_alerts_total',
    'Total number of staff alerts generated',
    ['hotel_id', 'alert_type', 'priority', 'urgency_level']
)

STAFF_ALERT_RESPONSE_TIME = Histogram(
    'staff_alert_response_time_seconds',
    'Time taken to respond to staff alerts',
    ['hotel_id', 'alert_type', 'priority'],
    buckets=[60, 300, 900, 1800, 3600, 7200, 14400]  # 1min to 4hours
)

NOTIFICATION_DELIVERY_TOTAL = Counter(
    'notification_delivery_total',
    'Total number of notifications sent',
    ['hotel_id', 'channel', 'status']
)

NOTIFICATION_DELIVERY_DURATION = Histogram(
    'notification_delivery_duration_seconds',
    'Time taken to deliver notifications',
    ['hotel_id', 'channel'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

AI_MODEL_PERFORMANCE = Summary(
    'ai_model_performance',
    'AI model performance metrics',
    ['hotel_id', 'model_type', 'metric_type']
)

SENTIMENT_TRENDS_GAUGE = Gauge(
    'sentiment_trends_current',
    'Current sentiment trend indicators',
    ['hotel_id', 'trend_type']
)


class SentimentLogger:
    """Enhanced logger for sentiment analysis operations"""
    
    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.logger = logger.bind(correlation_id=self.correlation_id)
    
    def log_sentiment_analysis_start(
        self,
        message_id: str,
        hotel_id: str,
        guest_id: str,
        message_content_length: int,
        analysis_type: str = "realtime"
    ) -> None:
        """Log start of sentiment analysis"""
        self.logger.info(
            "Sentiment analysis started",
            event_type="sentiment_analysis_start",
            message_id=message_id,
            hotel_id=hotel_id,
            guest_id=guest_id,
            message_content_length=message_content_length,
            analysis_type=analysis_type,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_sentiment_analysis_result(
        self,
        message_id: str,
        hotel_id: str,
        guest_id: str,
        result: SentimentAnalysisResult,
        processing_time_ms: float,
        analysis_type: str = "realtime"
    ) -> None:
        """Log sentiment analysis result"""
        # Update Prometheus metrics
        SENTIMENT_ANALYSIS_TOTAL.labels(
            hotel_id=hotel_id,
            sentiment_type=result.sentiment.value,
            requires_attention=str(result.requires_attention)
        ).inc()
        
        SENTIMENT_ANALYSIS_DURATION.labels(
            hotel_id=hotel_id,
            analysis_type=analysis_type
        ).observe(processing_time_ms / 1000.0)
        
        SENTIMENT_SCORE_DISTRIBUTION.labels(hotel_id=hotel_id).observe(result.score)
        SENTIMENT_CONFIDENCE_DISTRIBUTION.labels(hotel_id=hotel_id).observe(result.confidence)
        
        # Structured logging
        self.logger.info(
            "Sentiment analysis completed",
            event_type="sentiment_analysis_result",
            message_id=message_id,
            hotel_id=hotel_id,
            guest_id=guest_id,
            sentiment_type=result.sentiment.value,
            sentiment_score=result.score,
            confidence_score=result.confidence,
            requires_attention=result.requires_attention,
            keywords=result.keywords,
            processing_time_ms=processing_time_ms,
            analysis_type=analysis_type,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_sentiment_analysis_error(
        self,
        message_id: str,
        hotel_id: str,
        error: str,
        error_type: str,
        processing_time_ms: float,
        analysis_type: str = "realtime"
    ) -> None:
        """Log sentiment analysis error"""
        self.logger.error(
            "Sentiment analysis failed",
            event_type="sentiment_analysis_error",
            message_id=message_id,
            hotel_id=hotel_id,
            error=error,
            error_type=error_type,
            processing_time_ms=processing_time_ms,
            analysis_type=analysis_type,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_staff_alert_created(
        self,
        alert_id: str,
        message_id: str,
        hotel_id: str,
        guest_id: str,
        alert_type: str,
        priority: str,
        urgency_level: int,
        sentiment_score: float
    ) -> None:
        """Log staff alert creation"""
        # Update Prometheus metrics
        STAFF_ALERTS_TOTAL.labels(
            hotel_id=hotel_id,
            alert_type=alert_type,
            priority=priority,
            urgency_level=str(urgency_level)
        ).inc()
        
        # Structured logging
        self.logger.info(
            "Staff alert created",
            event_type="staff_alert_created",
            alert_id=alert_id,
            message_id=message_id,
            hotel_id=hotel_id,
            guest_id=guest_id,
            alert_type=alert_type,
            priority=priority,
            urgency_level=urgency_level,
            sentiment_score=sentiment_score,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_staff_alert_acknowledged(
        self,
        alert_id: str,
        hotel_id: str,
        acknowledged_by: str,
        response_time_seconds: int
    ) -> None:
        """Log staff alert acknowledgment"""
        # Update Prometheus metrics
        STAFF_ALERT_RESPONSE_TIME.labels(
            hotel_id=hotel_id,
            alert_type="sentiment",  # Could be made dynamic
            priority="medium"  # Could be made dynamic
        ).observe(response_time_seconds)
        
        # Structured logging
        self.logger.info(
            "Staff alert acknowledged",
            event_type="staff_alert_acknowledged",
            alert_id=alert_id,
            hotel_id=hotel_id,
            acknowledged_by=acknowledged_by,
            response_time_seconds=response_time_seconds,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_notification_sent(
        self,
        alert_id: str,
        hotel_id: str,
        channel: str,
        status: str,
        delivery_time_ms: float,
        recipient: Optional[str] = None
    ) -> None:
        """Log notification delivery"""
        # Update Prometheus metrics
        NOTIFICATION_DELIVERY_TOTAL.labels(
            hotel_id=hotel_id,
            channel=channel,
            status=status
        ).inc()
        
        NOTIFICATION_DELIVERY_DURATION.labels(
            hotel_id=hotel_id,
            channel=channel
        ).observe(delivery_time_ms / 1000.0)
        
        # Structured logging
        self.logger.info(
            "Notification sent",
            event_type="notification_sent",
            alert_id=alert_id,
            hotel_id=hotel_id,
            channel=channel,
            status=status,
            delivery_time_ms=delivery_time_ms,
            recipient=recipient,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_ai_model_performance(
        self,
        hotel_id: str,
        model_type: str,
        metric_type: str,
        metric_value: float,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log AI model performance metrics"""
        # Update Prometheus metrics
        AI_MODEL_PERFORMANCE.labels(
            hotel_id=hotel_id,
            model_type=model_type,
            metric_type=metric_type
        ).observe(metric_value)
        
        # Structured logging
        self.logger.info(
            "AI model performance metric",
            event_type="ai_model_performance",
            hotel_id=hotel_id,
            model_type=model_type,
            metric_type=metric_type,
            metric_value=metric_value,
            context=context or {},
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_sentiment_trend_update(
        self,
        hotel_id: str,
        trend_type: str,
        trend_value: float,
        period: str,
        data_points: int
    ) -> None:
        """Log sentiment trend updates"""
        # Update Prometheus gauge
        SENTIMENT_TRENDS_GAUGE.labels(
            hotel_id=hotel_id,
            trend_type=trend_type
        ).set(trend_value)
        
        # Structured logging
        self.logger.info(
            "Sentiment trend updated",
            event_type="sentiment_trend_update",
            hotel_id=hotel_id,
            trend_type=trend_type,
            trend_value=trend_value,
            period=period,
            data_points=data_points,
            timestamp=datetime.utcnow().isoformat()
        )


@contextmanager
def sentiment_analysis_timing(
    logger_instance: SentimentLogger,
    message_id: str,
    hotel_id: str,
    analysis_type: str = "realtime"
):
    """Context manager for timing sentiment analysis operations"""
    start_time = time.time()
    try:
        yield
    finally:
        processing_time_ms = (time.time() - start_time) * 1000
        logger_instance.logger.debug(
            "Sentiment analysis timing",
            message_id=message_id,
            hotel_id=hotel_id,
            analysis_type=analysis_type,
            processing_time_ms=processing_time_ms
        )


def log_sentiment_operation(operation_type: str):
    """Decorator for logging sentiment operations"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            correlation_id = kwargs.get('correlation_id') or str(uuid.uuid4())
            sentiment_logger = SentimentLogger(correlation_id)
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                processing_time = (time.time() - start_time) * 1000
                
                sentiment_logger.logger.info(
                    f"Sentiment operation completed: {operation_type}",
                    operation_type=operation_type,
                    processing_time_ms=processing_time,
                    success=True
                )
                return result
                
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                sentiment_logger.logger.error(
                    f"Sentiment operation failed: {operation_type}",
                    operation_type=operation_type,
                    processing_time_ms=processing_time,
                    error=str(e),
                    success=False
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            correlation_id = kwargs.get('correlation_id') or str(uuid.uuid4())
            sentiment_logger = SentimentLogger(correlation_id)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                processing_time = (time.time() - start_time) * 1000
                
                sentiment_logger.logger.info(
                    f"Sentiment operation completed: {operation_type}",
                    operation_type=operation_type,
                    processing_time_ms=processing_time,
                    success=True
                )
                return result
                
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                sentiment_logger.logger.error(
                    f"Sentiment operation failed: {operation_type}",
                    operation_type=operation_type,
                    processing_time_ms=processing_time,
                    error=str(e),
                    success=False
                )
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def get_sentiment_logger(correlation_id: Optional[str] = None) -> SentimentLogger:
    """Get sentiment logger instance"""
    return SentimentLogger(correlation_id)


def log_sentiment_batch_operation(
    operation_type: str,
    hotel_id: str,
    batch_size: int,
    success_count: int,
    error_count: int,
    processing_time_ms: float,
    correlation_id: Optional[str] = None
) -> None:
    """Log batch sentiment operations"""
    sentiment_logger = SentimentLogger(correlation_id)
    
    sentiment_logger.logger.info(
        "Sentiment batch operation completed",
        event_type="sentiment_batch_operation",
        operation_type=operation_type,
        hotel_id=hotel_id,
        batch_size=batch_size,
        success_count=success_count,
        error_count=error_count,
        success_rate=success_count / batch_size if batch_size > 0 else 0,
        processing_time_ms=processing_time_ms,
        timestamp=datetime.utcnow().isoformat()
    )


def log_sentiment_system_health(
    hotel_id: str,
    health_metrics: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> None:
    """Log sentiment system health metrics"""
    sentiment_logger = SentimentLogger(correlation_id)
    
    sentiment_logger.logger.info(
        "Sentiment system health check",
        event_type="sentiment_system_health",
        hotel_id=hotel_id,
        health_metrics=health_metrics,
        timestamp=datetime.utcnow().isoformat()
    )
