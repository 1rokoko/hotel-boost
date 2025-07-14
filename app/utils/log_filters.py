"""
Custom log filters for controlling log output.

This module provides various filters to control which log messages
are processed and output based on different criteria.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Union

from app.core.config import settings


class LevelFilter(logging.Filter):
    """Filter logs by level range"""
    
    def __init__(self, min_level: int = logging.DEBUG, max_level: int = logging.CRITICAL):
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter by log level range"""
        return self.min_level <= record.levelno <= self.max_level


class LoggerNameFilter(logging.Filter):
    """Filter logs by logger name patterns"""
    
    def __init__(self, include_patterns: Optional[List[str]] = None, 
                 exclude_patterns: Optional[List[str]] = None):
        super().__init__()
        self.include_patterns = [re.compile(pattern) for pattern in (include_patterns or [])]
        self.exclude_patterns = [re.compile(pattern) for pattern in (exclude_patterns or [])]
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter by logger name patterns"""
        logger_name = record.name
        
        # Check exclude patterns first
        for pattern in self.exclude_patterns:
            if pattern.search(logger_name):
                return False
                
        # If no include patterns, allow all (that weren't excluded)
        if not self.include_patterns:
            return True
            
        # Check include patterns
        for pattern in self.include_patterns:
            if pattern.search(logger_name):
                return True
                
        return False


class MessageFilter(logging.Filter):
    """Filter logs by message content"""
    
    def __init__(self, include_patterns: Optional[List[str]] = None,
                 exclude_patterns: Optional[List[str]] = None,
                 case_sensitive: bool = False):
        super().__init__()
        flags = 0 if case_sensitive else re.IGNORECASE
        self.include_patterns = [re.compile(pattern, flags) for pattern in (include_patterns or [])]
        self.exclude_patterns = [re.compile(pattern, flags) for pattern in (exclude_patterns or [])]
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter by message content"""
        message = record.getMessage()
        
        # Check exclude patterns first
        for pattern in self.exclude_patterns:
            if pattern.search(message):
                return False
                
        # If no include patterns, allow all (that weren't excluded)
        if not self.include_patterns:
            return True
            
        # Check include patterns
        for pattern in self.include_patterns:
            if pattern.search(message):
                return True
                
        return False


