"""
Logging middleware for FastAPI with performance optimization.

This middleware provides comprehensive request/response logging with
performance monitoring and error tracking integration.
"""

import time
import uuid
from typing import Callable, Optional
from datetime import datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.core.advanced_logging import log_api_request, log_performance_metric
from app.core.log_performance import get_performance_monitor
from app.utils.async_logger import get_performance_logger
from app.utils.error_tracker import ErrorTracker
from app.database import get_db

logger = get_logger(__name__)
perf_logger = get_performance_logger('api')
performance_monitor = get_performance_monitor()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced logging middleware with performance optimization"""
    
    def __init__(
        self,
        app,
        log_requests: bool = True,
        log_responses: bool = True,
        log_request_body: bool = False,
        log_response_body: bool = False,
        exclude_paths: Optional[list] = None,
        max_body_size: int = 1024
    ):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.exclude_paths = exclude_paths or ['/health', '/metrics', '/docs', '/openapi.json']
        self.max_body_size = max_body_size
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response with logging"""
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Skip logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
            
        # Start timing
        start_time = time.time()
        
        # Extract request information
        request_info = await self._extract_request_info(request)
        
        # Log request if enabled
        if self.log_requests:
            await self._log_request(request, request_info, request_id)
            
        # Process request
        response = None
        error = None
        
        try:
            response = await call_next(request)
            
        except Exception as e:
            error = e
            # Create error response
            response = StarletteResponse(
                content="Internal Server Error",
                status_code=500,
                media_type="text/plain"
            )
            
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Extract response information
        response_info = self._extract_response_info(response, processing_time)
        
        # Log response if enabled
        if self.log_responses:
            await self._log_response(request, response, response_info, request_id, processing_time)
            
        # Track error if occurred
        if error:
            await self._track_error(error, request, request_id)
            
        # Record performance metrics
        performance_monitor.record_log_event(
            processing_time=processing_time,
            error=error is not None
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
        
    async def _extract_request_info(self, request: Request) -> dict:
        """Extract request information for logging"""
        info = {
            'method': request.method,
            'url': str(request.url),
            'path': request.url.path,
            'query_params': dict(request.query_params),
            'headers': dict(request.headers),
            'client_ip': self._get_client_ip(request),
            'user_agent': request.headers.get('user-agent', ''),
            'content_type': request.headers.get('content-type', ''),
            'content_length': request.headers.get('content-length', 0)
        }
        
        # Extract user and hotel info if available
        info['user_id'] = getattr(request.state, 'user_id', None)
        info['hotel_id'] = getattr(request.state, 'hotel_id', None)
        
        # Log request body if enabled and not too large
        if self.log_request_body and request.method in ['POST', 'PUT', 'PATCH']:
            try:
                content_length = int(info['content_length'] or 0)
                if content_length <= self.max_body_size:
                    body = await request.body()
                    if body:
                        info['body'] = body.decode('utf-8', errors='ignore')[:self.max_body_size]
            except Exception:
                info['body'] = '<failed to read body>'
                
        return info
        
    def _extract_response_info(self, response: Response, processing_time: float) -> dict:
        """Extract response information for logging"""
        info = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'processing_time': processing_time,
            'content_length': response.headers.get('content-length', 0)
        }
        
        # Log response body if enabled and not too large
        if self.log_response_body and hasattr(response, 'body'):
            try:
                if hasattr(response.body, 'decode'):
                    body_text = response.body.decode('utf-8', errors='ignore')
                    if len(body_text) <= self.max_body_size:
                        info['body'] = body_text
                    else:
                        info['body'] = body_text[:self.max_body_size] + '...'
            except Exception:
                info['body'] = '<failed to read response body>'
                
        return info
        
    async def _log_request(self, request: Request, request_info: dict, request_id: str) -> None:
        """Log request information"""
        # Use performance logger for high-throughput logging
        perf_logger.info(
            f"Request: {request_info['method']} {request_info['path']}",
            extra={
                'log_type': 'api_request',
                'request_id': request_id,
                'method': request_info['method'],
                'path': request_info['path'],
                'query_params': request_info['query_params'],
                'client_ip': request_info['client_ip'],
                'user_agent': request_info['user_agent'],
                'user_id': request_info.get('user_id'),
                'hotel_id': request_info.get('hotel_id'),
                'content_type': request_info['content_type'],
                'content_length': request_info['content_length']
            }
        )
        
        # Log request body if included
        if 'body' in request_info:
            perf_logger.debug(
                f"Request body: {request_info['method']} {request_info['path']}",
                extra={
                    'log_type': 'api_request_body',
                    'request_id': request_id,
                    'body': request_info['body']
                }
            )
            
    async def _log_response(
        self,
        request: Request,
        response: Response,
        response_info: dict,
        request_id: str,
        processing_time: float
    ) -> None:
        """Log response information"""
        # Determine log level based on status code
        if response_info['status_code'] >= 500:
            log_level = 'error'
        elif response_info['status_code'] >= 400:
            log_level = 'warning'
        else:
            log_level = 'info'
            
        # Use performance logger
        getattr(perf_logger, log_level)(
            f"Response: {request.method} {request.url.path} -> {response_info['status_code']} ({processing_time:.3f}s)",
            extra={
                'log_type': 'api_response',
                'request_id': request_id,
                'method': request.method,
                'path': request.url.path,
                'status_code': response_info['status_code'],
                'processing_time': processing_time,
                'content_length': response_info['content_length'],
                'user_id': getattr(request.state, 'user_id', None),
                'hotel_id': getattr(request.state, 'hotel_id', None)
            }
        )
        
        # Use structured logging for API metrics
        log_api_request(
            method=request.method,
            path=request.url.path,
            status_code=response_info['status_code'],
            response_time=processing_time,
            request_id=request_id,
            user_id=getattr(request.state, 'user_id', None),
            hotel_id=getattr(request.state, 'hotel_id', None),
            client_ip=self._get_client_ip(request)
        )
        
        # Log performance metric
        log_performance_metric(
            operation='api_request',
            duration=processing_time,
            endpoint=request.url.path,
            method=request.method,
            status_code=response_info['status_code']
        )
        
        # Log response body if included
        if 'body' in response_info:
            perf_logger.debug(
                f"Response body: {request.method} {request.url.path}",
                extra={
                    'log_type': 'api_response_body',
                    'request_id': request_id,
                    'body': response_info['body']
                }
            )
            
    async def _track_error(self, error: Exception, request: Request, request_id: str) -> None:
        """Track error in error monitoring system"""
        try:
            db = next(get_db())
            error_tracker = ErrorTracker(db)
            
            error_tracker.track_error(
                error=error,
                request_id=request_id,
                user_id=getattr(request.state, 'user_id', None),
                hotel_id=getattr(request.state, 'hotel_id', None),
                method=request.method,
                path=request.url.path,
                status_code=500,
                context_data={
                    'query_params': dict(request.query_params),
                    'client_ip': self._get_client_ip(request),
                    'user_agent': request.headers.get('user-agent', '')
                }
            )
            
        except Exception as e:
            # Don't let error tracking failures affect the request
            logger.error(f"Failed to track error: {e}")
            
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
            
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
            
        # Fall back to direct client IP
        if hasattr(request.client, 'host'):
            return request.client.host
            
        return 'unknown'


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """Lightweight middleware focused on performance metrics"""
    
    def __init__(self, app, sample_rate: float = 1.0):
        super().__init__(app)
        self.sample_rate = sample_rate
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with minimal performance logging"""
        # Sample requests based on sample rate
        import random
        if random.random() > self.sample_rate:
            return await call_next(request)
            
        start_time = time.time()
        
        try:
            response = await call_next(request)
            processing_time = time.time() - start_time
            
            # Record minimal performance metrics
            performance_monitor.record_log_event(
                processing_time=processing_time,
                error=False
            )
            
            # Log only if slow or error
            if processing_time > 1.0 or response.status_code >= 400:
                log_performance_metric(
                    operation='slow_request',
                    duration=processing_time,
                    endpoint=request.url.path,
                    status_code=response.status_code
                )
                
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            performance_monitor.record_log_event(
                processing_time=processing_time,
                error=True
            )
            
            raise


def create_logging_middleware(
    log_level: str = "INFO",
    enable_request_logging: bool = True,
    enable_response_logging: bool = True,
    enable_body_logging: bool = False,
    performance_only: bool = False
) -> BaseHTTPMiddleware:
    """Factory function to create appropriate logging middleware"""
    
    if performance_only:
        return PerformanceLoggingMiddleware
    else:
        return lambda app: LoggingMiddleware(
            app,
            log_requests=enable_request_logging,
            log_responses=enable_response_logging,
            log_request_body=enable_body_logging and settings.DEBUG,
            log_response_body=enable_body_logging and settings.DEBUG
        )
