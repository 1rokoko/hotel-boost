"""
Database performance monitoring utilities
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import statistics

from app.core.logging import get_logger
from app.database import engine, get_connection_pool_stats

logger = get_logger(__name__)

@dataclass
class QueryMetrics:
    """Query performance metrics"""
    query_hash: str
    statement: str
    execution_count: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    last_executed: datetime
    slow_executions: int
    error_count: int

@dataclass
class ConnectionMetrics:
    """Connection pool metrics"""
    pool_size: int
    checked_out: int
    checked_in: int
    overflow: int
    total_connections: int
    utilization_percent: float
    timestamp: datetime

@dataclass
class DatabaseMetrics:
    """Overall database metrics"""
    total_queries: int
    queries_per_second: float
    avg_query_time_ms: float
    slow_queries: int
    failed_queries: int
    active_connections: int
    connection_utilization: float
    timestamp: datetime

class DatabasePerformanceMonitor:
    """
    Database performance monitoring system
    
    Tracks query performance, connection usage, and overall database health
    """
    
    def __init__(self, slow_query_threshold: float = 1000.0):
        """
        Initialize performance monitor
        
        Args:
            slow_query_threshold: Threshold in milliseconds for slow queries
        """
        self.slow_query_threshold = slow_query_threshold
        self.query_metrics: Dict[str, QueryMetrics] = {}
        self.connection_history: deque = deque(maxlen=1000)
        self.query_times: deque = deque(maxlen=10000)
        self.start_time = datetime.utcnow()
        self.total_queries = 0
        self.slow_queries = 0
        self.failed_queries = 0
        
    def record_query(
        self,
        statement: str,
        execution_time_ms: float,
        error: Optional[str] = None
    ) -> None:
        """
        Record query execution metrics
        
        Args:
            statement: SQL statement
            execution_time_ms: Execution time in milliseconds
            error: Error message if query failed
        """
        self.total_queries += 1
        self.query_times.append(execution_time_ms)
        
        if error:
            self.failed_queries += 1
        
        if execution_time_ms > self.slow_query_threshold:
            self.slow_queries += 1
        
        # Create query hash for grouping similar queries
        query_hash = self._hash_query(statement)
        
        if query_hash in self.query_metrics:
            metrics = self.query_metrics[query_hash]
            metrics.execution_count += 1
            metrics.total_time_ms += execution_time_ms
            metrics.avg_time_ms = metrics.total_time_ms / metrics.execution_count
            metrics.min_time_ms = min(metrics.min_time_ms, execution_time_ms)
            metrics.max_time_ms = max(metrics.max_time_ms, execution_time_ms)
            metrics.last_executed = datetime.utcnow()
            
            if execution_time_ms > self.slow_query_threshold:
                metrics.slow_executions += 1
            
            if error:
                metrics.error_count += 1
        else:
            self.query_metrics[query_hash] = QueryMetrics(
                query_hash=query_hash,
                statement=self._sanitize_statement(statement),
                execution_count=1,
                total_time_ms=execution_time_ms,
                avg_time_ms=execution_time_ms,
                min_time_ms=execution_time_ms,
                max_time_ms=execution_time_ms,
                last_executed=datetime.utcnow(),
                slow_executions=1 if execution_time_ms > self.slow_query_threshold else 0,
                error_count=1 if error else 0
            )
    
    async def record_connection_metrics(self) -> None:
        """Record current connection pool metrics"""
        try:
            pool_stats = await get_connection_pool_stats()
            
            if pool_stats:
                total_connections = (pool_stats.get('pool_size', 0) + 
                                   pool_stats.get('overflow', 0))
                utilization = 0
                if total_connections > 0:
                    utilization = (pool_stats.get('checked_out', 0) / total_connections) * 100
                
                metrics = ConnectionMetrics(
                    pool_size=pool_stats.get('pool_size', 0),
                    checked_out=pool_stats.get('checked_out', 0),
                    checked_in=pool_stats.get('checked_in', 0),
                    overflow=pool_stats.get('overflow', 0),
                    total_connections=total_connections,
                    utilization_percent=utilization,
                    timestamp=datetime.utcnow()
                )
                
                self.connection_history.append(metrics)
                
        except Exception as e:
            logger.error(f"Failed to record connection metrics: {str(e)}")
    
    def get_query_metrics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top query metrics
        
        Args:
            limit: Number of queries to return
            
        Returns:
            List[Dict[str, Any]]: Query metrics
        """
        # Sort by total execution time
        sorted_queries = sorted(
            self.query_metrics.values(),
            key=lambda x: x.total_time_ms,
            reverse=True
        )
        
        return [asdict(query) for query in sorted_queries[:limit]]
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get slowest queries
        
        Args:
            limit: Number of queries to return
            
        Returns:
            List[Dict[str, Any]]: Slow query metrics
        """
        slow_queries = [
            query for query in self.query_metrics.values()
            if query.slow_executions > 0
        ]
        
        # Sort by average execution time
        sorted_queries = sorted(
            slow_queries,
            key=lambda x: x.avg_time_ms,
            reverse=True
        )
        
        return [asdict(query) for query in sorted_queries[:limit]]
    
    def get_database_metrics(self) -> Dict[str, Any]:
        """
        Get overall database metrics
        
        Returns:
            Dict[str, Any]: Database metrics
        """
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        queries_per_second = self.total_queries / max(uptime_seconds, 1)
        
        avg_query_time = 0
        if self.query_times:
            avg_query_time = statistics.mean(self.query_times)
        
        # Get latest connection metrics
        connection_utilization = 0
        active_connections = 0
        if self.connection_history:
            latest_conn = self.connection_history[-1]
            connection_utilization = latest_conn.utilization_percent
            active_connections = latest_conn.checked_out
        
        return asdict(DatabaseMetrics(
            total_queries=self.total_queries,
            queries_per_second=round(queries_per_second, 2),
            avg_query_time_ms=round(avg_query_time, 2),
            slow_queries=self.slow_queries,
            failed_queries=self.failed_queries,
            active_connections=active_connections,
            connection_utilization=round(connection_utilization, 2),
            timestamp=datetime.utcnow()
        ))
    
    def get_connection_history(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Get connection metrics history
        
        Args:
            minutes: Number of minutes of history to return
            
        Returns:
            List[Dict[str, Any]]: Connection metrics history
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        filtered_history = [
            asdict(conn) for conn in self.connection_history
            if conn.timestamp >= cutoff_time
        ]
        
        return filtered_history
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive performance summary
        
        Returns:
            Dict[str, Any]: Performance summary
        """
        return {
            "database_metrics": self.get_database_metrics(),
            "top_queries": self.get_query_metrics(5),
            "slow_queries": self.get_slow_queries(5),
            "connection_metrics": self.connection_history[-1] if self.connection_history else None,
            "query_time_percentiles": self._get_query_time_percentiles(),
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds()
        }
    
    def reset_metrics(self) -> None:
        """Reset all metrics"""
        self.query_metrics.clear()
        self.connection_history.clear()
        self.query_times.clear()
        self.start_time = datetime.utcnow()
        self.total_queries = 0
        self.slow_queries = 0
        self.failed_queries = 0
    
    def _hash_query(self, statement: str) -> str:
        """
        Create hash for query grouping
        
        Args:
            statement: SQL statement
            
        Returns:
            str: Query hash
        """
        # Normalize query by removing parameters and extra whitespace
        normalized = " ".join(statement.split())
        # Simple hash based on query structure
        return str(hash(normalized))
    
    def _sanitize_statement(self, statement: str) -> str:
        """
        Sanitize SQL statement for storage
        
        Args:
            statement: SQL statement
            
        Returns:
            str: Sanitized statement
        """
        sanitized = " ".join(statement.split())
        if len(sanitized) > 200:
            sanitized = sanitized[:197] + "..."
        return sanitized
    
    def _get_query_time_percentiles(self) -> Dict[str, float]:
        """
        Get query time percentiles
        
        Returns:
            Dict[str, float]: Query time percentiles
        """
        if not self.query_times:
            return {}
        
        sorted_times = sorted(self.query_times)
        
        def percentile(data: List[float], p: float) -> float:
            index = int(len(data) * p / 100)
            return data[min(index, len(data) - 1)]
        
        return {
            "p50": round(percentile(sorted_times, 50), 2),
            "p90": round(percentile(sorted_times, 90), 2),
            "p95": round(percentile(sorted_times, 95), 2),
            "p99": round(percentile(sorted_times, 99), 2)
        }

