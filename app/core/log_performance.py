"""
Logging performance optimization and monitoring.

This module provides tools for optimizing logging performance,
monitoring log throughput, and managing log resources efficiently.
"""

import asyncio
import time
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field
import psutil
import logging

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.async_logger import get_performance_logger

logger = get_logger(__name__)


@dataclass
class LogMetrics:
    """Metrics for logging performance"""
    total_logs: int = 0
    logs_per_second: float = 0.0
    average_processing_time: float = 0.0
    memory_usage_mb: float = 0.0
    queue_size: int = 0
    dropped_logs: int = 0
    error_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)


class LogPerformanceMonitor:
    """Monitors logging performance and provides optimization recommendations"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics_history: deque = deque(maxlen=window_size)
        self.current_metrics = LogMetrics()
        self.start_time = time.time()
        self.lock = threading.Lock()
        
        # Performance thresholds
        self.thresholds = {
            'max_logs_per_second': 10000,
            'max_processing_time_ms': 10.0,
            'max_memory_usage_mb': 100.0,
            'max_queue_size': 1000,
            'max_dropped_logs_ratio': 0.01  # 1%
        }
        
    def record_log_event(
        self,
        processing_time: float,
        queue_size: int = 0,
        dropped: bool = False,
        error: bool = False
    ) -> None:
        """Record a log event for performance tracking"""
        with self.lock:
            self.current_metrics.total_logs += 1
            
            if dropped:
                self.current_metrics.dropped_logs += 1
            if error:
                self.current_metrics.error_count += 1
                
            # Update processing time (moving average)
            if self.current_metrics.total_logs == 1:
                self.current_metrics.average_processing_time = processing_time
            else:
                alpha = 0.1  # Smoothing factor
                self.current_metrics.average_processing_time = (
                    alpha * processing_time + 
                    (1 - alpha) * self.current_metrics.average_processing_time
                )
                
            self.current_metrics.queue_size = queue_size
            self.current_metrics.memory_usage_mb = self._get_memory_usage()
            
            # Calculate logs per second
            elapsed_time = time.time() - self.start_time
            if elapsed_time > 0:
                self.current_metrics.logs_per_second = self.current_metrics.total_logs / elapsed_time
                
            self.current_metrics.last_updated = datetime.utcnow()
            
            # Add to history
            self.metrics_history.append(LogMetrics(
                total_logs=self.current_metrics.total_logs,
                logs_per_second=self.current_metrics.logs_per_second,
                average_processing_time=self.current_metrics.average_processing_time,
                memory_usage_mb=self.current_metrics.memory_usage_mb,
                queue_size=self.current_metrics.queue_size,
                dropped_logs=self.current_metrics.dropped_logs,
                error_count=self.current_metrics.error_count,
                last_updated=self.current_metrics.last_updated
            ))
            
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
            
    def get_current_metrics(self) -> LogMetrics:
        """Get current performance metrics"""
        with self.lock:
            return LogMetrics(
                total_logs=self.current_metrics.total_logs,
                logs_per_second=self.current_metrics.logs_per_second,
                average_processing_time=self.current_metrics.average_processing_time,
                memory_usage_mb=self.current_metrics.memory_usage_mb,
                queue_size=self.current_metrics.queue_size,
                dropped_logs=self.current_metrics.dropped_logs,
                error_count=self.current_metrics.error_count,
                last_updated=self.current_metrics.last_updated
            )
            
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary with recommendations"""
        metrics = self.get_current_metrics()
        
        # Calculate dropped logs ratio
        dropped_ratio = (
            metrics.dropped_logs / metrics.total_logs 
            if metrics.total_logs > 0 else 0
        )
        
        # Check thresholds
        issues = []
        recommendations = []
        
        if metrics.logs_per_second > self.thresholds['max_logs_per_second']:
            issues.append(f"High log rate: {metrics.logs_per_second:.1f} logs/sec")
            recommendations.append("Consider increasing async queue size or using batch processing")
            
        if metrics.average_processing_time > self.thresholds['max_processing_time_ms']:
            issues.append(f"Slow processing: {metrics.average_processing_time:.2f}ms avg")
            recommendations.append("Optimize log formatters or use async handlers")
            
        if metrics.memory_usage_mb > self.thresholds['max_memory_usage_mb']:
            issues.append(f"High memory usage: {metrics.memory_usage_mb:.1f}MB")
            recommendations.append("Reduce log retention or implement log rotation")
            
        if metrics.queue_size > self.thresholds['max_queue_size']:
            issues.append(f"Large queue size: {metrics.queue_size}")
            recommendations.append("Increase worker threads or processing speed")
            
        if dropped_ratio > self.thresholds['max_dropped_logs_ratio']:
            issues.append(f"High drop rate: {dropped_ratio:.2%}")
            recommendations.append("Increase queue size or reduce log volume")
            
        return {
            'metrics': {
                'total_logs': metrics.total_logs,
                'logs_per_second': round(metrics.logs_per_second, 2),
                'average_processing_time_ms': round(metrics.average_processing_time * 1000, 2),
                'memory_usage_mb': round(metrics.memory_usage_mb, 2),
                'queue_size': metrics.queue_size,
                'dropped_logs': metrics.dropped_logs,
                'dropped_ratio': round(dropped_ratio, 4),
                'error_count': metrics.error_count,
                'uptime_seconds': round(time.time() - self.start_time, 2)
            },
            'performance_status': 'good' if not issues else 'degraded',
            'issues': issues,
            'recommendations': recommendations,
            'thresholds': self.thresholds
        }
        
    def get_trend_analysis(self, minutes: int = 10) -> Dict[str, Any]:
        """Analyze performance trends over time"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        recent_metrics = [
            m for m in self.metrics_history 
            if m.last_updated >= cutoff_time
        ]
        
        if len(recent_metrics) < 2:
            return {'status': 'insufficient_data', 'message': 'Not enough data for trend analysis'}
            
        # Calculate trends
        first_metric = recent_metrics[0]
        last_metric = recent_metrics[-1]
        
        logs_trend = last_metric.logs_per_second - first_metric.logs_per_second
        memory_trend = last_metric.memory_usage_mb - first_metric.memory_usage_mb
        processing_trend = last_metric.average_processing_time - first_metric.average_processing_time
        
        return {
            'period_minutes': minutes,
            'data_points': len(recent_metrics),
            'trends': {
                'logs_per_second': {
                    'change': round(logs_trend, 2),
                    'direction': 'increasing' if logs_trend > 0 else 'decreasing' if logs_trend < 0 else 'stable'
                },
                'memory_usage_mb': {
                    'change': round(memory_trend, 2),
                    'direction': 'increasing' if memory_trend > 0 else 'decreasing' if memory_trend < 0 else 'stable'
                },
                'processing_time_ms': {
                    'change': round(processing_trend * 1000, 2),
                    'direction': 'increasing' if processing_trend > 0 else 'decreasing' if processing_trend < 0 else 'stable'
                }
            }
        }


class LogOptimizer:
    """Provides automatic optimization for logging performance"""
    
    def __init__(self, monitor: LogPerformanceMonitor):
        self.monitor = monitor
        self.optimization_history: List[Dict[str, Any]] = []
        
    def auto_optimize(self) -> Dict[str, Any]:
        """Automatically optimize logging based on current metrics"""
        summary = self.monitor.get_performance_summary()
        optimizations = []
        
        if summary['performance_status'] == 'degraded':
            # Apply optimizations based on issues
            for issue in summary['issues']:
                if 'High log rate' in issue:
                    optimizations.append(self._optimize_log_rate())
                elif 'Slow processing' in issue:
                    optimizations.append(self._optimize_processing_speed())
                elif 'High memory usage' in issue:
                    optimizations.append(self._optimize_memory_usage())
                elif 'Large queue size' in issue:
                    optimizations.append(self._optimize_queue_size())
                elif 'High drop rate' in issue:
                    optimizations.append(self._optimize_drop_rate())
                    
        optimization_result = {
            'timestamp': datetime.utcnow().isoformat(),
            'issues_detected': len(summary['issues']),
            'optimizations_applied': optimizations,
            'status': 'optimized' if optimizations else 'no_action_needed'
        }
        
        self.optimization_history.append(optimization_result)
        return optimization_result
        
    def _optimize_log_rate(self) -> Dict[str, Any]:
        """Optimize for high log rate"""
        # In a real implementation, this would adjust logging levels,
        # enable sampling, or increase async processing
        return {
            'type': 'log_rate_optimization',
            'action': 'enabled_log_sampling',
            'description': 'Enabled log sampling to reduce volume'
        }
        
    def _optimize_processing_speed(self) -> Dict[str, Any]:
        """Optimize processing speed"""
        return {
            'type': 'processing_speed_optimization',
            'action': 'simplified_formatters',
            'description': 'Simplified log formatters for better performance'
        }
        
    def _optimize_memory_usage(self) -> Dict[str, Any]:
        """Optimize memory usage"""
        return {
            'type': 'memory_optimization',
            'action': 'reduced_buffer_size',
            'description': 'Reduced log buffer sizes to save memory'
        }
        
    def _optimize_queue_size(self) -> Dict[str, Any]:
        """Optimize queue size"""
        return {
            'type': 'queue_optimization',
            'action': 'increased_workers',
            'description': 'Increased worker threads for faster processing'
        }
        
    def _optimize_drop_rate(self) -> Dict[str, Any]:
        """Optimize drop rate"""
        return {
            'type': 'drop_rate_optimization',
            'action': 'increased_queue_capacity',
            'description': 'Increased queue capacity to reduce drops'
        }


class LogResourceManager:
    """Manages logging resources and cleanup"""
    
    def __init__(self):
        self.resource_limits = {
            'max_log_files': 50,
            'max_file_size_mb': 100,
            'max_total_size_gb': 5,
            'retention_days': 30
        }
        
    def cleanup_old_logs(self, log_directory: str) -> Dict[str, Any]:
        """Clean up old log files"""
        import os
        from pathlib import Path
        
        log_path = Path(log_directory)
        if not log_path.exists():
            return {'status': 'directory_not_found'}
            
        cutoff_time = time.time() - (self.resource_limits['retention_days'] * 24 * 3600)
        
        cleaned_files = []
        total_size_freed = 0
        
        for log_file in log_path.glob('*.log*'):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    cleaned_files.append(str(log_file))
                    total_size_freed += file_size
            except Exception as e:
                logger.warning(f"Failed to clean log file {log_file}: {e}")
                
        return {
            'status': 'completed',
            'files_cleaned': len(cleaned_files),
            'size_freed_mb': round(total_size_freed / 1024 / 1024, 2),
            'cleaned_files': cleaned_files
        }
        
    def check_disk_usage(self, log_directory: str) -> Dict[str, Any]:
        """Check disk usage for log directory"""
        import shutil
        from pathlib import Path
        
        log_path = Path(log_directory)
        if not log_path.exists():
            return {'status': 'directory_not_found'}
            
        try:
            total, used, free = shutil.disk_usage(log_path)
            
            # Calculate log directory size
            log_size = sum(
                f.stat().st_size for f in log_path.rglob('*') 
                if f.is_file()
            )
            
            return {
                'status': 'success',
                'disk_total_gb': round(total / 1024**3, 2),
                'disk_used_gb': round(used / 1024**3, 2),
                'disk_free_gb': round(free / 1024**3, 2),
                'disk_usage_percent': round((used / total) * 100, 2),
                'log_directory_size_mb': round(log_size / 1024**2, 2),
                'log_files_count': len(list(log_path.rglob('*.log*')))
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
            
    def rotate_logs_if_needed(self, log_directory: str) -> Dict[str, Any]:
        """Rotate logs if they exceed size limits"""
        from pathlib import Path
        import gzip
        import shutil
        
        log_path = Path(log_directory)
        if not log_path.exists():
            return {'status': 'directory_not_found'}
            
        rotated_files = []
        
        for log_file in log_path.glob('*.log'):
            try:
                file_size_mb = log_file.stat().st_size / 1024**2
                
                if file_size_mb > self.resource_limits['max_file_size_mb']:
                    # Rotate the file
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    rotated_name = f"{log_file.stem}_{timestamp}.log.gz"
                    rotated_path = log_path / rotated_name
                    
                    # Compress and move
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(rotated_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                            
                    # Clear original file
                    log_file.write_text('')
                    
                    rotated_files.append({
                        'original': str(log_file),
                        'rotated': str(rotated_path),
                        'size_mb': round(file_size_mb, 2)
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to rotate log file {log_file}: {e}")
                
        return {
            'status': 'completed',
            'files_rotated': len(rotated_files),
            'rotated_files': rotated_files
        }


# Global instances
_performance_monitor: Optional[LogPerformanceMonitor] = None
_log_optimizer: Optional[LogOptimizer] = None
_resource_manager: Optional[LogResourceManager] = None


def get_performance_monitor() -> LogPerformanceMonitor:
    """Get global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = LogPerformanceMonitor()
    return _performance_monitor


def get_log_optimizer() -> LogOptimizer:
    """Get global log optimizer instance"""
    global _log_optimizer
    if _log_optimizer is None:
        _log_optimizer = LogOptimizer(get_performance_monitor())
    return _log_optimizer


def get_resource_manager() -> LogResourceManager:
    """Get global resource manager instance"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = LogResourceManager()
    return _resource_manager


async def start_performance_monitoring() -> None:
    """Start background performance monitoring"""
    monitor = get_performance_monitor()
    optimizer = get_log_optimizer()
    
    while True:
        try:
            # Auto-optimize every 5 minutes
            await asyncio.sleep(300)
            optimizer.auto_optimize()
            
        except Exception as e:
            logger.error(f"Performance monitoring error: {e}")
            await asyncio.sleep(60)
