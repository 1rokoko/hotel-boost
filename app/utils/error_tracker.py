"""
Error tracking utilities for monitoring and analyzing application errors.

This module provides utilities for tracking, categorizing, and analyzing
errors across the application for monitoring and alerting purposes.
"""

import hashlib
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict, Counter

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_

from app.core.config import settings
from app.core.logging import get_logger
from app.models.error_log import ErrorLog, ErrorSummary
from app.exceptions.custom_exceptions import BaseCustomException

logger = get_logger(__name__)


class ErrorTracker:
    """Tracks and analyzes application errors"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
    def track_error(
        self,
        error: Exception,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        hotel_id: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        status_code: Optional[int] = None,
        context_data: Optional[Dict[str, Any]] = None
    ) -> ErrorLog:
        """
        Track an error occurrence
        
        Args:
            error: The exception that occurred
            request_id: Request ID for correlation
            user_id: User ID if available
            hotel_id: Hotel ID if available
            method: HTTP method
            path: Request path
            status_code: HTTP status code
            context_data: Additional context information
            
        Returns:
            ErrorLog instance
        """
        # Extract error information
        error_type = type(error).__name__
        error_message = str(error)
        
        # Get error code and details for custom exceptions
        if isinstance(error, BaseCustomException):
            error_code = error.error_code
            error_details = error.details
            severity = self._get_severity_from_status_code(error.status_code)
        else:
            error_code = "INTERNAL_ERROR"
            error_details = {}
            severity = "error"
            
        # Create fingerprint for grouping
        fingerprint = ErrorLog.create_fingerprint(
            error_type=error_type,
            error_message=error_message,
            path=path,
            method=method
        )
        
        # Check if we have seen this error before
        existing_error = self.db.query(ErrorLog).filter(
            ErrorLog.fingerprint == fingerprint,
            ErrorLog.is_resolved == False
        ).first()
        
        if existing_error:
            # Update existing error
            existing_error.count += 1
            existing_error.last_seen = datetime.utcnow()
            
            # Update context if provided
            if context_data:
                if existing_error.context_data:
                    existing_error.context_data.update(context_data)
                else:
                    existing_error.context_data = context_data
                    
            self.db.commit()
            return existing_error
        else:
            # Create new error log
            error_log = ErrorLog(
                error_code=error_code,
                error_type=error_type,
                error_message=error_message,
                service_name="whatsapp-hotel-bot",
                environment=settings.ENVIRONMENT,
                version=settings.VERSION,
                request_id=request_id,
                user_id=user_id,
                hotel_id=hotel_id,
                method=method,
                path=path,
                status_code=status_code,
                stack_trace=traceback.format_exc() if settings.DEBUG else None,
                error_details=error_details,
                context_data=context_data,
                severity=severity,
                fingerprint=fingerprint
            )
            
            self.db.add(error_log)
            self.db.commit()
            
            logger.info(
                "New error tracked",
                error_id=str(error_log.id),
                error_type=error_type,
                fingerprint=fingerprint,
                hotel_id=hotel_id
            )
            
            return error_log
            
    def get_error_statistics(
        self,
        hotel_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get error statistics for a time period
        
        Args:
            hotel_id: Filter by hotel ID
            start_time: Start of time period
            end_time: End of time period
            
        Returns:
            Dictionary with error statistics
        """
        if not start_time:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if not end_time:
            end_time = datetime.utcnow()
            
        # Build query
        query = self.db.query(ErrorLog).filter(
            ErrorLog.timestamp >= start_time,
            ErrorLog.timestamp <= end_time
        )
        
        if hotel_id:
            query = query.filter(ErrorLog.hotel_id == hotel_id)
            
        errors = query.all()
        
        # Calculate statistics
        total_errors = len(errors)
        unique_errors = len(set(error.fingerprint for error in errors))
        
        # Count by severity
        severity_counts = Counter(error.severity for error in errors)
        
        # Count by error type
        error_type_counts = Counter(error.error_type for error in errors)
        
        # Count by path
        path_counts = Counter(error.path for error in errors if error.path)
        
        # Calculate error rate (errors per hour)
        time_diff = (end_time - start_time).total_seconds() / 3600
        error_rate = total_errors / time_diff if time_diff > 0 else 0
        
        return {
            'total_errors': total_errors,
            'unique_errors': unique_errors,
            'error_rate': round(error_rate, 2),
            'severity_breakdown': dict(severity_counts),
            'top_error_types': dict(error_type_counts.most_common(10)),
            'top_error_paths': dict(path_counts.most_common(10)),
            'time_period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            }
        }
        
    def get_error_trends(
        self,
        hotel_id: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get error trends over time
        
        Args:
            hotel_id: Filter by hotel ID
            hours: Number of hours to analyze
            
        Returns:
            List of hourly error counts
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Build query
        query = self.db.query(
            func.date_trunc('hour', ErrorLog.timestamp).label('hour'),
            func.count(ErrorLog.id).label('count'),
            func.count(func.distinct(ErrorLog.fingerprint)).label('unique_count')
        ).filter(
            ErrorLog.timestamp >= start_time,
            ErrorLog.timestamp <= end_time
        )
        
        if hotel_id:
            query = query.filter(ErrorLog.hotel_id == hotel_id)
            
        results = query.group_by('hour').order_by('hour').all()
        
        # Convert to list of dictionaries
        trends = []
        for result in results:
            trends.append({
                'hour': result.hour.isoformat(),
                'total_errors': result.count,
                'unique_errors': result.unique_count
            })
            
        return trends
        
    def get_top_errors(
        self,
        hotel_id: Optional[str] = None,
        limit: int = 10,
        resolved: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get top errors by frequency
        
        Args:
            hotel_id: Filter by hotel ID
            limit: Maximum number of errors to return
            resolved: Whether to include resolved errors
            
        Returns:
            List of top errors
        """
        query = self.db.query(ErrorLog).filter(
            ErrorLog.is_resolved == resolved
        )
        
        if hotel_id:
            query = query.filter(ErrorLog.hotel_id == hotel_id)
            
        errors = query.order_by(desc(ErrorLog.count)).limit(limit).all()
        
        return [error.to_dict() for error in errors]
        
    def resolve_error(
        self,
        error_id: str,
        resolved_by: str,
        resolution_note: Optional[str] = None
    ) -> bool:
        """
        Mark an error as resolved
        
        Args:
            error_id: Error ID to resolve
            resolved_by: User who resolved the error
            resolution_note: Optional resolution note
            
        Returns:
            True if error was resolved, False if not found
        """
        error = self.db.query(ErrorLog).filter(ErrorLog.id == error_id).first()
        
        if not error:
            return False
            
        error.is_resolved = True
        error.resolved_at = datetime.utcnow()
        error.resolved_by = resolved_by
        
        if resolution_note and error.context_data:
            error.context_data['resolution_note'] = resolution_note
        elif resolution_note:
            error.context_data = {'resolution_note': resolution_note}
            
        self.db.commit()
        
        logger.info(
            "Error resolved",
            error_id=error_id,
            resolved_by=resolved_by,
            fingerprint=error.fingerprint
        )
        
        return True
        
    def create_error_summary(
        self,
        period_start: datetime,
        period_end: datetime,
        period_type: str,
        hotel_id: Optional[str] = None
    ) -> ErrorSummary:
        """
        Create an error summary for a time period
        
        Args:
            period_start: Start of period
            period_end: End of period
            period_type: Type of period (hour, day, week, month)
            hotel_id: Optional hotel ID filter
            
        Returns:
            ErrorSummary instance
        """
        # Get errors for the period
        query = self.db.query(ErrorLog).filter(
            ErrorLog.timestamp >= period_start,
            ErrorLog.timestamp <= period_end
        )
        
        if hotel_id:
            query = query.filter(ErrorLog.hotel_id == hotel_id)
            
        errors = query.all()
        
        # Calculate statistics
        total_errors = len(errors)
        unique_errors = len(set(error.fingerprint for error in errors))
        
        severity_counts = Counter(error.severity for error in errors)
        error_type_counts = Counter(error.error_type for error in errors)
        path_counts = Counter(error.path for error in errors if error.path)
        
        # Calculate error rate
        time_diff = (period_end - period_start).total_seconds() / 3600
        error_rate = total_errors / time_diff if time_diff > 0 else 0
        
        # Create summary
        summary = ErrorSummary(
            period_start=period_start,
            period_end=period_end,
            period_type=period_type,
            hotel_id=hotel_id,
            environment=settings.ENVIRONMENT,
            total_errors=total_errors,
            unique_errors=unique_errors,
            critical_errors=severity_counts.get('critical', 0),
            error_errors=severity_counts.get('error', 0),
            warning_errors=severity_counts.get('warning', 0),
            top_error_types=dict(error_type_counts.most_common(5)),
            top_error_paths=dict(path_counts.most_common(5)),
            error_rate=int(error_rate)
        )
        
        self.db.add(summary)
        self.db.commit()
        
        return summary
        
    def _get_severity_from_status_code(self, status_code: int) -> str:
        """Get severity level from HTTP status code"""
        if status_code >= 500:
            return "error"
        elif status_code >= 400:
            return "warning"
        else:
            return "info"


class ErrorAnalyzer:
    """Analyzes error patterns and trends"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
    def detect_error_spikes(
        self,
        hotel_id: Optional[str] = None,
        threshold_multiplier: float = 3.0,
        hours_to_analyze: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Detect error spikes compared to historical average
        
        Args:
            hotel_id: Filter by hotel ID
            threshold_multiplier: Multiplier for spike detection
            hours_to_analyze: Hours to analyze for spikes
            
        Returns:
            List of detected spikes
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_to_analyze)
        
        # Get hourly error counts
        query = self.db.query(
            func.date_trunc('hour', ErrorLog.timestamp).label('hour'),
            func.count(ErrorLog.id).label('count')
        ).filter(
            ErrorLog.timestamp >= start_time,
            ErrorLog.timestamp <= end_time
        )
        
        if hotel_id:
            query = query.filter(ErrorLog.hotel_id == hotel_id)
            
        hourly_counts = query.group_by('hour').all()
        
        if len(hourly_counts) < 3:
            return []
            
        # Calculate average and detect spikes
        counts = [count.count for count in hourly_counts]
        average = sum(counts) / len(counts)
        threshold = average * threshold_multiplier
        
        spikes = []
        for hour_data in hourly_counts:
            if hour_data.count > threshold:
                spikes.append({
                    'hour': hour_data.hour.isoformat(),
                    'error_count': hour_data.count,
                    'average': round(average, 2),
                    'threshold': round(threshold, 2),
                    'spike_ratio': round(hour_data.count / average, 2)
                })
                
        return spikes
        
    def find_error_patterns(
        self,
        hotel_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Find patterns in error occurrences
        
        Args:
            hotel_id: Filter by hotel ID
            days: Number of days to analyze
            
        Returns:
            Dictionary with pattern analysis
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        query = self.db.query(ErrorLog).filter(
            ErrorLog.timestamp >= start_time,
            ErrorLog.timestamp <= end_time
        )
        
        if hotel_id:
            query = query.filter(ErrorLog.hotel_id == hotel_id)
            
        errors = query.all()
        
        # Analyze patterns
        hourly_distribution = defaultdict(int)
        daily_distribution = defaultdict(int)
        user_error_counts = defaultdict(int)
        path_error_counts = defaultdict(int)
        
        for error in errors:
            hour = error.timestamp.hour
            day = error.timestamp.strftime('%A')
            
            hourly_distribution[hour] += 1
            daily_distribution[day] += 1
            
            if error.user_id:
                user_error_counts[error.user_id] += 1
                
            if error.path:
                path_error_counts[error.path] += 1
                
        return {
            'hourly_distribution': dict(hourly_distribution),
            'daily_distribution': dict(daily_distribution),
            'top_error_users': dict(Counter(user_error_counts).most_common(10)),
            'top_error_paths': dict(Counter(path_error_counts).most_common(10)),
            'total_errors_analyzed': len(errors),
            'analysis_period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'days': days
            }
        }
