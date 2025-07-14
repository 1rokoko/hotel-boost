"""
Database middleware for request tracking and metrics
"""

import time
import uuid
from typing import Callable, Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

from app.core.logging import get_logger
from app.core.database_logging import db_logger
from app.utils.db_monitor import health_checker
from app.database import get_connection_pool_stats

logger = get_logger(__name__)

class DatabaseMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track database operations per request
    
    This middleware tracks database usage, query counts, and performance
    metrics for each HTTP request.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        track_queries: bool = True,
        track_connections: bool = True,
        log_slow_requests: bool = True,
        slow_request_threshold: float = 5000.0  # milliseconds
    ):
        """
        Initialize database metrics middleware
        
        Args:
            app: ASGI application
            track_queries: Whether to track query metrics per request
            track_connections: Whether to track connection usage per request
            log_slow_requests: Whether to log slow database requests
            slow_request_threshold: Threshold in milliseconds for slow requests
        """
        super().__init__(app)
        self.track_queries = track_queries
        self.track_connections = track_connections
        self.log_slow_requests = log_slow_requests
        self.slow_request_threshold = slow_request_threshold
        self.request_metrics = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and track database metrics
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        # Generate correlation ID for request tracking
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        # Initialize request metrics
        request_start_time = time.time()
        initial_query_count = 0  # Simplified without performance_monitor
        initial_pool_stats = await get_connection_pool_stats() if self.track_connections else None
        
        # Store initial metrics
        self.request_metrics[correlation_id] = {
            "start_time": request_start_time,
            "initial_query_count": initial_query_count,
            "initial_pool_stats": initial_pool_stats,
            "path": request.url.path,
            "method": request.method,
            "tenant_id": getattr(request.state, 'tenant_id', None)
        }
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate metrics after request
            await self._log_request_metrics(correlation_id, response.status_code)
            
            return response
            
        except Exception as e:
            # Log metrics for failed requests
            await self._log_request_metrics(correlation_id, 500, str(e))
            raise
            
        finally:
            # Clean up request metrics
            self.request_metrics.pop(correlation_id, None)
    
    async def _log_request_metrics(
        self,
        correlation_id: str,
        status_code: int,
        error: Optional[str] = None
    ) -> None:
        """
        Log request database metrics
        
        Args:
            correlation_id: Request correlation ID
            status_code: HTTP status code
            error: Error message if request failed
        """
        try:
            request_metrics = self.request_metrics.get(correlation_id)
            if not request_metrics:
                return
            
            # Calculate request duration
            request_duration = (time.time() - request_metrics["start_time"]) * 1000
            
            # Calculate query metrics
            final_query_count = 0  # Simplified without performance_monitor
            queries_executed = final_query_count - request_metrics["initial_query_count"]
            
            # Get final connection pool stats
            final_pool_stats = await get_connection_pool_stats() if self.track_connections else None
            
            # Build log data
            log_data = {
                "event": "request_database_metrics",
                "correlation_id": correlation_id,
                "path": request_metrics["path"],
                "method": request_metrics["method"],
                "status_code": status_code,
                "duration_ms": round(request_duration, 2),
                "queries_executed": queries_executed,
                "tenant_id": str(request_metrics["tenant_id"]) if request_metrics["tenant_id"] else None,
                "timestamp": time.time()
            }
            
            if error:
                log_data["error"] = error
            
            if self.track_connections and final_pool_stats:
                log_data["pool_stats"] = final_pool_stats
                
                # Calculate connection usage change
                if request_metrics["initial_pool_stats"]:
                    initial_checked_out = request_metrics["initial_pool_stats"].get("checked_out", 0)
                    final_checked_out = final_pool_stats.get("checked_out", 0)
                    log_data["connection_change"] = final_checked_out - initial_checked_out
            
            # Determine log level
            log_level = "info"
            if error:
                log_level = "error"
            elif self.log_slow_requests and request_duration > self.slow_request_threshold:
                log_level = "warning"
                log_data["event"] = "slow_database_request"
            elif queries_executed == 0:
                log_level = "debug"  # No database queries
            
            # Log the metrics
            getattr(logger, log_level)("Request database metrics", extra=log_data)
            
        except Exception as e:
            logger.error(f"Failed to log request metrics: {str(e)}")

class DatabaseHealthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor database health during requests
    
    This middleware can optionally perform health checks and
    reject requests if the database is unhealthy.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        health_check_interval: int = 60,  # seconds
        reject_on_unhealthy: bool = False,
        health_check_paths: Optional[list] = None
    ):
        """
        Initialize database health middleware
        
        Args:
            app: ASGI application
            health_check_interval: Interval between health checks in seconds
            reject_on_unhealthy: Whether to reject requests when database is unhealthy
            health_check_paths: Paths that trigger health checks
        """
        super().__init__(app)
        self.health_check_interval = health_check_interval
        self.reject_on_unhealthy = reject_on_unhealthy
        self.health_check_paths = health_check_paths or ["/health", "/health/db"]
        self.last_health_check = 0
        self.last_health_status = "unknown"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with database health monitoring
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        # Check if this is a health check request
        if request.url.path in self.health_check_paths:
            return await self._handle_health_check_request(request, call_next)
        
        # Periodic health check
        current_time = time.time()
        if current_time - self.last_health_check > self.health_check_interval:
            await self._perform_background_health_check()
            self.last_health_check = current_time
        
        # Reject request if database is unhealthy and rejection is enabled
        if self.reject_on_unhealthy and self.last_health_status == "unhealthy":
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service Unavailable",
                    "message": "Database is currently unhealthy",
                    "status": self.last_health_status
                }
            )
        
        # Process request normally
        return await call_next(request)
    
    async def _handle_health_check_request(self, request: Request, call_next: Callable) -> Response:
        """
        Handle health check requests
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: Health check response
        """
        try:
            # Force a health check
            await self._perform_background_health_check()
            
            # Let the request proceed to get full health data
            response = await call_next(request)
            
            # Add health status header
            response.headers["X-Database-Health"] = self.last_health_status
            
            return response
            
        except Exception as e:
            logger.error(f"Health check request failed: {str(e)}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Health Check Failed",
                    "message": str(e)
                }
            )
    
    async def _perform_background_health_check(self) -> None:
        """Perform background health check"""
        try:
            from app.database import get_db_session
            
            async with get_db_session() as session:
                health_data = await health_checker.check_database_health(session)
                self.last_health_status = health_data.get("status", "unknown")
                
                # Log health status changes
                if hasattr(self, '_previous_status') and self._previous_status != self.last_health_status:
                    logger.info(
                        f"Database health status changed: {self._previous_status} -> {self.last_health_status}",
                        extra={
                            "event": "database_health_change",
                            "previous_status": self._previous_status,
                            "current_status": self.last_health_status,
                            "timestamp": time.time()
                        }
                    )
                
                self._previous_status = self.last_health_status
                
        except Exception as e:
            logger.error(f"Background health check failed: {str(e)}")
            self.last_health_status = "unhealthy"

class DatabaseConnectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor database connection usage
    
    This middleware tracks connection pool usage and can
    implement connection limiting or throttling.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        max_concurrent_requests: Optional[int] = None,
        connection_warning_threshold: float = 0.8
    ):
        """
        Initialize database connection middleware
        
        Args:
            app: ASGI application
            max_concurrent_requests: Maximum concurrent requests (optional)
            connection_warning_threshold: Threshold for connection pool warnings
        """
        super().__init__(app)
        self.max_concurrent_requests = max_concurrent_requests
        self.connection_warning_threshold = connection_warning_threshold
        self.active_requests = 0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with connection monitoring
        
        Args:
            request: HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response: HTTP response
        """
        # Check concurrent request limit
        if self.max_concurrent_requests and self.active_requests >= self.max_concurrent_requests:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": "Maximum concurrent requests exceeded",
                    "active_requests": self.active_requests,
                    "max_requests": self.max_concurrent_requests
                }
            )
        
        self.active_requests += 1
        
        try:
            # Check connection pool status
            pool_stats = await get_connection_pool_stats()
            if pool_stats:
                await self._check_connection_warnings(pool_stats)
            
            # Process request
            response = await call_next(request)
            
            # Add connection info to response headers
            if pool_stats:
                response.headers["X-DB-Pool-Utilization"] = str(
                    round((pool_stats.get("checked_out", 0) / max(pool_stats.get("pool_size", 1), 1)) * 100, 1)
                )
            
            return response
            
        finally:
            self.active_requests -= 1
    
    async def _check_connection_warnings(self, pool_stats: Dict[str, Any]) -> None:
        """
        Check for connection pool warnings
        
        Args:
            pool_stats: Connection pool statistics
        """
        try:
            total_connections = pool_stats.get("pool_size", 0) + pool_stats.get("overflow", 0)
            if total_connections > 0:
                utilization = pool_stats.get("checked_out", 0) / total_connections
                
                if utilization > self.connection_warning_threshold:
                    logger.warning(
                        f"High database connection utilization: {utilization:.1%}",
                        extra={
                            "event": "high_connection_utilization",
                            "utilization": utilization,
                            "pool_stats": pool_stats,
                            "active_requests": self.active_requests,
                            "timestamp": time.time()
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to check connection warnings: {str(e)}")

# Convenience function to add all database middlewares
def add_database_middlewares(app: ASGIApp, **kwargs) -> ASGIApp:
    """
    Add all database-related middlewares to the application
    
    Args:
        app: ASGI application
        **kwargs: Configuration for middlewares
        
    Returns:
        ASGIApp: Application with database middlewares added
    """
    # Add middlewares in reverse order (they are applied in LIFO order)
    app.add_middleware(DatabaseConnectionMiddleware, **kwargs.get('connection', {}))
    app.add_middleware(DatabaseHealthMiddleware, **kwargs.get('health', {}))
    app.add_middleware(DatabaseMetricsMiddleware, **kwargs.get('metrics', {}))
    
    return app
