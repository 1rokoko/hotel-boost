"""
Prometheus metrics for sentiment analysis monitoring
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import time

from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
import structlog

logger = structlog.get_logger(__name__)

# Create custom registry for sentiment metrics
sentiment_registry = CollectorRegistry()

# Sentiment Analysis Metrics
sentiment_analysis_requests = Counter(
    'sentiment_analysis_requests_total',
    'Total number of sentiment analysis requests',
    ['hotel_id', 'analysis_type', 'status'],
    registry=sentiment_registry
)

sentiment_analysis_duration = Histogram(
    'sentiment_analysis_duration_seconds',
    'Duration of sentiment analysis operations',
    ['hotel_id', 'analysis_type'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0],
    registry=sentiment_registry
)

sentiment_score_histogram = Histogram(
    'sentiment_score_distribution',
    'Distribution of sentiment scores',
    ['hotel_id'],
    buckets=[-1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    registry=sentiment_registry
)

sentiment_confidence_histogram = Histogram(
    'sentiment_confidence_distribution',
    'Distribution of sentiment confidence scores',
    ['hotel_id'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=sentiment_registry
)

# Alert Metrics
staff_alerts_created = Counter(
    'staff_alerts_created_total',
    'Total number of staff alerts created',
    ['hotel_id', 'alert_type', 'priority', 'urgency_level'],
    registry=sentiment_registry
)

staff_alerts_acknowledged = Counter(
    'staff_alerts_acknowledged_total',
    'Total number of staff alerts acknowledged',
    ['hotel_id', 'alert_type', 'priority'],
    registry=sentiment_registry
)

staff_alert_response_time = Histogram(
    'staff_alert_response_time_seconds',
    'Time taken to acknowledge staff alerts',
    ['hotel_id', 'alert_type', 'priority'],
    buckets=[30, 60, 300, 600, 1800, 3600, 7200, 14400, 28800],  # 30s to 8h
    registry=sentiment_registry
)

staff_alert_resolution_time = Histogram(
    'staff_alert_resolution_time_seconds',
    'Time taken to resolve staff alerts',
    ['hotel_id', 'alert_type', 'priority'],
    buckets=[300, 600, 1800, 3600, 7200, 14400, 28800, 86400],  # 5min to 24h
    registry=sentiment_registry
)

# Notification Metrics
notifications_sent = Counter(
    'notifications_sent_total',
    'Total number of notifications sent',
    ['hotel_id', 'channel', 'status'],
    registry=sentiment_registry
)

notification_delivery_time = Histogram(
    'notification_delivery_time_seconds',
    'Time taken to deliver notifications',
    ['hotel_id', 'channel'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=sentiment_registry
)

# AI Model Performance Metrics
ai_model_accuracy = Gauge(
    'ai_model_accuracy_score',
    'AI model accuracy score',
    ['hotel_id', 'model_type'],
    registry=sentiment_registry
)

ai_model_latency = Summary(
    'ai_model_latency_seconds',
    'AI model response latency',
    ['hotel_id', 'model_type'],
    registry=sentiment_registry
)

ai_model_tokens_used = Counter(
    'ai_model_tokens_used_total',
    'Total tokens used by AI model',
    ['hotel_id', 'model_type', 'operation'],
    registry=sentiment_registry
)

# System Health Metrics
sentiment_system_health = Gauge(
    'sentiment_system_health_score',
    'Overall sentiment system health score (0-1)',
    ['hotel_id', 'component'],
    registry=sentiment_registry
)

sentiment_processing_queue_size = Gauge(
    'sentiment_processing_queue_size',
    'Number of messages waiting for sentiment processing',
    ['hotel_id', 'queue_type'],
    registry=sentiment_registry
)

sentiment_error_rate = Gauge(
    'sentiment_error_rate',
    'Error rate for sentiment operations (0-1)',
    ['hotel_id', 'operation_type'],
    registry=sentiment_registry
)

# Business Metrics
guest_satisfaction_score = Gauge(
    'guest_satisfaction_score',
    'Calculated guest satisfaction score (0-100)',
    ['hotel_id', 'period'],
    registry=sentiment_registry
)

negative_sentiment_rate = Gauge(
    'negative_sentiment_rate',
    'Rate of negative sentiment messages (0-1)',
    ['hotel_id', 'period'],
    registry=sentiment_registry
)

sentiment_trend_direction = Gauge(
    'sentiment_trend_direction',
    'Sentiment trend direction (-1: declining, 0: stable, 1: improving)',
    ['hotel_id', 'period'],
    registry=sentiment_registry
)

# Escalation Metrics
alert_escalations = Counter(
    'alert_escalations_total',
    'Total number of alert escalations',
    ['hotel_id', 'escalation_level', 'reason'],
    registry=sentiment_registry
)

overdue_alerts = Gauge(
    'overdue_alerts_count',
    'Number of overdue alerts',
    ['hotel_id', 'priority'],
    registry=sentiment_registry
)

# Configuration and Rules Metrics
threshold_violations = Counter(
    'threshold_violations_total',
    'Total number of threshold violations',
    ['hotel_id', 'threshold_type'],
    registry=sentiment_registry
)

rule_evaluations = Counter(
    'rule_evaluations_total',
    'Total number of rule evaluations',
    ['hotel_id', 'rule_type', 'result'],
    registry=sentiment_registry
)


class SentimentMetricsCollector:
    """Collector for sentiment analysis metrics"""
    
    def __init__(self):
        self.start_time = time.time()
    
    def record_sentiment_analysis(
        self,
        hotel_id: str,
        analysis_type: str,
        status: str,
        duration_seconds: float,
        sentiment_score: float,
        confidence_score: float
    ) -> None:
        """Record sentiment analysis metrics"""
        try:
            # Record request
            sentiment_analysis_requests.labels(
                hotel_id=hotel_id,
                analysis_type=analysis_type,
                status=status
            ).inc()
            
            # Record duration
            sentiment_analysis_duration.labels(
                hotel_id=hotel_id,
                analysis_type=analysis_type
            ).observe(duration_seconds)
            
            # Record score distributions (only for successful analyses)
            if status == "success":
                sentiment_score_histogram.labels(hotel_id=hotel_id).observe(sentiment_score)
                sentiment_confidence_histogram.labels(hotel_id=hotel_id).observe(confidence_score)
                
        except Exception as e:
            logger.error("Failed to record sentiment analysis metrics", error=str(e))
    
    def record_staff_alert(
        self,
        hotel_id: str,
        alert_type: str,
        priority: str,
        urgency_level: int
    ) -> None:
        """Record staff alert creation"""
        try:
            staff_alerts_created.labels(
                hotel_id=hotel_id,
                alert_type=alert_type,
                priority=priority,
                urgency_level=str(urgency_level)
            ).inc()
        except Exception as e:
            logger.error("Failed to record staff alert metrics", error=str(e))
    
    def record_alert_acknowledgment(
        self,
        hotel_id: str,
        alert_type: str,
        priority: str,
        response_time_seconds: float
    ) -> None:
        """Record staff alert acknowledgment"""
        try:
            staff_alerts_acknowledged.labels(
                hotel_id=hotel_id,
                alert_type=alert_type,
                priority=priority
            ).inc()
            
            staff_alert_response_time.labels(
                hotel_id=hotel_id,
                alert_type=alert_type,
                priority=priority
            ).observe(response_time_seconds)
        except Exception as e:
            logger.error("Failed to record alert acknowledgment metrics", error=str(e))
    
    def record_alert_resolution(
        self,
        hotel_id: str,
        alert_type: str,
        priority: str,
        resolution_time_seconds: float
    ) -> None:
        """Record staff alert resolution"""
        try:
            staff_alert_resolution_time.labels(
                hotel_id=hotel_id,
                alert_type=alert_type,
                priority=priority
            ).observe(resolution_time_seconds)
        except Exception as e:
            logger.error("Failed to record alert resolution metrics", error=str(e))
    
    def record_notification(
        self,
        hotel_id: str,
        channel: str,
        status: str,
        delivery_time_seconds: float
    ) -> None:
        """Record notification delivery"""
        try:
            notifications_sent.labels(
                hotel_id=hotel_id,
                channel=channel,
                status=status
            ).inc()
            
            if status == "success":
                notification_delivery_time.labels(
                    hotel_id=hotel_id,
                    channel=channel
                ).observe(delivery_time_seconds)
        except Exception as e:
            logger.error("Failed to record notification metrics", error=str(e))
    
    def record_ai_model_performance(
        self,
        hotel_id: str,
        model_type: str,
        accuracy_score: float,
        latency_seconds: float,
        tokens_used: int,
        operation: str
    ) -> None:
        """Record AI model performance metrics"""
        try:
            ai_model_accuracy.labels(
                hotel_id=hotel_id,
                model_type=model_type
            ).set(accuracy_score)
            
            ai_model_latency.labels(
                hotel_id=hotel_id,
                model_type=model_type
            ).observe(latency_seconds)
            
            ai_model_tokens_used.labels(
                hotel_id=hotel_id,
                model_type=model_type,
                operation=operation
            ).inc(tokens_used)
        except Exception as e:
            logger.error("Failed to record AI model performance metrics", error=str(e))
    
    def update_system_health(
        self,
        hotel_id: str,
        component: str,
        health_score: float
    ) -> None:
        """Update system health metrics"""
        try:
            sentiment_system_health.labels(
                hotel_id=hotel_id,
                component=component
            ).set(health_score)
        except Exception as e:
            logger.error("Failed to update system health metrics", error=str(e))
    
    def update_business_metrics(
        self,
        hotel_id: str,
        period: str,
        satisfaction_score: float,
        negative_rate: float,
        trend_direction: float
    ) -> None:
        """Update business metrics"""
        try:
            guest_satisfaction_score.labels(
                hotel_id=hotel_id,
                period=period
            ).set(satisfaction_score)
            
            negative_sentiment_rate.labels(
                hotel_id=hotel_id,
                period=period
            ).set(negative_rate)
            
            sentiment_trend_direction.labels(
                hotel_id=hotel_id,
                period=period
            ).set(trend_direction)
        except Exception as e:
            logger.error("Failed to update business metrics", error=str(e))
    
    def record_escalation(
        self,
        hotel_id: str,
        escalation_level: str,
        reason: str
    ) -> None:
        """Record alert escalation"""
        try:
            alert_escalations.labels(
                hotel_id=hotel_id,
                escalation_level=escalation_level,
                reason=reason
            ).inc()
        except Exception as e:
            logger.error("Failed to record escalation metrics", error=str(e))
    
    def update_overdue_alerts(
        self,
        hotel_id: str,
        priority: str,
        count: int
    ) -> None:
        """Update overdue alerts count"""
        try:
            overdue_alerts.labels(
                hotel_id=hotel_id,
                priority=priority
            ).set(count)
        except Exception as e:
            logger.error("Failed to update overdue alerts metrics", error=str(e))
    
    def record_threshold_violation(
        self,
        hotel_id: str,
        threshold_type: str
    ) -> None:
        """Record threshold violation"""
        try:
            threshold_violations.labels(
                hotel_id=hotel_id,
                threshold_type=threshold_type
            ).inc()
        except Exception as e:
            logger.error("Failed to record threshold violation metrics", error=str(e))
    
    def record_rule_evaluation(
        self,
        hotel_id: str,
        rule_type: str,
        result: str
    ) -> None:
        """Record rule evaluation"""
        try:
            rule_evaluations.labels(
                hotel_id=hotel_id,
                rule_type=rule_type,
                result=result
            ).inc()
        except Exception as e:
            logger.error("Failed to record rule evaluation metrics", error=str(e))
    
    def get_metrics(self) -> str:
        """Get all metrics in Prometheus format"""
        return generate_latest(sentiment_registry)
    
    def get_metrics_content_type(self) -> str:
        """Get content type for metrics"""
        return CONTENT_TYPE_LATEST


# Global metrics collector instance
sentiment_metrics = SentimentMetricsCollector()


def get_sentiment_metrics() -> SentimentMetricsCollector:
    """Get sentiment metrics collector instance"""
    return sentiment_metrics
