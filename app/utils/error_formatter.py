"""
Error formatting utilities for consistent error responses.

This module provides utilities for formatting errors in a consistent way
across the application, including sanitization and structured formatting.
"""

import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from app.core.config import settings
from app.exceptions.custom_exceptions import BaseCustomException


class ErrorFormatter:
    """Formats errors for consistent API responses and logging"""
    
    @staticmethod
    def format_error_response(
        error: Union[Exception, BaseCustomException],
        request_id: Optional[str] = None,
        include_traceback: bool = False
    ) -> Dict[str, Any]:
        """
        Format error for API response
        
        Args:
            error: The exception to format
            request_id: Optional request ID for tracking
            include_traceback: Whether to include traceback (only in debug mode)
            
        Returns:
            Formatted error dictionary
        """
        if request_id is None:
            request_id = str(uuid4())
            
        # Base error structure
        error_response = {
            "error": True,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "whatsapp-hotel-bot"
        }
        
        if isinstance(error, BaseCustomException):
            # Custom exception with structured data
            error_response.update({
                "error_code": error.error_code,
                "message": error.message,
                "details": error.details,
                "status_code": error.status_code
            })
        else:
            # Standard exception
            error_response.update({
                "error_code": "INTERNAL_ERROR",
                "message": str(error) if settings.DEBUG else "An internal error occurred",
                "details": {
                    "error_type": type(error).__name__
                },
                "status_code": 500
            })
        
        # Add traceback in debug mode
        if include_traceback and settings.DEBUG:
            error_response["traceback"] = traceback.format_exc()
            
        return error_response
    
    @staticmethod
    def format_validation_errors(
        validation_errors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Format validation errors from Pydantic or similar validators
        
        Args:
            validation_errors: List of validation error dictionaries
            
        Returns:
            Formatted validation error response
        """
        formatted_errors = []
        
        for error in validation_errors:
            formatted_error = {
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", "Validation error"),
                "type": error.get("type", "validation_error"),
                "input": error.get("input")
            }
            formatted_errors.append(formatted_error)
        
        return {
            "error": True,
            "error_code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "details": {
                "validation_errors": formatted_errors,
                "error_count": len(formatted_errors)
            },
            "status_code": 422,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def format_log_error(
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        sanitize_sensitive: bool = True
    ) -> Dict[str, Any]:
        """
        Format error for logging purposes
        
        Args:
            error: The exception to format
            context: Additional context information
            sanitize_sensitive: Whether to sanitize sensitive information
            
        Returns:
            Formatted error dictionary for logging
        """
        log_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add custom exception details
        if isinstance(error, BaseCustomException):
            log_data.update({
                "error_code": error.error_code,
                "status_code": error.status_code,
                "details": error.details
            })
        
        # Add context if provided
        if context:
            sanitized_context = (
                ErrorFormatter._sanitize_context(context) 
                if sanitize_sensitive 
                else context
            )
            log_data["context"] = sanitized_context
        
        # Add traceback in debug mode
        if settings.DEBUG:
            log_data["traceback"] = traceback.format_exc()
            
        return log_data
    
    @staticmethod
    def _sanitize_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize sensitive information from context
        
        Args:
            context: Context dictionary to sanitize
            
        Returns:
            Sanitized context dictionary
        """
        sensitive_keys = {
            "password", "token", "api_key", "secret", "authorization",
            "auth", "credential", "key", "private", "confidential"
        }
        
        sanitized = {}
        
        for key, value in context.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive information
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = ErrorFormatter._sanitize_context(value)
            elif isinstance(value, str) and len(value) > 100:
                # Truncate very long strings
                sanitized[key] = value[:100] + "..."
            else:
                sanitized[key] = value
                
        return sanitized
    
    @staticmethod
    def format_external_api_error(
        api_name: str,
        status_code: int,
        response_data: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format external API error for logging
        
        Args:
            api_name: Name of the external API
            status_code: HTTP status code from API
            response_data: Response data from API
            request_data: Request data sent to API
            
        Returns:
            Formatted external API error
        """
        error_data = {
            "error_type": "external_api_error",
            "api_name": api_name,
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if response_data:
            error_data["api_response"] = response_data
            
        if request_data:
            # Sanitize request data to remove sensitive information
            error_data["api_request"] = ErrorFormatter._sanitize_context(request_data)
            
        return error_data
    
    @staticmethod
    def format_database_error(
        operation: str,
        table: Optional[str] = None,
        error: Optional[Exception] = None,
        query_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format database error for logging
        
        Args:
            operation: Database operation that failed
            table: Table name if applicable
            error: The database exception
            query_params: Query parameters (will be sanitized)
            
        Returns:
            Formatted database error
        """
        error_data = {
            "error_type": "database_error",
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if table:
            error_data["table"] = table
            
        if error:
            error_data["error_message"] = str(error)
            error_data["error_class"] = type(error).__name__
            
        if query_params:
            # Sanitize query parameters
            error_data["query_params"] = ErrorFormatter._sanitize_context(query_params)
            
        return error_data
    
    @staticmethod
    def format_task_error(
        task_name: str,
        task_id: str,
        error: Exception,
        args: Optional[tuple] = None,
        kwargs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format Celery task error for logging
        
        Args:
            task_name: Name of the failed task
            task_id: Task ID
            error: The exception that occurred
            args: Task arguments
            kwargs: Task keyword arguments
            
        Returns:
            Formatted task error
        """
        error_data = {
            "error_type": "task_error",
            "task_name": task_name,
            "task_id": task_id,
            "error_message": str(error),
            "error_class": type(error).__name__,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if args:
            # Sanitize task arguments
            error_data["task_args"] = [
                ErrorFormatter._sanitize_value(arg) for arg in args
            ]
            
        if kwargs:
            # Sanitize task keyword arguments
            error_data["task_kwargs"] = ErrorFormatter._sanitize_context(kwargs)
            
        return error_data
    
    @staticmethod
    def _sanitize_value(value: Any) -> Any:
        """
        Sanitize a single value
        
        Args:
            value: Value to sanitize
            
        Returns:
            Sanitized value
        """
        if isinstance(value, dict):
            return ErrorFormatter._sanitize_context(value)
        elif isinstance(value, str) and len(value) > 100:
            return value[:100] + "..."
        else:
            return value


class ErrorSummary:
    """Provides error summary and statistics"""
    
    @staticmethod
    def create_error_summary(
        errors: List[Dict[str, Any]],
        time_window: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create summary of errors for monitoring
        
        Args:
            errors: List of error dictionaries
            time_window: Time window for the summary
            
        Returns:
            Error summary dictionary
        """
        if not errors:
            return {
                "total_errors": 0,
                "error_types": {},
                "time_window": time_window,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        error_types = {}
        status_codes = {}
        
        for error in errors:
            # Count error types
            error_type = error.get("error_type", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
            # Count status codes
            status_code = error.get("status_code", 500)
            status_codes[str(status_code)] = status_codes.get(str(status_code), 0) + 1
        
        return {
            "total_errors": len(errors),
            "error_types": error_types,
            "status_codes": status_codes,
            "time_window": time_window,
            "timestamp": datetime.utcnow().isoformat(),
            "most_common_error": max(error_types.items(), key=lambda x: x[1])[0] if error_types else None
        }
