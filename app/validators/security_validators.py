"""
Enhanced Pydantic security validators for input validation and sanitization

This module provides custom Pydantic validators that integrate with the input
sanitization framework to provide comprehensive security validation.
"""

import re
import mimetypes
from typing import Any, Dict, List, Optional, Set, Union, Type
from pydantic import field_validator, Field, BaseModel
# str_validator is deprecated in Pydantic v2, using built-in str instead
import structlog

from app.utils.input_sanitizer import (
    InputSanitizer,
    InputSanitizationError,
    SAFE_FILE_EXTENSIONS,
    DANGEROUS_FILE_EXTENSIONS,
    MAX_FILE_SIZE
)

logger = structlog.get_logger(__name__)

# Global sanitizer instance for validators
security_sanitizer = InputSanitizer(strict_mode=True)


class SecurityValidationError(ValueError):
    """Custom validation error for security issues"""
    pass


def validate_safe_text(
    v: str,
    max_length: Optional[int] = None,
    allow_html: bool = False,
    allowed_tags: Optional[Set[str]] = None
) -> str:
    """
    Validate and sanitize text input for security
    
    Args:
        v: Input value
        max_length: Maximum allowed length
        allow_html: Whether to allow HTML content
        allowed_tags: Set of allowed HTML tags
        
    Returns:
        str: Sanitized text
        
    Raises:
        SecurityValidationError: If validation fails
    """
    if not isinstance(v, str):
        v = str(v)
    
    if not v:
        return v
    
    try:
        if allow_html:
            sanitized = security_sanitizer.sanitize_html(v, allowed_tags)
        else:
            sanitized = security_sanitizer.sanitize_text(v, max_length)
        
        # Check if sanitization removed too much content
        if len(sanitized) < len(v) * 0.5:  # If more than 50% was removed
            logger.warning(
                "Significant content removed during sanitization",
                original_length=len(v),
                sanitized_length=len(sanitized)
            )
        
        return sanitized
        
    except InputSanitizationError as e:
        raise SecurityValidationError(f"Text validation failed: {str(e)}")


def validate_safe_phone(v: str) -> str:
    """
    Validate and sanitize phone number
    
    Args:
        v: Phone number input
        
    Returns:
        str: Sanitized phone number
        
    Raises:
        SecurityValidationError: If validation fails
    """
    if not isinstance(v, str):
        v = str(v)
    
    if not v:
        return v
    
    try:
        sanitized = security_sanitizer.sanitize_phone_number(v)
        if not sanitized:
            raise SecurityValidationError("Invalid phone number format")
        return sanitized
        
    except InputSanitizationError as e:
        raise SecurityValidationError(f"Phone validation failed: {str(e)}")


def validate_safe_email(v: str) -> str:
    """
    Validate and sanitize email address
    
    Args:
        v: Email input
        
    Returns:
        str: Sanitized email
        
    Raises:
        SecurityValidationError: If validation fails
    """
    if not isinstance(v, str):
        v = str(v)
    
    if not v:
        return v
    
    try:
        sanitized = security_sanitizer.sanitize_email(v)
        if not sanitized:
            raise SecurityValidationError("Invalid email format")
        return sanitized
        
    except InputSanitizationError as e:
        raise SecurityValidationError(f"Email validation failed: {str(e)}")


def validate_safe_url(v: str) -> str:
    """
    Validate and sanitize URL
    
    Args:
        v: URL input
        
    Returns:
        str: Sanitized URL
        
    Raises:
        SecurityValidationError: If validation fails
    """
    if not isinstance(v, str):
        v = str(v)
    
    if not v:
        return v
    
    try:
        sanitized = security_sanitizer.sanitize_url(v)
        if not sanitized:
            raise SecurityValidationError("Invalid or dangerous URL")
        return sanitized
        
    except InputSanitizationError as e:
        raise SecurityValidationError(f"URL validation failed: {str(e)}")


def validate_safe_json(v: Union[str, Dict, List]) -> Union[str, Dict, List]:
    """
    Validate and sanitize JSON input
    
    Args:
        v: JSON input
        
    Returns:
        Sanitized JSON data
        
    Raises:
        SecurityValidationError: If validation fails
    """
    try:
        sanitized = security_sanitizer.sanitize_json_input(v)
        return sanitized
        
    except InputSanitizationError as e:
        raise SecurityValidationError(f"JSON validation failed: {str(e)}")


