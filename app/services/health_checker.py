"""
Comprehensive health checking service for all system dependencies
"""

import asyncio
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import httpx
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.circuit_breaker import get_all_circuit_breakers, CircuitState

logger = get_logger(__name__)


class DependencyStatus(Enum):
    """Health status for dependencies"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    status: DependencyStatus
    response_time_ms: float
    details: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SystemHealthStatus:
    """Overall system health status"""
    overall_status: DependencyStatus
    checks: Dict[str, HealthCheckResult]
    circuit_breakers: Dict[str, Dict[str, Any]]
    total_check_time_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HealthChecker:
    """
    Comprehensive health checker for all system dependencies
    """
    
    def __init__(self):
        self.timeout = 10.0  # Default timeout for health checks
        self._cache = {}
        self._cache_ttl = 30  # Cache results for 30 seconds
    
    async def check_database(self, db: AsyncSession) -> HealthCheckResult:
        """Check database connectivity and performance"""
        start_time = time.time()
        
        try:
            # Basic connectivity check
            await db.execute(text("SELECT 1"))
            
            # Check current time (tests basic functionality)
            result = await db.execute(text("SELECT NOW() as current_time"))
            current_time = result.fetchone()
            
            # Test transaction capability
            await db.execute(text("BEGIN"))
            await db.execute(text("SELECT 1"))
            await db.execute(text("ROLLBACK"))
            
            # Check connection pool status
            pool_info = {}
            if hasattr(db.bind, 'pool'):
                pool = db.bind.pool
                pool_info = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": pool.invalid()
                }
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                status=DependencyStatus.HEALTHY,
                response_time_ms=round(response_time, 2),
                details="Database connection and operations successful",
                metadata={
                    "current_time": str(current_time[0]) if current_time else None,
                    "pool_info": pool_info
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("Database health check failed", error=str(e))
            
            return HealthCheckResult(
                status=DependencyStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                details="Database connection or operation failed",
                error=str(e)
            )
    
    async def check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity and performance"""
        start_time = time.time()
        redis_client = None
        
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=self.timeout
            )
            
            # Test basic operations
            await redis_client.ping()
            
            # Test read/write operations
            test_key = f"health_check_{int(time.time())}"
            await redis_client.set(test_key, "test_value", ex=10)
            value = await redis_client.get(test_key)
            await redis_client.delete(test_key)
            
            if value != "test_value":
                raise Exception("Redis read/write test failed")
            
            # Get Redis info
            info = await redis_client.info()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                status=DependencyStatus.HEALTHY,
                response_time_ms=round(response_time, 2),
                details="Redis connection and operations successful",
                metadata={
                    "redis_version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory_human": info.get("used_memory_human"),
                    "uptime_in_seconds": info.get("uptime_in_seconds")
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("Redis health check failed", error=str(e))
            
            return HealthCheckResult(
                status=DependencyStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                details="Redis connection or operation failed",
                error=str(e)
            )
        
        finally:
            if redis_client:
                await redis_client.close()
    
    async def check_green_api(self) -> HealthCheckResult:
        """Check Green API connectivity"""
        start_time = time.time()
        
        try:
            # Use a simple endpoint to check connectivity
            # This is a placeholder - adjust based on actual Green API endpoints
            timeout = httpx.Timeout(self.timeout)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Check if Green API is configured
                if not hasattr(settings, 'GREEN_API_URL') or not settings.GREEN_API_URL:
                    return HealthCheckResult(
                        status=DependencyStatus.UNKNOWN,
                        response_time_ms=0,
                        details="Green API not configured"
                    )
                
                # Simple connectivity check
                response = await client.get(f"{settings.GREEN_API_URL}/waInstance{settings.GREEN_API_INSTANCE}/getStateInstance/{settings.GREEN_API_TOKEN}")
                
                response_time = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    return HealthCheckResult(
                        status=DependencyStatus.HEALTHY,
                        response_time_ms=round(response_time, 2),
                        details="Green API is accessible",
                        metadata={"status_code": response.status_code}
                    )
                else:
                    return HealthCheckResult(
                        status=DependencyStatus.DEGRADED,
                        response_time_ms=round(response_time, 2),
                        details=f"Green API returned status {response.status_code}",
                        metadata={"status_code": response.status_code}
                    )
                    
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("Green API health check failed", error=str(e))
            
            return HealthCheckResult(
                status=DependencyStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                details="Green API connection failed",
                error=str(e)
            )
    
    async def check_deepseek_api(self) -> HealthCheckResult:
        """Check DeepSeek API connectivity"""
        start_time = time.time()
        
        try:
            # Check if DeepSeek API is configured
            if not hasattr(settings, 'DEEPSEEK_API_KEY') or not settings.DEEPSEEK_API_KEY:
                return HealthCheckResult(
                    status=DependencyStatus.UNKNOWN,
                    response_time_ms=0,
                    details="DeepSeek API not configured"
                )
            
            timeout = httpx.Timeout(self.timeout)
            headers = {
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            
            # Simple API test - get models list
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    "https://api.deepseek.com/v1/models",
                    headers=headers
                )
                
                response_time = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    return HealthCheckResult(
                        status=DependencyStatus.HEALTHY,
                        response_time_ms=round(response_time, 2),
                        details="DeepSeek API is accessible",
                        metadata={"status_code": response.status_code}
                    )
                else:
                    return HealthCheckResult(
                        status=DependencyStatus.DEGRADED,
                        response_time_ms=round(response_time, 2),
                        details=f"DeepSeek API returned status {response.status_code}",
                        metadata={"status_code": response.status_code}
                    )
                    
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("DeepSeek API health check failed", error=str(e))
            
            return HealthCheckResult(
                status=DependencyStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                details="DeepSeek API connection failed",
                error=str(e)
            )
    
    async def check_celery_workers(self) -> HealthCheckResult:
        """Check Celery workers status"""
        start_time = time.time()
        
        try:
            from app.core.celery_app import celery_app
            
            # Get worker statistics
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            active = inspect.active()
            
            response_time = (time.time() - start_time) * 1000
            
            if stats:
                worker_count = len(stats)
                active_tasks = sum(len(tasks) for tasks in active.values()) if active else 0
                
                return HealthCheckResult(
                    status=DependencyStatus.HEALTHY,
                    response_time_ms=round(response_time, 2),
                    details=f"{worker_count} Celery workers available",
                    metadata={
                        "worker_count": worker_count,
                        "active_tasks": active_tasks,
                        "workers": list(stats.keys()) if stats else []
                    }
                )
            else:
                return HealthCheckResult(
                    status=DependencyStatus.UNHEALTHY,
                    response_time_ms=round(response_time, 2),
                    details="No Celery workers available",
                    error="No workers found"
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error("Celery health check failed", error=str(e))
            
            return HealthCheckResult(
                status=DependencyStatus.UNHEALTHY,
                response_time_ms=round(response_time, 2),
                details="Celery workers check failed",
                error=str(e)
            )
    
    def _get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers"""
        circuit_breakers = get_all_circuit_breakers()
        status = {}
        
        for name, cb in circuit_breakers.items():
            metrics = cb.get_metrics()
            status[name] = {
                "state": cb.state.value,
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": round(metrics.success_rate(), 3),
                "failure_rate": round(metrics.failure_rate(), 3),
                "circuit_open_count": metrics.circuit_open_count,
                "last_failure_time": metrics.last_failure_time.isoformat() if metrics.last_failure_time else None,
                "last_success_time": metrics.last_success_time.isoformat() if metrics.last_success_time else None
            }
        
        return status
    
    async def check_all_dependencies(self, db: Optional[AsyncSession] = None) -> SystemHealthStatus:
        """
        Check all system dependencies
        
        Args:
            db: Database session (optional)
            
        Returns:
            SystemHealthStatus with all check results
        """
        start_time = time.time()
        checks = {}
        
        # Run all health checks concurrently
        tasks = {
            "redis": self.check_redis(),
            "green_api": self.check_green_api(),
            "deepseek_api": self.check_deepseek_api(),
            "celery_workers": self.check_celery_workers()
        }
        
        # Add database check if session provided
        if db:
            tasks["database"] = self.check_database(db)
        
        # Execute all checks
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Process results
        for i, (name, task) in enumerate(tasks.items()):
            result = results[i]
            if isinstance(result, Exception):
                checks[name] = HealthCheckResult(
                    status=DependencyStatus.UNHEALTHY,
                    response_time_ms=0,
                    details=f"Health check failed with exception",
                    error=str(result)
                )
            else:
                checks[name] = result
        
        # Get circuit breaker status
        circuit_breakers = self._get_circuit_breaker_status()
        
        # Determine overall status
        overall_status = self._determine_overall_status(checks, circuit_breakers)
        
        total_time = (time.time() - start_time) * 1000
        
        return SystemHealthStatus(
            overall_status=overall_status,
            checks=checks,
            circuit_breakers=circuit_breakers,
            total_check_time_ms=round(total_time, 2)
        )
    
    def _determine_overall_status(self, checks: Dict[str, HealthCheckResult], 
                                circuit_breakers: Dict[str, Dict[str, Any]]) -> DependencyStatus:
        """Determine overall system status based on individual checks"""
        
        # Count statuses
        status_counts = {status: 0 for status in DependencyStatus}
        for check in checks.values():
            status_counts[check.status] += 1
        
        # Check circuit breakers
        open_circuit_breakers = sum(1 for cb in circuit_breakers.values() 
                                  if cb["state"] == CircuitState.OPEN.value)
        
        # Determine overall status
        if status_counts[DependencyStatus.UNHEALTHY] > 0 or open_circuit_breakers > 2:
            return DependencyStatus.UNHEALTHY
        elif (status_counts[DependencyStatus.DEGRADED] > 0 or 
              open_circuit_breakers > 0 or 
              status_counts[DependencyStatus.UNKNOWN] > 1):
            return DependencyStatus.DEGRADED
        else:
            return DependencyStatus.HEALTHY


# Global health checker instance
health_checker = HealthChecker()
