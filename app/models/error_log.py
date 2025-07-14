"""
Error log model for storing and tracking application errors.

This module defines the database model for storing error information
for monitoring, analysis, and alerting purposes.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class ErrorLog(Base):
    """Model for storing application errors"""
    
    __tablename__ = "error_logs"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Error identification
    error_code = Column(String(100), nullable=False, index=True)
    error_type = Column(String(100), nullable=False, index=True)
    error_message = Column(Text, nullable=False)
    
    # Context information
    service_name = Column(String(100), nullable=False, default="whatsapp-hotel-bot")
    environment = Column(String(50), nullable=False, index=True)
    version = Column(String(50), nullable=True)
    
    # Request context
    request_id = Column(String(100), nullable=True, index=True)
    user_id = Column(String(100), nullable=True, index=True)
    hotel_id = Column(String(100), nullable=True, index=True)
    
    # HTTP context
    method = Column(String(10), nullable=True)
    path = Column(String(500), nullable=True)
    status_code = Column(Integer, nullable=True, index=True)
    
    # Error details
    stack_trace = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    context_data = Column(JSON, nullable=True)
    
    # Timing
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Tracking
    count = Column(Integer, nullable=False, default=1)
    first_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Status
    is_resolved = Column(Boolean, nullable=False, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    
    # Severity
    severity = Column(String(20), nullable=False, default="error", index=True)  # debug, info, warning, error, critical
    
    # Fingerprint for grouping similar errors
    fingerprint = Column(String(64), nullable=False, index=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_error_logs_timestamp_desc', timestamp.desc()),
        Index('idx_error_logs_hotel_timestamp', hotel_id, timestamp.desc()),
        Index('idx_error_logs_fingerprint_timestamp', fingerprint, timestamp.desc()),
        Index('idx_error_logs_severity_timestamp', severity, timestamp.desc()),
        Index('idx_error_logs_unresolved', is_resolved, timestamp.desc()),
    )
    
    def __repr__(self) -> str:
        return f"<ErrorLog(id={self.id}, error_type={self.error_type}, timestamp={self.timestamp})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': str(self.id),
            'error_code': self.error_code,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'service_name': self.service_name,
            'environment': self.environment,
            'version': self.version,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'hotel_id': self.hotel_id,
            'method': self.method,
            'path': self.path,
            'status_code': self.status_code,
            'stack_trace': self.stack_trace,
            'error_details': self.error_details,
            'context_data': self.context_data,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'count': self.count,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_resolved': self.is_resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
            'severity': self.severity,
            'fingerprint': self.fingerprint
        }
    
    @classmethod
    def create_fingerprint(
        cls,
        error_type: str,
        error_message: str,
        path: Optional[str] = None,
        method: Optional[str] = None
    ) -> str:
        """Create a fingerprint for grouping similar errors"""
        import hashlib
        
        # Normalize error message (remove dynamic parts)
        normalized_message = cls._normalize_error_message(error_message)
        
        # Create fingerprint components
        components = [error_type, normalized_message]
        
        if path:
            # Normalize path (remove IDs and dynamic parts)
            normalized_path = cls._normalize_path(path)
            components.append(normalized_path)
            
        if method:
            components.append(method)
            
        # Create hash
        fingerprint_string = '|'.join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]
    
    @staticmethod
    def _normalize_error_message(message: str) -> str:
        """Normalize error message by removing dynamic parts"""
        import re
        
        # Remove UUIDs
        message = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', 
                        'UUID', message, flags=re.IGNORECASE)
        
        # Remove numbers that might be IDs
        message = re.sub(r'\b\d{4,}\b', 'ID', message)
        
        # Remove timestamps
        message = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', 'TIMESTAMP', message)
        
        # Remove file paths
        message = re.sub(r'/[^\s]+\.py', '/PATH.py', message)
        
        # Remove line numbers
        message = re.sub(r'line \d+', 'line N', message)
        
        return message.strip()
    
    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize URL path by removing dynamic parts"""
        import re
        
        # Remove UUIDs from path
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 
                     '/{uuid}', path, flags=re.IGNORECASE)
        
        # Remove numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Remove query parameters
        path = path.split('?')[0]
        
        return path


class ErrorSummary(Base):
    """Model for storing error summaries and statistics"""
    
    __tablename__ = "error_summaries"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Time period
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    period_type = Column(String(20), nullable=False)  # hour, day, week, month
    
    # Context
    hotel_id = Column(String(100), nullable=True, index=True)
    environment = Column(String(50), nullable=False, index=True)
    
    # Statistics
    total_errors = Column(Integer, nullable=False, default=0)
    unique_errors = Column(Integer, nullable=False, default=0)
    critical_errors = Column(Integer, nullable=False, default=0)
    error_errors = Column(Integer, nullable=False, default=0)
    warning_errors = Column(Integer, nullable=False, default=0)
    
    # Top errors
    top_error_types = Column(JSON, nullable=True)
    top_error_paths = Column(JSON, nullable=True)
    
    # Trends
    error_rate = Column(Integer, nullable=False, default=0)  # errors per hour
    error_trend = Column(String(20), nullable=True)  # increasing, decreasing, stable
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_error_summaries_period', period_start, period_end),
        Index('idx_error_summaries_hotel_period', hotel_id, period_start, period_end),
    )
    
    def __repr__(self) -> str:
        return f"<ErrorSummary(id={self.id}, period={self.period_start}-{self.period_end}, total_errors={self.total_errors})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': str(self.id),
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'period_type': self.period_type,
            'hotel_id': self.hotel_id,
            'environment': self.environment,
            'total_errors': self.total_errors,
            'unique_errors': self.unique_errors,
            'critical_errors': self.critical_errors,
            'error_errors': self.error_errors,
            'warning_errors': self.warning_errors,
            'top_error_types': self.top_error_types,
            'top_error_paths': self.top_error_paths,
            'error_rate': self.error_rate,
            'error_trend': self.error_trend,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
