"""
Prometheus metrics configuration for WhatsApp Hotel Bot
"""

from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
from typing import Dict, Optional
import time
import functools

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create custom registry for better control
REGISTRY = CollectorRegistry()

# Security Metrics (CRITICAL)
security_events_total = Counter(
    'security_events_total',
    'Total security events',
    ['event_type', 'severity'],  # event_type: failed_auth/invalid_signature/rate_limit_exceeded
    registry=REGISTRY
)

webhook_signature_validations = Counter(
    'webhook_signature_validations_total',
    'Webhook signature validation attempts',
    ['status'],  # status: valid/invalid/missing
    registry=REGISTRY
)

rate_limit_violations = Counter(
    'rate_limit_violations_total',
    'Rate limit violations',
    ['endpoint', 'user_type'],  # user_type: hotel/guest/admin
    registry=REGISTRY
)

# System Health Metrics (CRITICAL)
external_api_errors = Counter(
    'external_api_errors_total',
    'External API errors',
    ['api_name', 'error_type'],  # api_name: green_api/deepseek_api
    registry=REGISTRY
)

circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['service'],
    registry=REGISTRY
)

# Application info metric
app_info = Info(
    'whatsapp_hotel_bot_info',
    'Application information',
    registry=REGISTRY
)

# HTTP request metrics
http_requests_total = Counter(
    'whatsapp_hotel_bot_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=REGISTRY
)

http_request_duration_seconds = Histogram(
    'whatsapp_hotel_bot_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=REGISTRY
)

# Database metrics
database_connections_active = Gauge(
    'whatsapp_hotel_bot_database_connections_active',
    'Active database connections',
    registry=REGISTRY
)

database_query_duration_seconds = Histogram(
    'whatsapp_hotel_bot_database_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table'],
    registry=REGISTRY
)

database_queries_total = Counter(
    'whatsapp_hotel_bot_database_queries_total',
    'Total database queries',
    ['operation', 'table', 'status'],
    registry=REGISTRY
)

# External API metrics
external_api_requests_total = Counter(
    'whatsapp_hotel_bot_external_api_requests_total',
    'Total external API requests',
    ['service', 'endpoint', 'status_code'],
    registry=REGISTRY
)

external_api_request_duration_seconds = Histogram(
    'whatsapp_hotel_bot_external_api_request_duration_seconds',
    'External API request duration in seconds',
    ['service', 'endpoint'],
    registry=REGISTRY
)

# WhatsApp specific metrics
whatsapp_messages_sent_total = Counter(
    'whatsapp_hotel_bot_messages_sent_total',
    'Total WhatsApp messages sent',
    ['hotel_id', 'message_type', 'status'],
    registry=REGISTRY
)

whatsapp_messages_received_total = Counter(
    'whatsapp_hotel_bot_messages_received_total',
    'Total WhatsApp messages received',
    ['hotel_id', 'message_type'],
    registry=REGISTRY
)

whatsapp_webhooks_processed_total = Counter(
    'whatsapp_hotel_bot_webhooks_processed_total',
    'Total WhatsApp webhooks processed',
    ['webhook_type', 'status'],
    registry=REGISTRY
)

# AI/Sentiment analysis metrics
sentiment_analysis_requests_total = Counter(
    'whatsapp_hotel_bot_sentiment_analysis_requests_total',
    'Total sentiment analysis requests',
    ['sentiment_type', 'confidence_level'],
    registry=REGISTRY
)

sentiment_analysis_duration_seconds = Histogram(
    'whatsapp_hotel_bot_sentiment_analysis_duration_seconds',
    'Sentiment analysis duration in seconds',
    registry=REGISTRY
)

# Business metrics
active_hotels_total = Gauge(
    'whatsapp_hotel_bot_active_hotels_total',
    'Total number of active hotels',
    registry=REGISTRY
)

active_conversations_total = Gauge(
    'whatsapp_hotel_bot_active_conversations_total',
    'Total number of active conversations',
    registry=REGISTRY
)

triggers_executed_total = Counter(
    'whatsapp_hotel_bot_triggers_executed_total',
    'Total triggers executed',
    ['trigger_type', 'hotel_id', 'status'],
    registry=REGISTRY
)

# Error metrics
errors_total = Counter(
    'whatsapp_hotel_bot_errors_total',
    'Total errors',
    ['error_type', 'component'],
    registry=REGISTRY
)

# Performance metrics
response_time_percentiles = Histogram(
    'whatsapp_hotel_bot_response_time_seconds',
    'Response time percentiles',
    ['endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY
)

def init_metrics():
    """Initialize application metrics with basic info"""
    app_info.info({
        'version': settings.VERSION,
        'environment': settings.ENVIRONMENT,
        'service': 'whatsapp-hotel-bot'
    })

def track_http_request(method: str, endpoint: str, status_code: int, duration: float):
    """Track HTTP request metrics"""
    http_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code)
    ).inc()
    
    http_request_duration_seconds.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)
    
    response_time_percentiles.labels(endpoint=endpoint).observe(duration)

