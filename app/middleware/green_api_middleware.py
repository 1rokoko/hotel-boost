"""
Green API monitoring middleware
"""

import time
import asyncio
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from datetime import datetime, timedelta
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.green_api_logging import get_green_api_logger, LoggingContext

logger = structlog.get_logger(__name__)


class GreenAPIMetrics:
    """Metrics collector for Green API operations"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        
        # Request metrics
        self.request_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        
        # Rate limiting metrics
        self.rate_limit_hits = 0
        self.rate_limit_waits = deque(maxlen=max_history)
        
        # Response time history
        self.response_times = deque(maxlen=max_history)
        
        # Error tracking
        self.errors_by_type = defaultdict(int)
        self.errors_by_status = defaultdict(int)
        
        # Instance metrics
        self.instance_metrics = defaultdict(lambda: {
            'requests': 0,
            'errors': 0,
            'last_request': None,
            'avg_response_time': 0.0
        })
        
        # Webhook metrics
        self.webhook_count = 0
        self.webhook_errors = 0
        self.webhooks_by_type = defaultdict(int)
        
        # Message metrics
        self.messages_sent = 0
        self.messages_received = 0
        self.messages_failed = 0
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def record_request(
        self,
        instance_id: Optional[str] = None,
        response_time: Optional[float] = None,
        status_code: Optional[int] = None,
        error: Optional[Exception] = None
    ):
        """Record API request metrics"""
        async with self._lock:
            self.request_count += 1
            
            if response_time is not None:
                self.total_response_time += response_time
                self.response_times.append(response_time)
            
            if error:
                self.error_count += 1
                self.errors_by_type[type(error).__name__] += 1
                
                if status_code:
                    self.errors_by_status[status_code] += 1
            
            if instance_id:
                metrics = self.instance_metrics[instance_id]
                metrics['requests'] += 1
                metrics['last_request'] = datetime.utcnow()
                
                if error:
                    metrics['errors'] += 1
                
                if response_time is not None:
                    # Update rolling average
                    current_avg = metrics['avg_response_time']
                    request_count = metrics['requests']
                    metrics['avg_response_time'] = (
                        (current_avg * (request_count - 1) + response_time) / request_count
                    )
    
    async def record_rate_limit(self, wait_time: float):
        """Record rate limiting event"""
        async with self._lock:
            self.rate_limit_hits += 1
            self.rate_limit_waits.append(wait_time)
    
    async def record_webhook(self, webhook_type: str, success: bool = True):
        """Record webhook metrics"""
        async with self._lock:
            self.webhook_count += 1
            self.webhooks_by_type[webhook_type] += 1
            
            if not success:
                self.webhook_errors += 1
    
    async def record_message(self, message_type: str, success: bool = True):
        """Record message metrics"""
        async with self._lock:
            if message_type == 'sent':
                if success:
                    self.messages_sent += 1
                else:
                    self.messages_failed += 1
            elif message_type == 'received':
                self.messages_received += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        avg_response_time = (
            self.total_response_time / max(self.request_count, 1)
        )
        
        error_rate = self.error_count / max(self.request_count, 1)
        
        # Calculate percentiles for response times
        response_times_list = list(self.response_times)
        response_times_list.sort()
        
        def percentile(data: List[float], p: float) -> float:
            if not data:
                return 0.0
            k = (len(data) - 1) * p
            f = int(k)
            c = k - f
            if f + 1 < len(data):
                return data[f] * (1 - c) + data[f + 1] * c
            else:
                return data[f]
        
        return {
            'requests': {
                'total': self.request_count,
                'errors': self.error_count,
                'error_rate': error_rate,
                'success_rate': 1 - error_rate
            },
            'response_times': {
                'average': avg_response_time,
                'p50': percentile(response_times_list, 0.5),
                'p95': percentile(response_times_list, 0.95),
                'p99': percentile(response_times_list, 0.99)
            },
            'rate_limiting': {
                'hits': self.rate_limit_hits,
                'average_wait': sum(self.rate_limit_waits) / max(len(self.rate_limit_waits), 1)
            },
            'webhooks': {
                'total': self.webhook_count,
                'errors': self.webhook_errors,
                'by_type': dict(self.webhooks_by_type)
            },
            'messages': {
                'sent': self.messages_sent,
                'received': self.messages_received,
                'failed': self.messages_failed
            },
            'errors': {
                'by_type': dict(self.errors_by_type),
                'by_status': dict(self.errors_by_status)
            },
            'instances': {
                instance_id: {
                    **metrics,
                    'last_request': metrics['last_request'].isoformat() if metrics['last_request'] else None
                }
                for instance_id, metrics in self.instance_metrics.items()
            }
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.request_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        self.rate_limit_hits = 0
        self.webhook_count = 0
        self.webhook_errors = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.messages_failed = 0
        
        self.rate_limit_waits.clear()
        self.response_times.clear()
        self.errors_by_type.clear()
        self.errors_by_status.clear()
        self.instance_metrics.clear()
        self.webhooks_by_type.clear()


class GreenAPIMiddleware(BaseHTTPMiddleware):
    """Middleware for monitoring Green API operations"""
    
    def __init__(self, app, metrics: Optional[GreenAPIMetrics] = None):
        super().__init__(app)
        self.metrics = metrics or GreenAPIMetrics()
        self.green_api_logger = get_green_api_logger("middleware")
    
    async def dispatch(self, request: Request, call_next):
        """Process request and collect metrics"""
        start_time = time.time()
        
        # Check if this is a Green API related request
        is_green_api_request = self._is_green_api_request(request)
        
        if not is_green_api_request:
            return await call_next(request)
        
        # Extract context information
        instance_id = self._extract_instance_id(request)
        correlation_id = self._extract_correlation_id(request)
        
        # Set up logging context
        with LoggingContext(correlation_id=correlation_id, instance_id=instance_id):
            logger_context = self.green_api_logger
            if instance_id:
                logger_context = logger_context.with_instance(instance_id)
            
            # Log request
            logger_context.log_request(
                method=request.method,
                url=str(request.url),
                headers=dict(request.headers)
            )
            
            try:
                # Process request
                response = await call_next(request)
                
                # Calculate response time
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                
                # Log response
                logger_context.log_response(
                    status_code=response.status_code,
                    duration=response_time
                )
                
                # Record metrics
                await self.metrics.record_request(
                    instance_id=instance_id,
                    response_time=response_time,
                    status_code=response.status_code
                )
                
                # Add metrics headers
                response.headers["X-Green-API-Response-Time"] = str(response_time)
                if instance_id:
                    response.headers["X-Green-API-Instance"] = instance_id
                
                return response
                
            except Exception as e:
                # Calculate response time for error case
                response_time = (time.time() - start_time) * 1000
                
                # Log error
                logger_context.log_error(e, "request_processing")
                
                # Record error metrics
                await self.metrics.record_request(
                    instance_id=instance_id,
                    response_time=response_time,
                    error=e
                )
                
                raise
    
    def _is_green_api_request(self, request: Request) -> bool:
        """Check if request is related to Green API"""
        path = request.url.path
        
        # Check for webhook endpoints
        if "/webhooks/green-api" in path:
            return True
        
        # Check for Green API headers
        if "X-Green-API-Instance" in request.headers:
            return True
        
        # Check for Green API query parameters
        if "instance_id" in request.query_params:
            return True
        
        return False
    
    def _extract_instance_id(self, request: Request) -> Optional[str]:
        """Extract Green API instance ID from request"""
        # Check headers
        instance_id = request.headers.get("X-Green-API-Instance")
        if instance_id:
            return instance_id
        
        # Check query parameters
        instance_id = request.query_params.get("instance_id")
        if instance_id:
            return instance_id
        
        # Check path parameters (for webhook endpoints)
        path_parts = request.url.path.split("/")
        if "green-api" in path_parts:
            try:
                green_api_index = path_parts.index("green-api")
                if green_api_index + 1 < len(path_parts):
                    return path_parts[green_api_index + 1]
            except (ValueError, IndexError):
                pass
        
        return None
    
    def _extract_correlation_id(self, request: Request) -> Optional[str]:
        """Extract correlation ID from request"""
        # Check for correlation ID in headers
        correlation_id = request.headers.get("X-Correlation-ID")
        if correlation_id:
            return correlation_id
        
        # Check for request ID
        request_id = request.headers.get("X-Request-ID")
        if request_id:
            return request_id
        
        # Generate new correlation ID
        import uuid
        return str(uuid.uuid4())


# Global metrics instance
green_api_metrics = GreenAPIMetrics()


def get_green_api_metrics() -> GreenAPIMetrics:
    """Get global Green API metrics instance"""
    return green_api_metrics


def reset_green_api_metrics():
    """Reset global Green API metrics"""
    green_api_metrics.reset_metrics()


# Export main components
__all__ = [
    'GreenAPIMiddleware',
    'GreenAPIMetrics',
    'green_api_metrics',
    'get_green_api_metrics',
    'reset_green_api_metrics'
]
