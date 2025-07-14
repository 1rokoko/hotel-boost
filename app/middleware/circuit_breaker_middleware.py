"""
Circuit breaker middleware for FastAPI
"""

import time
from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.circuit_breaker import (
    get_circuit_breaker, 
    CircuitBreakerOpenException,
    CircuitBreakerTimeoutException,
    CircuitState
)
from app.core.circuit_breaker_config import (
    get_circuit_breaker_config,
    CircuitBreakerNames
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply circuit breaker protection to API endpoints
    """
    
    def __init__(self, app, protected_paths: Dict[str, str] = None):
        """
        Initialize circuit breaker middleware
        
        Args:
            app: FastAPI application
            protected_paths: Dict mapping path patterns to circuit breaker names
        """
        super().__init__(app)
        
        # Default protected paths
        self.protected_paths = protected_paths or {
            "/api/v1/webhooks/": CircuitBreakerNames.WEBHOOK_PROCESSING,
            "/api/v1/messages/": CircuitBreakerNames.MESSAGE_SENDING,
            "/api/v1/sentiment/": CircuitBreakerNames.SENTIMENT_ANALYSIS,
            "/api/v1/triggers/": CircuitBreakerNames.TRIGGER_EXECUTION,
        }
        
        # Initialize circuit breakers for protected paths
        self._initialize_circuit_breakers()
    
    def _initialize_circuit_breakers(self) -> None:
        """Initialize circuit breakers for all protected paths"""
        for path, cb_name in self.protected_paths.items():
            config = get_circuit_breaker_config(cb_name)
            get_circuit_breaker(cb_name, config)
            logger.info("Initialized circuit breaker for path", 
                       path=path, 
                       circuit_breaker=cb_name)
    
    def _get_circuit_breaker_name(self, path: str) -> str:
        """
        Get circuit breaker name for a given path
        
        Args:
            path: Request path
            
        Returns:
            Circuit breaker name or None if not protected
        """
        for protected_path, cb_name in self.protected_paths.items():
            if path.startswith(protected_path):
                return cb_name
        return None
    
    def _create_circuit_breaker_response(self, cb_name: str, exception: Exception) -> JSONResponse:
        """
        Create appropriate response for circuit breaker exceptions
        
        Args:
            cb_name: Circuit breaker name
            exception: The circuit breaker exception
            
        Returns:
            JSONResponse with appropriate error message
        """
        if isinstance(exception, CircuitBreakerOpenException):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service Temporarily Unavailable",
                    "message": f"Service is currently experiencing issues. Please try again later.",
                    "circuit_breaker": cb_name,
                    "retry_after": 60,  # Suggest retry after 60 seconds
                    "timestamp": time.time()
                },
                headers={"Retry-After": "60"}
            )
        
        elif isinstance(exception, CircuitBreakerTimeoutException):
            return JSONResponse(
                status_code=504,
                content={
                    "error": "Gateway Timeout",
                    "message": "Request timed out. Please try again.",
                    "circuit_breaker": cb_name,
                    "timestamp": time.time()
                }
            )
        
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred.",
                    "circuit_breaker": cb_name,
                    "timestamp": time.time()
                }
            )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with circuit breaker protection
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
        path = request.url.path
        cb_name = self._get_circuit_breaker_name(path)
        
        # If path is not protected, proceed normally
        if not cb_name:
            return await call_next(request)
        
        # Get circuit breaker
        circuit_breaker = get_circuit_breaker(cb_name)
        
        # Add circuit breaker info to request state
        request.state.circuit_breaker_name = cb_name
        request.state.circuit_breaker = circuit_breaker
        
        try:
            # Execute request with circuit breaker protection
            response = await circuit_breaker.call(call_next, request)
            
            # Add circuit breaker headers to response
            if hasattr(response, 'headers'):
                response.headers["X-Circuit-Breaker"] = cb_name
                response.headers["X-Circuit-Breaker-State"] = circuit_breaker.state.value
            
            return response
            
        except (CircuitBreakerOpenException, CircuitBreakerTimeoutException) as e:
            logger.warning("Circuit breaker blocked request", 
                         path=path,
                         circuit_breaker=cb_name,
                         exception=type(e).__name__)
            return self._create_circuit_breaker_response(cb_name, e)
        
        except Exception as e:
            # Log unexpected errors but don't expose them
            logger.error("Unexpected error in circuit breaker middleware", 
                        path=path,
                        circuit_breaker=cb_name,
                        error=str(e))
            return self._create_circuit_breaker_response(cb_name, e)


class CircuitBreakerHealthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add circuit breaker health information to responses
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add circuit breaker health headers to responses
        """
        response = await call_next(request)
        
        # Add circuit breaker health headers for monitoring
        if request.url.path.startswith("/health") or request.url.path.startswith("/api/v1/health"):
            from app.utils.circuit_breaker import get_all_circuit_breakers
            
            circuit_breakers = get_all_circuit_breakers()
            
            # Count circuit breakers by state
            states = {"closed": 0, "open": 0, "half_open": 0}
            for cb in circuit_breakers.values():
                states[cb.state.value] += 1
            
            # Add headers
            if hasattr(response, 'headers'):
                response.headers["X-Circuit-Breakers-Total"] = str(len(circuit_breakers))
                response.headers["X-Circuit-Breakers-Closed"] = str(states["closed"])
                response.headers["X-Circuit-Breakers-Open"] = str(states["open"])
                response.headers["X-Circuit-Breakers-Half-Open"] = str(states["half_open"])
        
        return response


def add_circuit_breaker_middleware(app, protected_paths: Dict[str, str] = None) -> None:
    """
    Add circuit breaker middleware to FastAPI app
    
    Args:
        app: FastAPI application
        protected_paths: Dict mapping path patterns to circuit breaker names
    """
    app.add_middleware(CircuitBreakerMiddleware, protected_paths=protected_paths)
    app.add_middleware(CircuitBreakerHealthMiddleware)
    
    logger.info("Circuit breaker middleware added to application",
               protected_paths=list(protected_paths.keys()) if protected_paths else "default")


# Decorator for manual circuit breaker protection
def circuit_breaker_protected(circuit_breaker_name: str):
    """
    Decorator to protect functions with circuit breaker
    
    Args:
        circuit_breaker_name: Name of the circuit breaker to use
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            config = get_circuit_breaker_config(circuit_breaker_name)
            circuit_breaker = get_circuit_breaker(circuit_breaker_name, config)
            return await circuit_breaker.call(func, *args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            config = get_circuit_breaker_config(circuit_breaker_name)
            circuit_breaker = get_circuit_breaker(circuit_breaker_name, config)
            return circuit_breaker.call(func, *args, **kwargs)
        
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