def track_database_query(operation: str, table: str, duration: float, success: bool = True):
    """Track database query metrics"""
    status = "success" if success else "error"
    
    database_queries_total.labels(
        operation=operation,
        table=table,
        status=status
    ).inc()
    
    database_query_duration_seconds.labels(
        operation=operation,
        table=table
    ).observe(duration)

def track_external_api_request(service: str, endpoint: str, status_code: int, duration: float):
    """Track external API request metrics"""
    external_api_requests_total.labels(
        service=service,
        endpoint=endpoint,
        status_code=str(status_code)
    ).inc()
    
    external_api_request_duration_seconds.labels(
        service=service,
        endpoint=endpoint
    ).observe(duration)

def track_whatsapp_message_sent(hotel_id: str, message_type: str, success: bool = True):
    """Track WhatsApp message sent metrics"""
    status = "success" if success else "error"
    whatsapp_messages_sent_total.labels(
        hotel_id=hotel_id,
        message_type=message_type,
        status=status
    ).inc()

def track_whatsapp_message_received(hotel_id: str, message_type: str):
    """Track WhatsApp message received metrics"""
    whatsapp_messages_received_total.labels(
        hotel_id=hotel_id,
        message_type=message_type
    ).inc()

def track_webhook_processed(webhook_type: str, success: bool = True):
    """Track webhook processing metrics"""
    status = "success" if success else "error"
    whatsapp_webhooks_processed_total.labels(
        webhook_type=webhook_type,
        status=status
    ).inc()

def track_sentiment_analysis(sentiment_type: str, confidence: float, duration: float):
    """Track sentiment analysis metrics"""
    # Categorize confidence levels
    if confidence >= 0.8:
        confidence_level = "high"
    elif confidence >= 0.6:
        confidence_level = "medium"
    else:
        confidence_level = "low"
    
    sentiment_analysis_requests_total.labels(
        sentiment_type=sentiment_type,
        confidence_level=confidence_level
    ).inc()
    
    sentiment_analysis_duration_seconds.observe(duration)

def track_error(error_type: str, component: str):
    """Track error metrics"""
    errors_total.labels(
        error_type=error_type,
        component=component
    ).inc()

def update_business_metrics(active_hotels: int, active_conversations: int):
    """Update business metrics"""
    active_hotels_total.set(active_hotels)
    active_conversations_total.set(active_conversations)

def track_trigger_execution(trigger_type: str, hotel_id: str, success: bool = True):
    """Track trigger execution metrics"""
    status = "success" if success else "error"
    triggers_executed_total.labels(
        trigger_type=trigger_type,
        hotel_id=hotel_id,
        status=status
    ).inc()

# Decorator for automatic metrics tracking
def track_performance(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to automatically track function performance"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Track success
                if labels:
                    response_time_percentiles.labels(**labels).observe(duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                # Track error
                track_error(type(e).__name__, func.__name__)
                
                raise
        return wrapper
    return decorator

# Async version of the decorator
def track_async_performance(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to automatically track async function performance"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Track success
                if labels:
                    response_time_percentiles.labels(**labels).observe(duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                # Track error
                track_error(type(e).__name__, func.__name__)
                
                raise
        return wrapper
    return decorator

# Additional tracking functions for performance optimization
def track_database_query(operation: str, table: str, duration: float, success: bool = True):
    """Track database query metrics"""
    try:
        database_queries_total.labels(
            operation=operation,
            table=table,
            status="success" if success else "error"
        ).inc()

        if success:
            database_query_duration.labels(
                operation=operation,
                table=table
            ).observe(duration)

    except Exception as e:
        logger.error("Failed to track database query metrics", error=str(e))


def track_cache_operation(operation: str, level: str, success: bool, duration_ms: float = 0):
    """Track cache operation metrics"""
    try:
        # This would be implemented with proper cache metrics
        # For now, we'll use a simple counter
        pass
    except Exception as e:
        logger.error("Failed to track cache operation metrics", error=str(e))


def track_memory_usage(memory_mb: float, memory_percent: float, gc_objects: int):
    """Track memory usage metrics"""
    try:
        # This would be implemented with proper memory metrics
        # For now, we'll use simple tracking
        pass
    except Exception as e:
        logger.error("Failed to track memory usage metrics", error=str(e))


def track_async_operation(operation_type: str, duration: float, success: bool):
    """Track async operation metrics"""
    try:
        # This would be implemented with proper async metrics
        # For now, we'll use simple tracking
        pass
    except Exception as e:
        logger.error("Failed to track async operation metrics", error=str(e))


# Initialize metrics on module import
if settings.PROMETHEUS_ENABLED:
    init_metrics()