def validate_file_upload(
    filename: str,
    content_type: Optional[str] = None,
    file_size: Optional[int] = None
) -> str:
    """
    Validate file upload for security
    
    Args:
        filename: Name of uploaded file
        content_type: MIME type of file
        file_size: Size of file in bytes
        
    Returns:
        str: Validated filename
        
    Raises:
        SecurityValidationError: If validation fails
    """
    if not filename:
        raise SecurityValidationError("Filename is required")
    
    # Sanitize filename
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Check file extension
    file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
    
    if file_ext in DANGEROUS_FILE_EXTENSIONS:
        raise SecurityValidationError(f"Dangerous file extension: {file_ext}")
    
    if file_ext not in SAFE_FILE_EXTENSIONS:
        logger.warning("Unknown file extension", extension=file_ext, filename=filename)
        # In strict mode, reject unknown extensions
        # raise SecurityValidationError(f"Unknown file extension: {file_ext}")
    
    # Validate content type
    if content_type:
        expected_type, _ = mimetypes.guess_type(filename)
        if expected_type and not content_type.startswith(expected_type.split('/')[0]):
            logger.warning(
                "Content type mismatch",
                filename=filename,
                expected=expected_type,
                actual=content_type
            )
    
    # Check file size
    if file_size and file_size > MAX_FILE_SIZE:
        raise SecurityValidationError(
            f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})"
        )
    
    return filename


def validate_content_type(v: str, allowed_types: Optional[Set[str]] = None) -> str:
    """
    Validate HTTP content type
    
    Args:
        v: Content type string
        allowed_types: Set of allowed content types
        
    Returns:
        str: Validated content type
        
    Raises:
        SecurityValidationError: If validation fails
    """
    if not isinstance(v, str):
        v = str(v)
    
    if not v:
        return v
    
    # Extract main content type (remove parameters)
    main_type = v.split(';')[0].strip().lower()
    
    # Default allowed types
    if allowed_types is None:
        allowed_types = {
            'application/json',
            'application/x-www-form-urlencoded',
            'text/plain',
            'text/html',
            'multipart/form-data'
        }
    
    if main_type not in allowed_types:
        raise SecurityValidationError(f"Invalid content type: {main_type}")
    
    return v


def validate_user_agent(v: str) -> str:
    """
    Validate User-Agent header
    
    Args:
        v: User-Agent string
        
    Returns:
        str: Validated User-Agent
        
    Raises:
        SecurityValidationError: If validation fails
    """
    if not isinstance(v, str):
        v = str(v)
    
    if not v:
        return v
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'<script',
        r'javascript:',
        r'vbscript:',
        r'data:',
        r'expression\(',
        r'@import'
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, v, re.IGNORECASE):
            raise SecurityValidationError("Suspicious User-Agent detected")
    
    # Limit length
    if len(v) > 500:
        v = v[:500]
        logger.warning("User-Agent truncated due to length")
    
    return v


# Custom Pydantic field types with security validation
class SafeStr(str):
    """String field with automatic sanitization"""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, validation_info=None):
        field = validation_info.field_info if validation_info else None
        max_length = getattr(field, 'max_length', None) if field else None
        return validate_safe_text(v, max_length=max_length)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        """Pydantic v2 compatibility"""
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema()
        )


class SafeHtml(str):
    """HTML string field with sanitization"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v, field=None):
        allowed_tags = getattr(field, 'allowed_tags', None) if field else None
        return validate_safe_text(v, allow_html=True, allowed_tags=allowed_tags)


class SafePhone(str):
    """Phone number field with validation"""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, validation_info=None):
        return validate_safe_phone(v)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        """Pydantic v2 compatibility"""
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema()
        )


class SafeEmail(str):
    """Email field with validation"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        return validate_safe_email(v)


class SafeUrl(str):
    """URL field with validation"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        return validate_safe_url(v)


# Base model with security validation
class SecureBaseModel(BaseModel):
    """Base model with built-in security validation"""

    model_config = {
        "validate_assignment": True,
        "use_enum_values": True,
        "populate_by_name": True,
        "validate_default": True
    }


# Validator decorators for common use cases
def secure_text_validator(max_length: Optional[int] = None):
    """Decorator for secure text validation"""
    def validator_func(cls, v):
        return validate_safe_text(v, max_length=max_length)
    # Note: Pydantic v2 validator decorators work differently
    # This is a simplified version for compatibility
    return validator_func


def secure_html_validator(allowed_tags: Optional[Set[str]] = None):
    """Decorator for secure HTML validation"""
    def validator_func(cls, v):
        return validate_safe_text(v, allow_html=True, allowed_tags=allowed_tags)
    # Note: Pydantic v2 validator decorators work differently
    # This is a simplified version for compatibility
    return validator_func


# Export main classes and functions
__all__ = [
    'SecurityValidationError',
    'validate_safe_text',
    'validate_safe_phone',
    'validate_safe_email',
    'validate_safe_url',
    'validate_safe_json',
    'validate_file_upload',
    'validate_content_type',
    'validate_user_agent',
    'SafeStr',
    'SafeHtml',
    'SafePhone',
    'SafeEmail',
    'SafeUrl',
    'SecureBaseModel',
    'secure_text_validator',
    'secure_html_validator'
]