# Global performance monitor instance
performance_monitor = DatabasePerformanceMonitor()

class DatabaseHealthChecker:
    """
    Database health monitoring system
    """
    
    def __init__(self):
        self.last_check = None
        self.health_history: deque = deque(maxlen=100)
    
    async def check_database_health(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Perform comprehensive database health check
        
        Args:
            session: Database session
            
        Returns:
            Dict[str, Any]: Health check results
        """
        health_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "checks": {}
        }
        
        try:
            # Basic connectivity check
            start_time = time.time()
            await session.execute(text("SELECT 1"))
            connectivity_time = (time.time() - start_time) * 1000
            
            health_data["checks"]["connectivity"] = {
                "status": "pass",
                "response_time_ms": round(connectivity_time, 2)
            }
            
            # Database version check
            try:
                result = await session.execute(text("SELECT version()"))
                version = result.scalar()
                health_data["checks"]["version"] = {
                    "status": "pass",
                    "version": version
                }
            except Exception as e:
                health_data["checks"]["version"] = {
                    "status": "fail",
                    "error": str(e)
                }
            
            # Table existence check
            try:
                result = await session.execute(text("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('hotels', 'guests', 'triggers', 'conversations', 'messages', 'staff_notifications')
                """))
                table_count = result.scalar()
                
                health_data["checks"]["tables"] = {
                    "status": "pass" if table_count == 6 else "warn",
                    "expected_tables": 6,
                    "found_tables": table_count
                }
            except Exception as e:
                health_data["checks"]["tables"] = {
                    "status": "fail",
                    "error": str(e)
                }
            
            # Connection pool check
            pool_stats = await get_connection_pool_stats()
            if pool_stats:
                utilization = 0
                if pool_stats.get('pool_size', 0) > 0:
                    utilization = (pool_stats.get('checked_out', 0) / pool_stats.get('pool_size', 1)) * 100
                
                health_data["checks"]["connection_pool"] = {
                    "status": "pass" if utilization < 80 else "warn",
                    "utilization_percent": round(utilization, 2),
                    "pool_stats": pool_stats
                }
            
            # Performance metrics check
            db_metrics = performance_monitor.get_database_metrics()
            health_data["checks"]["performance"] = {
                "status": "pass" if db_metrics["avg_query_time_ms"] < 1000 else "warn",
                "avg_query_time_ms": db_metrics["avg_query_time_ms"],
                "queries_per_second": db_metrics["queries_per_second"],
                "slow_queries": db_metrics["slow_queries"]
            }
            
        except Exception as e:
            health_data["status"] = "unhealthy"
            health_data["error"] = str(e)
            logger.error(f"Database health check failed: {str(e)}")
        
        # Determine overall status
        failed_checks = [
            check for check in health_data["checks"].values()
            if check.get("status") == "fail"
        ]
        
        if failed_checks:
            health_data["status"] = "unhealthy"
        elif any(check.get("status") == "warn" for check in health_data["checks"].values()):
            health_data["status"] = "degraded"
        
        self.last_check = datetime.utcnow()
        self.health_history.append(health_data)
        
        return health_data
    
    def get_health_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get health check history
        
        Args:
            limit: Number of health checks to return
            
        Returns:
            List[Dict[str, Any]]: Health check history
        """
        return list(self.health_history)[-limit:]

# Global health checker instance
health_checker = DatabaseHealthChecker()
