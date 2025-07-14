"""
Monitoring middleware for WhatsApp Hotel Bot
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from app.core.logging import get_logger, set_correlation_id
from app.core.metrics import track_http_request, track_error
from app.core.config import settings

logger = get_logger("monitoring")

class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for monitoring HTTP requests and responses"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and track metrics"""
        
        # Start timing
        start_time = time.time()
        
        # Set correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        set_correlation_id(correlation_id)
        
        # Extract request info
        method = request.method
        url_path = request.url.path
        user_agent = request.headers.get("User-Agent", "unknown")
        client_ip = self._get_client_ip(request)
        
        # Log request start
        logger.info(
            "Request started",
            method=method,
            path=url_path,
            user_agent=user_agent,
            client_ip=client_ip,
            query_params=str(request.query_params) if request.query_params else None
        )
        
        # Process request
        response = None
        status_code = 500  # Default to error
        error_occurred = False
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
        except Exception as e:
            error_occurred = True
            status_code = 500
            
            # Track error
            track_error(type(e).__name__, "http_request")
            
            logger.error(
                "Request failed with exception",
                method=method,
                path=url_path,
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Create error response
            response = StarletteResponse(
                content={"error": "Internal server error"},
                status_code=500,
                media_type="application/json"
            )
        
        finally:
            # Calculate duration
            duration = time.time() - start_time
            
            # Track metrics
            endpoint = self._normalize_endpoint(url_path)
            track_http_request(method, endpoint, status_code, duration)
            
            # Log request completion
            log_level = "error" if error_occurred or status_code >= 400 else "info"
            getattr(logger, log_level)(
                "Request completed",
                method=method,
                path=url_path,
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
                response_size=getattr(response, 'content_length', None) if response else None
            )
            
            # Add response headers
            if response:
                response.headers["X-Response-Time"] = f"{duration:.3f}s"
                if correlation_id:
                    response.headers["X-Correlation-ID"] = correlation_id
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client host
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics"""
        # Remove query parameters
        if "?" in path:
            path = path.split("?")[0]
        
        # Normalize common patterns
        # Replace UUIDs with placeholder
        import re
        uuid_pattern = r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        path = re.sub(uuid_pattern, '/{uuid}', path, flags=re.IGNORECASE)
        
        # Replace numeric IDs with placeholder
        numeric_pattern = r'/\d+'
        path = re.sub(numeric_pattern, '/{id}', path)
        
        # Limit path length for metrics
        if len(path) > 100:
            path = path[:97] + "..."
        
        return path

class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Middleware for health check monitoring"""
    
    def __init__(self, app, health_check_paths: list = None):
        super().__init__(app)
        self.health_check_paths = health_check_paths or ["/health", "/api/v1/health"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process health check requests with minimal overhead"""
        
        if request.url.path in self.health_check_paths:
            # Minimal logging for health checks to reduce noise
            start_time = time.time()
            
            try:
                response = await call_next(request)
                duration = time.time() - start_time
                
                # Only log if health check is slow or fails
                if duration > 1.0 or response.status_code != 200:
                    logger.warning(
                        "Health check issue",
                        path=request.url.path,
                        status_code=response.status_code,
                        duration_ms=round(duration * 1000, 2)
                    )
                
                return response
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "Health check failed",
                    path=request.url.path,
                    error=str(e),
                    duration_ms=round(duration * 1000, 2)
                )
                raise
        
        else:
            # Not a health check, pass through
            return await call_next(request)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware to add comprehensive security headers"""

    def __init__(self, app):
        super().__init__(app)
        # Import here to avoid circular imports
        from app.core.security_config import security_config
        self.headers_config = security_config.headers

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add comprehensive security headers to response"""
        response = await call_next(request)

        # Add all configured security headers
        response.headers["Content-Security-Policy"] = self.headers_config.content_security_policy
        response.headers["X-Content-Type-Options"] = self.headers_config.x_content_type_options
        response.headers["X-Frame-Options"] = self.headers_config.x_frame_options
        response.headers["X-XSS-Protection"] = self.headers_config.x_xss_protection
        response.headers["Referrer-Policy"] = self.headers_config.referrer_policy
        response.headers["Permissions-Policy"] = self.headers_config.permissions_policy
        response.headers["Cross-Origin-Embedder-Policy"] = self.headers_config.cross_origin_embedder_policy
        response.headers["Cross-Origin-Opener-Policy"] = self.headers_config.cross_origin_opener_policy
        response.headers["Cross-Origin-Resource-Policy"] = self.headers_config.cross_origin_resource_policy

        # Add HSTS header (environment-specific)
        if self.headers_config.strict_transport_security != "max-age=0":
            response.headers["Strict-Transport-Security"] = self.headers_config.strict_transport_security

        # Add custom headers
        for header_name, header_value in self.headers_config.custom_headers.items():
            response.headers[header_name] = header_value

        return response

class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Basic rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}  # In production, use Redis
        self.window_start = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting"""
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/v1/health"]:
            return await call_next(request)
        
        # Initialize or reset window
        if (client_ip not in self.window_start or 
            current_time - self.window_start[client_ip] >= 60):
            self.window_start[client_ip] = current_time
            self.request_counts[client_ip] = 0
        
        # Check rate limit
        self.request_counts[client_ip] += 1
        
        if self.request_counts[client_ip] > self.requests_per_minute:
            logger.warning(
                "Rate limit exceeded",
                client_ip=client_ip,
                requests=self.request_counts[client_ip],
                limit=self.requests_per_minute
            )
            
            return StarletteResponse(
                content={"error": "Rate limit exceeded"},
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"}
            )
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        if request.client:
            return request.client.host
        
        return "unknown"
