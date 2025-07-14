"""
Performance monitoring dashboard integration for WhatsApp Hotel Bot
Provides real-time performance metrics and alerting
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

import structlog
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest

from app.core.database_pool import get_enhanced_pool
from app.services.cache_service import get_cache_service
from app.utils.query_optimizer import get_query_analyzer
from app.utils.memory_optimizer import get_memory_profiler
from app.utils.async_optimizer import get_async_optimizer
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceAlert:
    """Performance alert definition"""
    metric_name: str
    threshold: float
    current_value: float
    severity: str  # "warning", "critical"
    message: str
    timestamp: datetime


class PerformanceMetricsCollector:
    """Collects performance metrics from all optimization components"""
    
    def __init__(self):
        self.logger = logger.bind(component="performance_metrics")
        self.registry = CollectorRegistry()
        self._setup_prometheus_metrics()
        
        # Alert thresholds
        self.alert_thresholds = {
            "database_pool_utilization": {"warning": 70.0, "critical": 85.0},
            "cache_hit_rate": {"warning": 80.0, "critical": 70.0},  # Lower is worse
            "memory_usage_percent": {"warning": 75.0, "critical": 90.0},
            "avg_response_time_ms": {"warning": 1000.0, "critical": 2000.0},
            "error_rate_percent": {"warning": 1.0, "critical": 5.0}
        }
        
        self.active_alerts: List[PerformanceAlert] = []
    
    def _setup_prometheus_metrics(self):
        """Setup Prometheus metrics"""
        # Database metrics
        self.db_pool_utilization = Gauge(
            'db_pool_utilization_percent',
            'Database connection pool utilization percentage',
            registry=self.registry
        )
        
        self.db_query_duration = Histogram(
            'db_query_duration_seconds',
            'Database query duration',
            ['operation', 'table'],
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_hit_rate = Gauge(
            'cache_hit_rate_percent',
            'Cache hit rate percentage',
            ['cache_level'],
            registry=self.registry
        )
        
        self.cache_operation_duration = Histogram(
            'cache_operation_duration_seconds',
            'Cache operation duration',
            ['operation', 'level'],
            registry=self.registry
        )
        
        # Memory metrics
        self.memory_usage = Gauge(
            'memory_usage_mb',
            'Memory usage in megabytes',
            registry=self.registry
        )
        
        self.memory_usage_percent = Gauge(
            'memory_usage_percent',
            'Memory usage percentage',
            registry=self.registry
        )
        
        # Async metrics
        self.async_task_duration = Histogram(
            'async_task_duration_seconds',
            'Async task duration',
            ['operation_type'],
            registry=self.registry
        )
        
        self.active_async_tasks = Gauge(
            'active_async_tasks',
            'Number of active async tasks',
            registry=self.registry
        )
        
        # Performance alerts
        self.performance_alerts = Counter(
            'performance_alerts_total',
            'Total number of performance alerts',
            ['metric', 'severity'],
            registry=self.registry
        )
    
    async def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect metrics from all performance components"""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "database": await self._collect_database_metrics(),
            "cache": await self._collect_cache_metrics(),
            "memory": await self._collect_memory_metrics(),
            "async": await self._collect_async_metrics()
        }
        
        # Update Prometheus metrics
        await self._update_prometheus_metrics(metrics)
        
        # Check for alerts
        alerts = self._check_alerts(metrics)
        if alerts:
            self.active_alerts.extend(alerts)
            for alert in alerts:
                self.performance_alerts.labels(
                    metric=alert.metric_name,
                    severity=alert.severity
                ).inc()
        
        return metrics
    
    async def _collect_database_metrics(self) -> Dict[str, Any]:
        """Collect database performance metrics"""
        try:
            pool = get_enhanced_pool()
            pool_metrics = await pool.get_pool_metrics()
            pool_summary = await pool.get_performance_summary()
            
            query_analyzer = get_query_analyzer()
            query_summary = query_analyzer.get_performance_summary()
            
            return {
                "pool_utilization_percent": pool_metrics.utilization_percent,
                "pool_size": pool_metrics.pool_size,
                "checked_out_connections": pool_metrics.checked_out,
                "avg_checkout_time_ms": pool_metrics.avg_checkout_time_ms,
                "total_queries": query_summary.get("total_queries", 0),
                "slow_queries": query_summary.get("slow_queries", 0),
                "avg_query_time_ms": query_summary.get("avg_execution_time_ms", 0),
                "n1_detections": query_summary.get("n1_detections", 0)
            }
        except Exception as e:
            self.logger.error("Failed to collect database metrics", error=str(e))
            return {}
    
    async def _collect_cache_metrics(self) -> Dict[str, Any]:
        """Collect cache performance metrics"""
        try:
            cache_service = await get_cache_service()
            cache_stats = await cache_service.get_cache_stats()
            
            metrics = cache_stats.get("metrics", {})
            hit_rate = metrics.get("hit_rate_percent", 0)
            
            return {
                "hit_rate_percent": hit_rate,
                "total_hits": metrics.get("hits", 0),
                "total_misses": metrics.get("misses", 0),
                "total_operations": metrics.get("total_operations", 0),
                "memory_cache_size": cache_stats.get("memory_cache", {}).get("size", 0),
                "memory_cache_utilization": cache_stats.get("memory_cache", {}).get("utilization_percent", 0),
                "redis_memory_usage": cache_stats.get("redis_cache", {}).get("used_memory", 0)
            }
        except Exception as e:
            self.logger.error("Failed to collect cache metrics", error=str(e))
            return {}
    
    async def _collect_memory_metrics(self) -> Dict[str, Any]:
        """Collect memory performance metrics"""
        try:
            profiler = get_memory_profiler()
            memory_report = profiler.get_memory_report()
            
            current_snapshot = memory_report.get("current_snapshot", {})
            
            return {
                "process_memory_mb": current_snapshot.get("process_memory_mb", 0),
                "memory_percent": current_snapshot.get("memory_percent", 0),
                "gc_objects": current_snapshot.get("gc_objects", 0),
                "tracemalloc_current_mb": current_snapshot.get("tracemalloc_current_mb", 0),
                "tracemalloc_peak_mb": current_snapshot.get("tracemalloc_peak_mb", 0),
                "memory_leaks": len(memory_report.get("memory_leaks", [])),
                "trends": memory_report.get("trends", {})
            }
        except Exception as e:
            self.logger.error("Failed to collect memory metrics", error=str(e))
            return {}
    
    async def _collect_async_metrics(self) -> Dict[str, Any]:
        """Collect async processing metrics"""
        try:
            optimizer = get_async_optimizer()
            async_stats = optimizer.task_pool.get_performance_stats()
            
            return {
                "active_tasks": async_stats.get("active_tasks", 0),
                "completed_tasks": async_stats.get("completed_tasks", 0),
                "operation_stats": async_stats.get("operation_stats", {})
            }
        except Exception as e:
            self.logger.error("Failed to collect async metrics", error=str(e))
            return {}
    
    async def _update_prometheus_metrics(self, metrics: Dict[str, Any]):
        """Update Prometheus metrics"""
        try:
            # Database metrics
            db_metrics = metrics.get("database", {})
            if db_metrics:
                self.db_pool_utilization.set(db_metrics.get("pool_utilization_percent", 0))
            
            # Cache metrics
            cache_metrics = metrics.get("cache", {})
            if cache_metrics:
                self.cache_hit_rate.labels(cache_level="overall").set(
                    cache_metrics.get("hit_rate_percent", 0)
                )
            
            # Memory metrics
            memory_metrics = metrics.get("memory", {})
            if memory_metrics:
                self.memory_usage.set(memory_metrics.get("process_memory_mb", 0))
                self.memory_usage_percent.set(memory_metrics.get("memory_percent", 0))
            
            # Async metrics
            async_metrics = metrics.get("async", {})
            if async_metrics:
                self.active_async_tasks.set(async_metrics.get("active_tasks", 0))
                
        except Exception as e:
            self.logger.error("Failed to update Prometheus metrics", error=str(e))
    
    def _check_alerts(self, metrics: Dict[str, Any]) -> List[PerformanceAlert]:
        """Check for performance alerts"""
        alerts = []
        
        try:
            # Database pool utilization
            db_utilization = metrics.get("database", {}).get("pool_utilization_percent", 0)
            alerts.extend(self._check_threshold_alert(
                "database_pool_utilization",
                db_utilization,
                "Database connection pool utilization"
            ))
            
            # Cache hit rate (lower is worse)
            cache_hit_rate = metrics.get("cache", {}).get("hit_rate_percent", 100)
            if cache_hit_rate < self.alert_thresholds["cache_hit_rate"]["critical"]:
                alerts.append(PerformanceAlert(
                    metric_name="cache_hit_rate",
                    threshold=self.alert_thresholds["cache_hit_rate"]["critical"],
                    current_value=cache_hit_rate,
                    severity="critical",
                    message=f"Cache hit rate critically low: {cache_hit_rate:.1f}%",
                    timestamp=datetime.utcnow()
                ))
            elif cache_hit_rate < self.alert_thresholds["cache_hit_rate"]["warning"]:
                alerts.append(PerformanceAlert(
                    metric_name="cache_hit_rate",
                    threshold=self.alert_thresholds["cache_hit_rate"]["warning"],
                    current_value=cache_hit_rate,
                    severity="warning",
                    message=f"Cache hit rate low: {cache_hit_rate:.1f}%",
                    timestamp=datetime.utcnow()
                ))
            
            # Memory usage
            memory_percent = metrics.get("memory", {}).get("memory_percent", 0)
            alerts.extend(self._check_threshold_alert(
                "memory_usage_percent",
                memory_percent,
                "Memory usage"
            ))
            
            # Query performance
            avg_query_time = metrics.get("database", {}).get("avg_query_time_ms", 0)
            alerts.extend(self._check_threshold_alert(
                "avg_response_time_ms",
                avg_query_time,
                "Average query response time"
            ))
            
        except Exception as e:
            self.logger.error("Failed to check alerts", error=str(e))
        
        return alerts
    
    def _check_threshold_alert(self, metric_name: str, current_value: float, description: str) -> List[PerformanceAlert]:
        """Check threshold-based alerts"""
        alerts = []
        thresholds = self.alert_thresholds.get(metric_name, {})
        
        if current_value > thresholds.get("critical", float('inf')):
            alerts.append(PerformanceAlert(
                metric_name=metric_name,
                threshold=thresholds["critical"],
                current_value=current_value,
                severity="critical",
                message=f"{description} critically high: {current_value:.1f}",
                timestamp=datetime.utcnow()
            ))
        elif current_value > thresholds.get("warning", float('inf')):
            alerts.append(PerformanceAlert(
                metric_name=metric_name,
                threshold=thresholds["warning"],
                current_value=current_value,
                severity="warning",
                message=f"{description} high: {current_value:.1f}",
                timestamp=datetime.utcnow()
            ))
        
        return alerts
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format"""
        return generate_latest(self.registry).decode('utf-8')
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active performance alerts"""
        # Clean up old alerts (older than 1 hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        self.active_alerts = [
            alert for alert in self.active_alerts
            if alert.timestamp > cutoff_time
        ]
        
        return [asdict(alert) for alert in self.active_alerts]


# Global metrics collector
performance_metrics_collector: Optional[PerformanceMetricsCollector] = None


def get_performance_metrics_collector() -> PerformanceMetricsCollector:
    """Get the global performance metrics collector"""
    global performance_metrics_collector
    if performance_metrics_collector is None:
        performance_metrics_collector = PerformanceMetricsCollector()
    return performance_metrics_collector


async def start_performance_monitoring(interval_seconds: int = 60):
    """Start continuous performance monitoring"""
    collector = get_performance_metrics_collector()
    
    async def monitoring_loop():
        while True:
            try:
                metrics = await collector.collect_all_metrics()
                logger.debug("Performance metrics collected", 
                           timestamp=metrics["timestamp"])
            except Exception as e:
                logger.error("Error in performance monitoring", error=str(e))
            
            await asyncio.sleep(interval_seconds)
    
    # Start monitoring task
    asyncio.create_task(monitoring_loop())
    logger.info("Performance monitoring started", interval=interval_seconds)
