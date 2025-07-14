"""
DeepSeek operation logging for WhatsApp Hotel Bot
"""

import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import uuid

import structlog
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.deepseek import DeepSeekOperationLog

logger = structlog.get_logger(__name__)


class DeepSeekLogger:
    """Logger for DeepSeek operations"""
    
    def __init__(self):
        self.operation_logs: List[DeepSeekOperationLog] = []
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_tokens_used': 0,
            'average_response_time': 0.0,
            'operations_by_type': {},
            'errors_by_type': {}
        }
    
    async def log_operation(
        self,
        operation_type: str,
        model_used: str,
        hotel_id: Optional[str] = None,
        guest_id: Optional[str] = None,
        message_id: Optional[str] = None,
        tokens_used: Optional[int] = None,
        api_response_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> DeepSeekOperationLog:
        """Log a DeepSeek operation"""
        
        log_entry = DeepSeekOperationLog(
            operation_type=operation_type,
            hotel_id=hotel_id,
            guest_id=guest_id,
            message_id=message_id,
            model_used=model_used,
            tokens_used=tokens_used,
            api_response_time_ms=api_response_time_ms,
            success=success,
            error_message=error_message,
            correlation_id=correlation_id or str(uuid.uuid4())
        )
        
        # Update metrics
        self._update_metrics(log_entry)
        
        # Store log entry
        self.operation_logs.append(log_entry)
        
        # Log to structured logger
        log_data = {
            'timestamp': log_entry.timestamp.isoformat(),
            'level': 'INFO' if success else 'ERROR',
            'service': 'whatsapp-hotel-bot',
            'component': 'deepseek',
            'operation': operation_type,
            'model': model_used,
            'correlation_id': log_entry.correlation_id,
            'success': success
        }
        
        if hotel_id:
            log_data['hotel_id'] = hotel_id
        if guest_id:
            log_data['guest_id'] = guest_id
        if message_id:
            log_data['message_id'] = message_id
        if tokens_used:
            log_data['tokens_used'] = tokens_used
        if api_response_time_ms:
            log_data['api_response_time_ms'] = api_response_time_ms
        if error_message:
            log_data['error_message'] = error_message
        
        if success:
            logger.info("DeepSeek operation completed", **log_data)
        else:
            logger.error("DeepSeek operation failed", **log_data)
        
        return log_entry
    
    def _update_metrics(self, log_entry: DeepSeekOperationLog):
        """Update internal metrics"""
        self.metrics['total_requests'] += 1
        
        if log_entry.success:
            self.metrics['successful_requests'] += 1
        else:
            self.metrics['failed_requests'] += 1
            
            # Track error types
            if log_entry.error_message:
                error_type = self._categorize_error(log_entry.error_message)
                self.metrics['errors_by_type'][error_type] = (
                    self.metrics['errors_by_type'].get(error_type, 0) + 1
                )
        
        # Track tokens
        if log_entry.tokens_used:
            self.metrics['total_tokens_used'] += log_entry.tokens_used
        
        # Track response times
        if log_entry.api_response_time_ms:
            current_avg = self.metrics['average_response_time']
            total_requests = self.metrics['total_requests']
            self.metrics['average_response_time'] = (
                (current_avg * (total_requests - 1) + log_entry.api_response_time_ms) / total_requests
            )
        
        # Track operations by type
        op_type = log_entry.operation_type
        self.metrics['operations_by_type'][op_type] = (
            self.metrics['operations_by_type'].get(op_type, 0) + 1
        )
    
    def _categorize_error(self, error_message: str) -> str:
        """Categorize error message"""
        error_lower = error_message.lower()
        
        if 'rate limit' in error_lower or 'too many requests' in error_lower:
            return 'rate_limit'
        elif 'timeout' in error_lower:
            return 'timeout'
        elif 'authentication' in error_lower or 'api key' in error_lower:
            return 'authentication'
        elif 'quota' in error_lower or 'billing' in error_lower:
            return 'quota_exceeded'
        elif 'network' in error_lower or 'connection' in error_lower:
            return 'network_error'
        elif 'invalid' in error_lower or 'bad request' in error_lower:
            return 'invalid_request'
        else:
            return 'unknown_error'
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics.copy()
    
    def get_recent_logs(self, limit: int = 100) -> List[DeepSeekOperationLog]:
        """Get recent operation logs"""
        return self.operation_logs[-limit:]
    
    def get_logs_by_hotel(self, hotel_id: str, limit: int = 50) -> List[DeepSeekOperationLog]:
        """Get logs for specific hotel"""
        hotel_logs = [log for log in self.operation_logs if log.hotel_id == hotel_id]
        return hotel_logs[-limit:]
    
    def get_error_logs(self, limit: int = 50) -> List[DeepSeekOperationLog]:
        """Get error logs"""
        error_logs = [log for log in self.operation_logs if not log.success]
        return error_logs[-limit:]
    
    def clear_old_logs(self, max_age_hours: int = 24):
        """Clear logs older than specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        self.operation_logs = [
            log for log in self.operation_logs 
            if log.timestamp > cutoff_time
        ]
        
        logger.info("Cleared old DeepSeek logs", 
                   cutoff_time=cutoff_time.isoformat(),
                   remaining_logs=len(self.operation_logs))
    
    def export_logs_json(self, limit: Optional[int] = None) -> str:
        """Export logs as JSON"""
        logs_to_export = self.operation_logs[-limit:] if limit else self.operation_logs
        
        export_data = {
            'export_timestamp': datetime.utcnow().isoformat(),
            'total_logs': len(logs_to_export),
            'metrics': self.metrics,
            'logs': [log.dict() for log in logs_to_export]
        }
        
        return json.dumps(export_data, indent=2, default=str)


# Global logger instance
_global_logger: Optional[DeepSeekLogger] = None


def get_deepseek_logger() -> DeepSeekLogger:
    """Get global DeepSeek logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = DeepSeekLogger()
    return _global_logger


async def log_deepseek_operation(
    operation_type: str,
    model_used: str,
    hotel_id: Optional[str] = None,
    guest_id: Optional[str] = None,
    message_id: Optional[str] = None,
    tokens_used: Optional[int] = None,
    api_response_time_ms: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> DeepSeekOperationLog:
    """Log a DeepSeek operation using global logger"""
    logger_instance = get_deepseek_logger()
    return await logger_instance.log_operation(
        operation_type=operation_type,
        model_used=model_used,
        hotel_id=hotel_id,
        guest_id=guest_id,
        message_id=message_id,
        tokens_used=tokens_used,
        api_response_time_ms=api_response_time_ms,
        success=success,
        error_message=error_message,
        correlation_id=correlation_id
    )


def get_deepseek_metrics() -> Dict[str, Any]:
    """Get DeepSeek metrics"""
    logger_instance = get_deepseek_logger()
    return logger_instance.get_metrics()


def get_deepseek_recent_logs(limit: int = 100) -> List[DeepSeekOperationLog]:
    """Get recent DeepSeek logs"""
    logger_instance = get_deepseek_logger()
    return logger_instance.get_recent_logs(limit)


def clear_old_deepseek_logs(max_age_hours: int = 24):
    """Clear old DeepSeek logs"""
    logger_instance = get_deepseek_logger()
    logger_instance.clear_old_logs(max_age_hours)


# Export main components
__all__ = [
    'DeepSeekLogger',
    'get_deepseek_logger',
    'log_deepseek_operation',
    'get_deepseek_metrics',
    'get_deepseek_recent_logs',
    'clear_old_deepseek_logs'
]
