"""
Global exception handlers for the FastAPI application.

This module provides centralized exception handling for all types of errors
that can occur in the application, ensuring consistent error responses.
"""

import logging
from typing import Any, Dict

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.exceptions.custom_exceptions import (
    BaseCustomException,
    DatabaseError,
    ExternalAPIError,
    ValidationError as CustomValidationError
)
from app.utils.error_formatter import ErrorFormatter

logger = get_logger(__name__)


async def base_custom_exception_handler(
    request: Request, 
    exc: BaseCustomException
) -> JSONResponse:
    """
    Handle custom application exceptions
    
    Args:
        request: FastAPI request object
        exc: Custom exception instance
        
    Returns:
        JSON response with formatted error
    """
    # Get request ID from headers or generate new one
    request_id = request.headers.get("X-Request-ID")
    
    # Format error response
    error_response = ErrorFormatter.format_error_response(
        error=exc,
        request_id=request_id,
        include_traceback=settings.DEBUG
    )
    
    # Log the error
    logger.error(
        "Custom exception occurred",
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
        status_code=exc.status_code
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )


async def http_exception_handler(
    request: Request, 
    exc: HTTPException
) -> JSONResponse:
    """
    Handle FastAPI HTTP exceptions
    
    Args:
        request: FastAPI request object
        exc: HTTP exception instance
        
    Returns:
        JSON response with formatted error
    """
    request_id = request.headers.get("X-Request-ID")
    
    error_response = {
        "error": True,
        "error_code": "HTTP_ERROR",
        "message": exc.detail if isinstance(exc.detail, str) else "HTTP error occurred",
        "details": exc.detail if isinstance(exc.detail, dict) else {},
        "status_code": exc.status_code,
        "request_id": request_id,
        "timestamp": ErrorFormatter.format_error_response(exc, request_id)["timestamp"],
        "service": "whatsapp-hotel-bot"
    }
    
    logger.warning(
        "HTTP exception occurred",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )


async def starlette_http_exception_handler(
    request: Request, 
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle Starlette HTTP exceptions
    
    Args:
        request: FastAPI request object
        exc: Starlette HTTP exception instance
        
    Returns:
        JSON response with formatted error
    """
    request_id = request.headers.get("X-Request-ID")
    
    error_response = {
        "error": True,
        "error_code": "HTTP_ERROR",
        "message": exc.detail,
        "details": {},
        "status_code": exc.status_code,
        "request_id": request_id,
        "timestamp": ErrorFormatter.format_error_response(exc, request_id)["timestamp"],
        "service": "whatsapp-hotel-bot"
    }
    
    logger.warning(
        "Starlette HTTP exception occurred",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )


async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors
    
    Args:
        request: FastAPI request object
        exc: Request validation error instance
        
    Returns:
        JSON response with formatted validation errors
    """
    request_id = request.headers.get("X-Request-ID")
    
    # Format validation errors
    error_response = ErrorFormatter.format_validation_errors(exc.errors())
    error_response["request_id"] = request_id
    error_response["service"] = "whatsapp-hotel-bot"
    
    logger.warning(
        "Validation error occurred",
        errors=exc.errors(),
        path=request.url.path,
        method=request.method,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response
    )


async def sqlalchemy_exception_handler(
    request: Request, 
    exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handle SQLAlchemy database errors
    
    Args:
        request: FastAPI request object
        exc: SQLAlchemy error instance
        
    Returns:
        JSON response with formatted database error
    """
    request_id = request.headers.get("X-Request-ID")
    
    # Convert to custom database error
    db_error = DatabaseError(
        message="Database operation failed",
        operation="unknown",
        details={"original_error": str(exc)}
    )
    
    error_response = ErrorFormatter.format_error_response(
        error=db_error,
        request_id=request_id,
        include_traceback=settings.DEBUG
    )
    
    logger.error(
        "Database error occurred",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
        exc_info=exc if settings.DEBUG else None
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
    )


async def general_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """
    Handle all other unhandled exceptions
    
    Args:
        request: FastAPI request object
        exc: Exception instance
        
    Returns:
        JSON response with formatted error
    """
    request_id = request.headers.get("X-Request-ID")
    
    error_response = ErrorFormatter.format_error_response(
        error=exc,
        request_id=request_id,
        include_traceback=settings.DEBUG
    )
    
    logger.error(
        "Unhandled exception occurred",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
        exc_info=exc
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response
    )


def register_exception_handlers(app) -> None:
    """
    Register all exception handlers with the FastAPI app
    
    Args:
        app: FastAPI application instance
    """
    # Custom exception handlers
    app.add_exception_handler(BaseCustomException, base_custom_exception_handler)
    
    # Standard exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # Database exception handlers
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    
    # Catch-all exception handler (must be last)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered successfully")


# Exception handler utilities
class ExceptionContext:
    """Context manager for adding additional context to exceptions"""
    
    def __init__(self, **context):
        self.context = context
        self.original_handler = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val and isinstance(exc_val, BaseCustomException):
            # Add context to custom exceptions
            exc_val.details.update(self.context)
        return False  # Don't suppress the exception


def add_error_context(**context):
    """
    Decorator to add context to exceptions raised in a function
    
    Args:
        **context: Context to add to exceptions
        
    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except BaseCustomException as e:
                e.details.update(context)
                raise
            except Exception as e:
                # Convert to custom exception with context
                custom_exc = BaseCustomException(
                    message=str(e),
                    error_code="FUNCTION_ERROR",
                    details=context
                )
                raise custom_exc from e
        return wrapper
    return decorator
