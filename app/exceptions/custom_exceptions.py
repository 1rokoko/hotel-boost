"""
Custom exceptions for the WhatsApp Hotel Bot application.

This module defines all custom exceptions used throughout the application,
providing structured error handling with proper error codes and messages.
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException


class BaseCustomException(Exception):
    """Base class for all custom exceptions"""
    
    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(BaseCustomException):
    """Raised when data validation fails"""
    
    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = str(value)
            
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=error_details,
            status_code=400
        )


class AuthenticationError(BaseCustomException):
    """Raised when authentication fails"""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            details=details,
            status_code=401
        )


class AuthorizationError(BaseCustomException):
    """Raised when authorization fails"""
    
    def __init__(
        self,
        message: str = "Access denied",
        required_permission: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if required_permission:
            error_details["required_permission"] = required_permission
            
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            details=error_details,
            status_code=403
        )


class ResourceNotFoundError(BaseCustomException):
    """Raised when a requested resource is not found"""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if not message:
            message = f"{resource_type} not found"
            if resource_id:
                message += f" (ID: {resource_id})"
                
        error_details = details or {}
        error_details["resource_type"] = resource_type
        if resource_id:
            error_details["resource_id"] = resource_id
            
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            details=error_details,
            status_code=404
        )


class ConflictError(BaseCustomException):
    """Raised when a resource conflict occurs"""
    
    def __init__(
        self,
        message: str = "Resource conflict",
        resource_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
            
        super().__init__(
            message=message,
            error_code="CONFLICT_ERROR",
            details=error_details,
            status_code=409
        )


class RateLimitError(BaseCustomException):
    """Raised when rate limit is exceeded"""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if limit:
            error_details["limit"] = limit
        if window:
            error_details["window_seconds"] = window
            
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            details=error_details,
            status_code=429
        )


class ExternalAPIError(BaseCustomException):
    """Raised when external API calls fail"""
    
    def __init__(
        self,
        api_name: str,
        message: str = "External API error",
        api_error_code: Optional[str] = None,
        api_response: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details["api_name"] = api_name
        if api_error_code:
            error_details["api_error_code"] = api_error_code
        if api_response:
            error_details["api_response"] = api_response
            
        super().__init__(
            message=f"{api_name}: {message}",
            error_code="EXTERNAL_API_ERROR",
            details=error_details,
            status_code=502
        )


class GreenAPIError(ExternalAPIError):
    """Raised when Green API calls fail"""
    
    def __init__(
        self,
        message: str = "Green API error",
        api_error_code: Optional[str] = None,
        api_response: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            api_name="Green API",
            message=message,
            api_error_code=api_error_code,
            api_response=api_response,
            details=details
        )


class DeepSeekAPIError(ExternalAPIError):
    """Raised when DeepSeek API calls fail"""
    
    def __init__(
        self,
        message: str = "DeepSeek API error",
        api_error_code: Optional[str] = None,
        api_response: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            api_name="DeepSeek API",
            message=message,
            api_error_code=api_error_code,
            api_response=api_response,
            details=details
        )


class DatabaseError(BaseCustomException):
    """Raised when database operations fail"""
    
    def __init__(
        self,
        message: str = "Database error",
        operation: Optional[str] = None,
        table: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if table:
            error_details["table"] = table
            
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details=error_details,
            status_code=500
        )


class TenantError(BaseCustomException):
    """Raised when tenant-related operations fail"""
    
    def __init__(
        self,
        message: str = "Tenant error",
        hotel_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if hotel_id:
            error_details["hotel_id"] = hotel_id
            
        super().__init__(
            message=message,
            error_code="TENANT_ERROR",
            details=error_details,
            status_code=400
        )


class ConfigurationError(BaseCustomException):
    """Raised when configuration is invalid or missing"""
    
    def __init__(
        self,
        message: str = "Configuration error",
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key
            
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=error_details,
            status_code=500
        )


class BusinessLogicError(BaseCustomException):
    """Raised when business logic validation fails"""
    
    def __init__(
        self,
        message: str = "Business logic error",
        rule: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if rule:
            error_details["rule"] = rule
            
        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            details=error_details,
            status_code=422
        )


class TaskExecutionError(BaseCustomException):
    """Raised when background task execution fails"""
    
    def __init__(
        self,
        task_name: str,
        message: str = "Task execution failed",
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details["task_name"] = task_name
        if task_id:
            error_details["task_id"] = task_id
            
        super().__init__(
            message=f"Task '{task_name}': {message}",
            error_code="TASK_EXECUTION_ERROR",
            details=error_details,
            status_code=500
        )


class WebhookError(BaseCustomException):
    """Raised when webhook processing fails"""
    
    def __init__(
        self,
        message: str = "Webhook processing error",
        webhook_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if webhook_type:
            error_details["webhook_type"] = webhook_type
            
        super().__init__(
            message=message,
            error_code="WEBHOOK_ERROR",
            details=error_details,
            status_code=400
        )


def to_http_exception(exc: BaseCustomException) -> HTTPException:
    """Convert custom exception to FastAPI HTTPException"""
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )
