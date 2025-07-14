"""
Logger utilities for WhatsApp Hotel Bot
"""

import functools
import time
from typing import Any, Callable, Dict, Optional, TypeVar, Union

import structlog
from fastapi import Request, Response

from app.core.logging import get_logger, set_correlation_id, PerformanceLogger

F = TypeVar('F', bound=Callable[..., Any])

def log_function_call(
    logger_name: Optional[str] = None,
    log_args: bool = True,
    log_result: bool = False,
    log_performance: bool = True
) -> Callable[[F], F]:
    """Decorator to log function calls"""
    
    def decorator(func: F) -> F:
        logger = get_logger(logger_name or func.__module__)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            # Log function entry
            log_data = {"function": func_name, "action": "entry"}
            if log_args:
                log_data.update({
                    "args": str(args) if args else None,
                    "kwargs": kwargs if kwargs else None
                })
            
            logger.debug("Function called", **log_data)
            
            # Execute function with performance tracking
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                
                # Log successful completion
                log_data = {
                    "function": func_name,
                    "action": "success",
                    "duration_ms": round((time.time() - start_time) * 1000, 2)
                }
                
                if log_result and result is not None:
                    log_data["result"] = str(result)[:200]  # Truncate long results
                
                if log_performance:
                    logger.info("Function completed", **log_data)
                else:
                    logger.debug("Function completed", **log_data)
                
                return result
                
            except Exception as e:
                # Log error
                logger.error(
                    "Function failed",
                    function=func_name,
                    action="error",
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round((time.time() - start_time) * 1000, 2)
                )
                raise
        
        return wrapper
    return decorator

def log_api_call(
    log_request_body: bool = False,
    log_response_body: bool = False
) -> Callable[[F], F]:
    """Decorator to log API endpoint calls"""
    
    def decorator(func: F) -> F:
        logger = get_logger("api")
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args (assuming it's the first parameter)
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request:
                # Set correlation ID from header or generate new one
                correlation_id = request.headers.get("X-Correlation-ID")
                set_correlation_id(correlation_id)
                
                # Log request
                log_data = {
                    "method": request.method,
                    "url": str(request.url),
                    "endpoint": func.__name__,
                    "user_agent": request.headers.get("User-Agent"),
                    "client_ip": request.client.host if request.client else None
                }
                
                if log_request_body and request.method in ["POST", "PUT", "PATCH"]:
                    try:
                        body = await request.body()
                        log_data["request_body"] = body.decode()[:500]  # Truncate
                    except:
                        log_data["request_body"] = "Could not read body"
                
                logger.info("API request received", **log_data)
            
            # Execute function
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                
                # Log response
                duration_ms = round((time.time() - start_time) * 1000, 2)
                log_data = {
                    "endpoint": func.__name__,
                    "duration_ms": duration_ms,
                    "status": "success"
                }
                
                if isinstance(result, Response):
                    log_data["status_code"] = result.status_code
                
                if log_response_body and result:
                    log_data["response_body"] = str(result)[:500]  # Truncate
                
                logger.info("API request completed", **log_data)
                return result
                
            except Exception as e:
                # Log error
                duration_ms = round((time.time() - start_time) * 1000, 2)
                logger.error(
                    "API request failed",
                    endpoint=func.__name__,
                    duration_ms=duration_ms,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
        
        return wrapper
    return decorator

class DatabaseLogger:
    """Logger for database operations"""
    
    def __init__(self):
        self.logger = get_logger("database")
    
    def log_query(
        self,
        operation: str,
        table: str,
        query: str,
        params: Optional[Dict] = None,
        duration_ms: Optional[float] = None,
        rows_affected: Optional[int] = None
    ):
        """Log database query"""
        log_data = {
            "operation": operation,
            "table": table,
            "query": query[:200],  # Truncate long queries
        }
        
        if params:
            log_data["params"] = str(params)[:100]  # Truncate long params
        
        if duration_ms is not None:
            log_data["duration_ms"] = round(duration_ms, 2)
        
        if rows_affected is not None:
            log_data["rows_affected"] = rows_affected
        
        self.logger.debug("Database query executed", **log_data)
    
    def log_transaction(self, action: str, transaction_id: Optional[str] = None):
        """Log database transaction"""
        log_data = {"action": action}
        if transaction_id:
            log_data["transaction_id"] = transaction_id
        
        self.logger.debug("Database transaction", **log_data)
    
    def log_connection_pool(self, active: int, total: int, checked_out: int):
        """Log connection pool status"""
        self.logger.debug(
            "Connection pool status",
            active_connections=active,
            total_connections=total,
            checked_out=checked_out
        )

class ExternalAPILogger:
    """Logger for external API calls"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = get_logger(f"external_api.{service_name}")
    
    def log_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None,
        body: Optional[str] = None
    ):
        """Log outgoing API request"""
        log_data = {
            "service": self.service_name,
            "method": method,
            "url": url,
            "action": "request"
        }
        
        if headers:
            # Remove sensitive headers
            safe_headers = {k: v for k, v in headers.items() 
                          if k.lower() not in ['authorization', 'x-api-key']}
            log_data["headers"] = safe_headers
        
        if body:
            log_data["body"] = body[:200]  # Truncate
        
        self.logger.info("External API request", **log_data)
    
    def log_response(
        self,
        status_code: int,
        response_time_ms: float,
        response_body: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log API response"""
        log_data = {
            "service": self.service_name,
            "status_code": status_code,
            "response_time_ms": round(response_time_ms, 2),
            "action": "response"
        }
        
        if response_body:
            log_data["response_body"] = response_body[:200]  # Truncate
        
        if error:
            log_data["error"] = error
            self.logger.error("External API error", **log_data)
        else:
            self.logger.info("External API response", **log_data)

# Convenience instances
db_logger = DatabaseLogger()
green_api_logger = ExternalAPILogger("green_api")
deepseek_logger = ExternalAPILogger("deepseek")
