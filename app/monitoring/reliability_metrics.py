"""
Prometheus metrics for reliability system monitoring
"""

from prometheus_client import Counter, Histogram, Gauge, Enum
from typing import Dict, Any
import time

from app.core.logging import get_logger

logger = get_logger(__name__)

# Circuit Breaker Metrics
circuit_breaker_requests_total = Counter(
    'circuit_breaker_requests_total',
    'Total number of requests through circuit breakers',
    ['service', 'state', 'result']
)

circuit_breaker_state = Enum(
    'circuit_breaker_state',
    'Current state of circuit breakers',
    ['service'],
    states=['closed', 'open', 'half_open']
)

circuit_breaker_failures_total = Counter(
    'circuit_breaker_failures_total',
    'Total number of circuit breaker failures',
    ['service', 'failure_type']
)

circuit_breaker_state_changes_total = Counter(
    'circuit_breaker_state_changes_total',
    'Total number of circuit breaker state changes',
    ['service', 'from_state', 'to_state']
)

circuit_breaker_response_time = Histogram(
    'circuit_breaker_response_time_seconds',
    'Response time of requests through circuit breakers',
    ['service'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

# Retry Metrics
retry_attempts_total = Counter(
    'retry_attempts_total',
    'Total number of retry attempts',
    ['service', 'strategy', 'result']
)

retry_delay_seconds = Histogram(
    'retry_delay_seconds',
    'Delay between retry attempts',
    ['service', 'strategy'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0]
)

# Health Check Metrics
health_check_duration_seconds = Histogram(
    'health_check_duration_seconds',
    'Duration of health checks',
    ['dependency'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

health_check_status = Enum(
    'health_check_status',
    'Current health status of dependencies',
    ['dependency'],
    states=['healthy', 'unhealthy', 'degraded', 'unknown']
)

health_check_total = Counter(
    'health_check_total',
    'Total number of health checks performed',
    ['dependency', 'status']
)

# Degradation Metrics
system_degradation_level = Enum(
    'system_degradation_level',
    'Current system degradation level',
    [],
    states=['normal', 'minor', 'moderate', 'severe', 'critical']
)

degradation_events_total = Counter(
    'degradation_events_total',
    'Total number of degradation events',
    ['rule', 'from_level', 'to_level']
)

fallback_usage_total = Counter(
    'fallback_usage_total',
    'Total number of fallback mechanism usages',
    ['service', 'fallback_type', 'result']
)

# Dead Letter Queue Metrics
dlq_messages_total = Gauge(
    'dlq_messages_total',
    'Total number of messages in dead letter queue'
)

dlq_messages_added_total = Counter(
    'dlq_messages_added_total',
    'Total number of messages added to DLQ',
    ['message_type', 'failure_reason']
)

dlq_messages_processed_total = Counter(
    'dlq_messages_processed_total',
    'Total number of DLQ messages processed',
    ['message_type', 'result']
)

dlq_processing_duration_seconds = Histogram(
    'dlq_processing_duration_seconds',
    'Duration of DLQ message processing',
    ['message_type'],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0]
)

# Dependency Monitoring Metrics
dependency_status = Enum(
    'dependency_status',
    'Current status of system dependencies',
    ['dependency'],
    states=['healthy', 'unhealthy', 'degraded', 'unknown']
)

dependency_check_duration_seconds = Histogram(
    'dependency_check_duration_seconds',
    'Duration of dependency checks',
    ['dependency'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)


class ReliabilityMetricsCollector:
    """
    Collector for reliability system metrics
    """
    
    def __init__(self):
        self.last_collection_time = time.time()
    
    def record_circuit_breaker_request(self, service: str, state: str, result: str, response_time: float = None):
        """Record circuit breaker request metrics"""
        circuit_breaker_requests_total.labels(service=service, state=state, result=result).inc()
        
        if response_time is not None:
            circuit_breaker_response_time.labels(service=service).observe(response_time)
    
    def record_circuit_breaker_state_change(self, service: str, from_state: str, to_state: str):
        """Record circuit breaker state change"""
        circuit_breaker_state_changes_total.labels(
            service=service, 
            from_state=from_state, 
            to_state=to_state
        ).inc()
        
        # Update current state
        circuit_breaker_state.labels(service=service).state(to_state)
    
    def record_circuit_breaker_failure(self, service: str, failure_type: str):
        """Record circuit breaker failure"""
        circuit_breaker_failures_total.labels(service=service, failure_type=failure_type).inc()
    
    def record_retry_attempt(self, service: str, strategy: str, result: str, delay: float = None):
        """Record retry attempt metrics"""
        retry_attempts_total.labels(service=service, strategy=strategy, result=result).inc()
        
        if delay is not None:
            retry_delay_seconds.labels(service=service, strategy=strategy).observe(delay)
    
    def record_health_check(self, dependency: str, status: str, duration: float):
        """Record health check metrics"""
        health_check_total.labels(dependency=dependency, status=status).inc()
        health_check_duration_seconds.labels(dependency=dependency).observe(duration)
        health_check_status.labels(dependency=dependency).state(status)
    
    def record_degradation_event(self, rule: str, from_level: str, to_level: str):
        """Record degradation event"""
        degradation_events_total.labels(rule=rule, from_level=from_level, to_level=to_level).inc()
        system_degradation_level.state(to_level)
    
    def record_fallback_usage(self, service: str, fallback_type: str, result: str):
        """Record fallback mechanism usage"""
        fallback_usage_total.labels(service=service, fallback_type=fallback_type, result=result).inc()
    
    def record_dlq_message_added(self, message_type: str, failure_reason: str):
        """Record message added to DLQ"""
        dlq_messages_added_total.labels(message_type=message_type, failure_reason=failure_reason).inc()
    
    def record_dlq_message_processed(self, message_type: str, result: str, duration: float = None):
        """Record DLQ message processing"""
        dlq_messages_processed_total.labels(message_type=message_type, result=result).inc()
        
        if duration is not None:
            dlq_processing_duration_seconds.labels(message_type=message_type).observe(duration)
    
    def update_dlq_queue_size(self, size: int):
        """Update DLQ queue size gauge"""
        dlq_messages_total.set(size)
    
    def record_dependency_check(self, dependency: str, status: str, duration: float):
        """Record dependency check"""
        dependency_check_duration_seconds.labels(dependency=dependency).observe(duration)
        dependency_status.labels(dependency=dependency).state(status)
    
    def collect_circuit_breaker_metrics(self):
        """Collect current circuit breaker metrics"""
        try:
            from app.utils.circuit_breaker import get_all_circuit_breakers
            
            circuit_breakers = get_all_circuit_breakers()
            
            for name, cb in circuit_breakers.items():
                # Update current state
                circuit_breaker_state.labels(service=name).state(cb.state.value)
                
                # Get metrics
                metrics = cb.get_metrics()
                
                # Update gauges (these don't auto-increment, so we set them)
                # Note: Prometheus counters should only increase, so we don't update them here
                # They are updated when actual events occur
                
        except Exception as e:
            logger.error("Failed to collect circuit breaker metrics", error=str(e))
    
    def collect_degradation_metrics(self):
        """Collect current degradation metrics"""
        try:
            from app.services.fallback_service import fallback_service
            
            current_level = fallback_service.current_degradation_level.value
            system_degradation_level.state(current_level)
            
        except Exception as e:
            logger.error("Failed to collect degradation metrics", error=str(e))
    
    def collect_dlq_metrics(self):
        """Collect current DLQ metrics"""
        try:
            import asyncio
            from app.tasks.dead_letter_handler import dlq_handler
            
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                stats = loop.run_until_complete(dlq_handler.get_stats())
                queue_size = stats.get('current_queue_size', 0)
                dlq_messages_total.set(queue_size)
            finally:
                loop.close()
                
        except Exception as e:
            logger.error("Failed to collect DLQ metrics", error=str(e))
    
    def collect_all_metrics(self):
        """Collect all reliability metrics"""
        current_time = time.time()
        
        # Only collect every 30 seconds to avoid overhead
        if current_time - self.last_collection_time < 30:
            return
        
        self.collect_circuit_breaker_metrics()
        self.collect_degradation_metrics()
        self.collect_dlq_metrics()
        
        self.last_collection_time = current_time


# Global metrics collector instance
reliability_metrics = ReliabilityMetricsCollector()


def get_reliability_metrics() -> ReliabilityMetricsCollector:
    """Get the global reliability metrics collector"""
    return reliability_metrics
