"""
Connection manager utilities for database connection lifecycle management
Provides connection health monitoring, automatic recovery, and performance optimization
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError, TimeoutError
from sqlalchemy import text
import structlog

from app.core.logging import get_logger
from app.core.database_pool import get_enhanced_pool, PoolConfiguration
from app.core.metrics import track_database_query

logger = get_logger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class ConnectionAttempt:
    """Connection attempt tracking"""
    timestamp: datetime
    success: bool
    duration_ms: float
    error: Optional[str] = None


class ConnectionManager:
    """Advanced connection manager with health monitoring and recovery"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logger.bind(component="connection_manager")
        
        # Connection state tracking
        self.connection_state = ConnectionState.HEALTHY
        self.last_health_check = datetime.utcnow()
        self.connection_attempts: List[ConnectionAttempt] = []
        self.consecutive_failures = 0
        
        # Performance tracking
        self.query_times: List[float] = []
        self.error_count = 0
        self.total_queries = 0
        
        # Recovery settings
        self.health_check_interval = 30  # seconds
        self.max_consecutive_failures = 5
        self.recovery_timeout = 300  # 5 minutes
    
    @asynccontextmanager
    async def get_session(self, timeout: Optional[float] = None):
        """Get a database session with automatic retry and health monitoring"""
        session = None
        start_time = time.time()
        
        try:
            # Get session from enhanced pool
            pool = get_enhanced_pool()
            session = await asyncio.wait_for(
                pool.get_session(),
                timeout=timeout or 30.0
            )
            
            # Record successful connection
            duration_ms = (time.time() - start_time) * 1000
            self._record_connection_attempt(True, duration_ms)
            
            yield session
            
        except (SQLAlchemyError, TimeoutError, asyncio.TimeoutError) as e:
            # Record failed connection
            duration_ms = (time.time() - start_time) * 1000
            self._record_connection_attempt(False, duration_ms, str(e))
            
            self.logger.error("Database connection failed", 
                            error=str(e), 
                            duration_ms=duration_ms)
            
            # Attempt recovery if needed
            if self.consecutive_failures >= self.max_consecutive_failures:
                await self._attempt_recovery()
            
            raise
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self._record_connection_attempt(False, duration_ms, str(e))
            self.logger.error("Unexpected connection error", error=str(e))
            raise
        
        finally:
            if session:
                try:
                    await session.close()
                except Exception as e:
                    self.logger.warning("Error closing session", error=str(e))
    
    async def execute_with_retry(
        self,
        query_func: Callable,
        *args,
        max_retries: Optional[int] = None,
        **kwargs
    ) -> Any:
        """Execute a database operation with automatic retry"""
        max_retries = max_retries or self.max_retries
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                
                async with self.get_session() as session:
                    result = await query_func(session, *args, **kwargs)
                    
                    # Track successful query
                    duration = (time.time() - start_time) * 1000
                    self._record_query_performance(duration, True)
                    
                    return result
                    
            except (DisconnectionError, TimeoutError) as e:
                last_error = e
                duration = (time.time() - start_time) * 1000
                self._record_query_performance(duration, False)
                
                if attempt < max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        "Database operation failed, retrying",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(
                        "Database operation failed after all retries",
                        attempts=max_retries + 1,
                        error=str(e)
                    )
                    raise
            
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                self._record_query_performance(duration, False)
                self.logger.error("Database operation error", error=str(e))
                raise
        
        if last_error:
            raise last_error
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        start_time = time.time()
        health_status = {
            "status": "unknown",
            "connection_state": self.connection_state.value,
            "last_check": self.last_health_check.isoformat(),
            "consecutive_failures": self.consecutive_failures,
            "performance": self._get_performance_metrics()
        }
        
        try:
            # Test basic connectivity
            async with self.get_session(timeout=10.0) as session:
                await session.execute(text("SELECT 1"))
                
            # Test pool health
            pool = get_enhanced_pool()
            pool_metrics = await pool.get_pool_metrics()
            
            health_status.update({
                "status": "healthy",
                "connection_test_ms": (time.time() - start_time) * 1000,
                "pool_utilization": pool_metrics.utilization_percent,
                "pool_size": pool_metrics.pool_size,
                "checked_out": pool_metrics.checked_out
            })
            
            self.connection_state = ConnectionState.HEALTHY
            self.consecutive_failures = 0
            
        except Exception as e:
            health_status.update({
                "status": "unhealthy",
                "error": str(e),
                "connection_test_ms": (time.time() - start_time) * 1000
            })
            
            self.connection_state = ConnectionState.FAILED
            self.consecutive_failures += 1
        
        self.last_health_check = datetime.utcnow()
        return health_status
    
    def _record_connection_attempt(self, success: bool, duration_ms: float, error: str = None):
        """Record connection attempt for tracking"""
        attempt = ConnectionAttempt(
            timestamp=datetime.utcnow(),
            success=success,
            duration_ms=duration_ms,
            error=error
        )
        
        self.connection_attempts.append(attempt)
        
        # Keep only recent attempts (last 100)
        if len(self.connection_attempts) > 100:
            self.connection_attempts = self.connection_attempts[-100:]
        
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
    
    def _record_query_performance(self, duration_ms: float, success: bool):
        """Record query performance metrics"""
        self.total_queries += 1
        
        if success:
            self.query_times.append(duration_ms)
            # Keep only recent query times (last 1000)
            if len(self.query_times) > 1000:
                self.query_times = self.query_times[-1000:]
        else:
            self.error_count += 1
        
        # Track in Prometheus metrics
        track_database_query(
            operation="query",
            table="unknown",
            duration=duration_ms / 1000,
            success=success
        )
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        if not self.query_times:
            return {
                "avg_query_time_ms": 0,
                "total_queries": self.total_queries,
                "error_rate": 0,
                "recent_attempts": len(self.connection_attempts)
            }
        
        import statistics
        
        return {
            "avg_query_time_ms": statistics.mean(self.query_times),
            "median_query_time_ms": statistics.median(self.query_times),
            "p95_query_time_ms": statistics.quantiles(self.query_times, n=20)[18] if len(self.query_times) > 20 else max(self.query_times),
            "total_queries": self.total_queries,
            "error_rate": self.error_count / max(self.total_queries, 1),
            "recent_attempts": len(self.connection_attempts),
            "successful_attempts": sum(1 for a in self.connection_attempts if a.success)
        }
    
    async def _attempt_recovery(self):
        """Attempt to recover from connection failures"""
        self.logger.warning("Attempting connection recovery", 
                          consecutive_failures=self.consecutive_failures)
        
        self.connection_state = ConnectionState.RECOVERING
        
        try:
            # Wait before attempting recovery
            await asyncio.sleep(5.0)
            
            # Perform health check
            health = await self.health_check()
            
            if health["status"] == "healthy":
                self.logger.info("Connection recovery successful")
                self.connection_state = ConnectionState.HEALTHY
                self.consecutive_failures = 0
            else:
                self.logger.error("Connection recovery failed", health=health)
                self.connection_state = ConnectionState.FAILED
                
        except Exception as e:
            self.logger.error("Error during connection recovery", error=str(e))
            self.connection_state = ConnectionState.FAILED


# Global connection manager instance
connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance"""
    return connection_manager