class AttributeFilter(logging.Filter):
    """Filter logs by record attributes"""
    
    def __init__(self, required_attributes: Optional[Dict[str, Any]] = None,
                 forbidden_attributes: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.required_attributes = required_attributes or {}
        self.forbidden_attributes = forbidden_attributes or {}
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter by record attributes"""
        # Check required attributes
        for attr_name, expected_value in self.required_attributes.items():
            if not hasattr(record, attr_name):
                return False
            actual_value = getattr(record, attr_name)
            if actual_value != expected_value:
                return False
                
        # Check forbidden attributes
        for attr_name, forbidden_value in self.forbidden_attributes.items():
            if hasattr(record, attr_name):
                actual_value = getattr(record, attr_name)
                if actual_value == forbidden_value:
                    return False
                    
        return True


class RateLimitFilter(logging.Filter):
    """Rate limit log messages to prevent spam"""
    
    def __init__(self, max_messages: int = 100, time_window: int = 60):
        super().__init__()
        self.max_messages = max_messages
        self.time_window = time_window
        self.message_counts: Dict[str, List[float]] = {}
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Rate limit messages"""
        import time
        
        current_time = time.time()
        message_key = f"{record.name}:{record.levelname}:{record.getMessage()}"
        
        # Clean old entries
        if message_key in self.message_counts:
            self.message_counts[message_key] = [
                timestamp for timestamp in self.message_counts[message_key]
                if current_time - timestamp < self.time_window
            ]
        else:
            self.message_counts[message_key] = []
            
        # Check rate limit
        if len(self.message_counts[message_key]) >= self.max_messages:
            return False
            
        # Add current message
        self.message_counts[message_key].append(current_time)
        return True


class SensitiveDataFilter(logging.Filter):
    """Filter out sensitive data from log messages"""
    
    def __init__(self, sensitive_patterns: Optional[List[str]] = None):
        super().__init__()
        default_patterns = [
            r'password["\s]*[:=]["\s]*[^"\s]+',
            r'token["\s]*[:=]["\s]*[^"\s]+',
            r'api_key["\s]*[:=]["\s]*[^"\s]+',
            r'secret["\s]*[:=]["\s]*[^"\s]+',
            r'authorization["\s]*[:=]["\s]*[^"\s]+',
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit card numbers
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        ]
        patterns = sensitive_patterns or default_patterns
        self.sensitive_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter sensitive data from messages"""
        # Check message
        message = record.getMessage()
        for pattern in self.sensitive_patterns:
            if pattern.search(message):
                # Replace sensitive data with placeholder
                record.msg = pattern.sub('***REDACTED***', str(record.msg))
                
        # Check record attributes
        for attr_name in dir(record):
            if not attr_name.startswith('_'):
                attr_value = getattr(record, attr_name)
                if isinstance(attr_value, str):
                    for pattern in self.sensitive_patterns:
                        if pattern.search(attr_value):
                            setattr(record, attr_name, pattern.sub('***REDACTED***', attr_value))
                            
        return True


class EnvironmentFilter(logging.Filter):
    """Filter logs based on environment"""
    
    def __init__(self, allowed_environments: Optional[List[str]] = None):
        super().__init__()
        self.allowed_environments = allowed_environments or ['development', 'staging', 'production']
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter by environment"""
        return settings.ENVIRONMENT in self.allowed_environments


class DebugFilter(logging.Filter):
    """Filter debug logs based on debug mode"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter debug logs"""
        if record.levelno == logging.DEBUG:
            return settings.DEBUG
        return True


class TenantFilter(logging.Filter):
    """Filter logs by tenant/hotel ID"""
    
    def __init__(self, allowed_tenants: Optional[Set[str]] = None,
                 blocked_tenants: Optional[Set[str]] = None):
        super().__init__()
        self.allowed_tenants = allowed_tenants
        self.blocked_tenants = blocked_tenants or set()
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter by tenant ID"""
        hotel_id = getattr(record, 'hotel_id', None)
        
        if hotel_id:
            # Check blocked tenants
            if hotel_id in self.blocked_tenants:
                return False
                
            # Check allowed tenants
            if self.allowed_tenants and hotel_id not in self.allowed_tenants:
                return False
                
        return True


class ErrorTypeFilter(logging.Filter):
    """Filter logs by error type"""
    
    def __init__(self, include_error_types: Optional[List[str]] = None,
                 exclude_error_types: Optional[List[str]] = None):
        super().__init__()
        self.include_error_types = set(include_error_types or [])
        self.exclude_error_types = set(exclude_error_types or [])
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter by error type"""
        error_type = getattr(record, 'error_type', None)
        
        if error_type:
            # Check exclude list first
            if error_type in self.exclude_error_types:
                return False
                
            # Check include list
            if self.include_error_types and error_type not in self.include_error_types:
                return False
                
        return True


class PerformanceFilter(logging.Filter):
    """Filter performance logs by thresholds"""
    
    def __init__(self, min_duration: Optional[float] = None,
                 max_duration: Optional[float] = None):
        super().__init__()
        self.min_duration = min_duration
        self.max_duration = max_duration
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter by performance thresholds"""
        duration = getattr(record, 'duration', None)
        
        if duration is not None:
            if self.min_duration is not None and duration < self.min_duration:
                return False
            if self.max_duration is not None and duration > self.max_duration:
                return False
                
        return True


class CompositeFilter(logging.Filter):
    """Combine multiple filters with AND/OR logic"""
    
    def __init__(self, filters: List[logging.Filter], logic: str = 'AND'):
        super().__init__()
        self.filters = filters
        self.logic = logic.upper()
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Apply composite filter logic"""
        if self.logic == 'AND':
            return all(f.filter(record) for f in self.filters)
        elif self.logic == 'OR':
            return any(f.filter(record) for f in self.filters)
        else:
            raise ValueError(f"Invalid logic: {self.logic}. Use 'AND' or 'OR'")


def create_default_filters() -> List[logging.Filter]:
    """Create default filters for the application"""
    filters = []
    
    # Always filter sensitive data
    filters.append(SensitiveDataFilter())
    
    # Filter by environment
    filters.append(EnvironmentFilter())
    
    # Filter debug logs in production
    if settings.ENVIRONMENT == 'production':
        filters.append(DebugFilter())
        
    # Rate limit to prevent spam
    filters.append(RateLimitFilter(max_messages=50, time_window=60))
    
    # Exclude noisy loggers in production
    if settings.ENVIRONMENT == 'production':
        filters.append(LoggerNameFilter(
            exclude_patterns=[
                r'uvicorn\.access',
                r'httpx',
                r'urllib3',
            ]
        ))
    
    return filters


def create_security_filters() -> List[logging.Filter]:
    """Create filters for security logs"""
    return [
        SensitiveDataFilter(),
        AttributeFilter(required_attributes={'log_type': 'security'}),
        LevelFilter(min_level=logging.WARNING)
    ]


def create_audit_filters() -> List[logging.Filter]:
    """Create filters for audit logs"""
    return [
        SensitiveDataFilter(),
        AttributeFilter(required_attributes={'log_type': 'audit'}),
        LevelFilter(min_level=logging.INFO)
    ]


def create_error_filters() -> List[logging.Filter]:
    """Create filters for error logs"""
    return [
        SensitiveDataFilter(),
        LevelFilter(min_level=logging.ERROR),
        RateLimitFilter(max_messages=20, time_window=60)
    ]
