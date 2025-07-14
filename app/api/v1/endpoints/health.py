"""
Health check endpoints with comprehensive dependency monitoring
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis.asyncio as redis
import httpx
import time
import asyncio
from typing import Dict, Any, Optional

from app.core.config import settings
from app.database import get_db
from app.core.logging import get_logger
from app.utils.circuit_breaker import get_all_circuit_breakers
from app.services.health_checker import HealthChecker, DependencyStatus

router = APIRouter()
logger = get_logger(__name__)

# Health check cache to avoid overwhelming dependencies
_health_cache = {}
_cache_ttl = 30  # seconds


def check_database(db: Session) -> Dict[str, Any]:
    """Check database connectivity and basic functionality"""
    try:
        fallback_service = fallbackService(db)
        start_time = time.time()

        # Simple connectivity check
        result = db.execute(text("SELECT 1"))
        result.fetchone()

        # Check if we can write (basic transaction test)
        db.execute(text("SELECT NOW()"))
        db.commit()

        response_time = (time.time() - start_time) * 1000

        return {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "details": "Database connection and basic operations successful"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Database connection or operation failed"
        }


async def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity and basic functionality"""
    try:
        start_time = time.time()

        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )

        # Test basic operations
        await redis_client.ping()
        test_key = f"health_check_{int(time.time())}"
        await redis_client.set(test_key, "test", ex=10)
        value = await redis_client.get(test_key)
        await redis_client.delete(test_key)

        response_time = (time.time() - start_time) * 1000

        await redis_client.close()

        if value != "test":
            raise Exception("Redis read/write test failed")

        return {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "details": "Redis connection and basic operations successful"
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "details": "Redis connection or operation failed"
        }


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    service: str
    version: str
    timestamp: datetime
    environment: str

@router.get("/", response_model=HealthResponse)
def health_check():
    """
    Health check endpoint
    Returns the current status of the service
    """
    return HealthResponse(
        status="healthy",
        service="whatsapp-hotel-bot",
        version=settings.VERSION,
        timestamp=datetime.now(timezone.utc),
        environment=settings.ENVIRONMENT
    )

@router.get("/live")
def liveness_check():
    """
    Liveness probe - indicates if the application is running
    Should return 200 if the application is alive
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "whatsapp-hotel-bot",
        "version": getattr(settings, 'VERSION', '1.0.0')
    }


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe - indicates if the application is ready to serve traffic
    Checks all critical dependencies with comprehensive health monitoring
    """
    current_time = time.time()
    cache_key = "readiness_check"

    # Check cache first
    if cache_key in _health_cache:
        cached_result, cached_time = _health_cache[cache_key]
        if current_time - cached_time < _cache_ttl:
            return cached_result

    start_time = time.time()

    # Use comprehensive health checker
    health_checker = HealthChecker()
    system_health = await health_checker.check_all_dependencies(db)

    # Convert to readiness response format
    checks = {}
    for name, result in system_health.checks.items():
        checks[name] = {
            "status": result.status.value,
            "response_time_ms": result.response_time_ms,
            "details": result.details,
            "error": result.error,
            "metadata": result.metadata
        }

    # Add circuit breaker information
    checks["circuit_breakers"] = {
        "status": "healthy" if system_health.overall_status.value != "unhealthy" else "degraded",
        "details": f"Circuit breakers status: {len(system_health.circuit_breakers)} monitored",
        "metadata": system_health.circuit_breakers
    }

    total_time = (time.time() - start_time) * 1000

    result = {
        "status": system_health.overall_status.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_check_time_ms": round(total_time, 2),
        "checks": checks,
        "system_health": {
            "degradation_level": system_health.overall_status.value,
            "circuit_breakers_summary": {
                "total": len(system_health.circuit_breakers),
                "open": sum(1 for cb in system_health.circuit_breakers.values() if cb["state"] == "open"),
                "closed": sum(1 for cb in system_health.circuit_breakers.values() if cb["state"] == "closed"),
                "half_open": sum(1 for cb in system_health.circuit_breakers.values() if cb["state"] == "half_open")
            }
        }
    }

    # Cache the result
    _health_cache[cache_key] = (result, current_time)

    if system_health.overall_status.value == "unhealthy":
        raise HTTPException(status_code=503, detail=result)

    return result


@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check endpoint with comprehensive system information
    Returns detailed information about service dependencies and reliability components
    """
    health_checker = HealthChecker()
    system_health = await health_checker.check_all_dependencies(db)

    # Get circuit breaker details
    from app.utils.circuit_breaker import get_all_circuit_breakers
    circuit_breakers = get_all_circuit_breakers()
    cb_details = {}
    for name, cb in circuit_breakers.items():
        metrics = cb.get_metrics()
        cb_details[name] = {
            "state": cb.state.value,
            "metrics": {
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": round(metrics.success_rate(), 3),
                "failure_rate": round(metrics.failure_rate(), 3),
                "circuit_open_count": metrics.circuit_open_count
            }
        }

    # Get degradation status
    from app.services.fallback_service import fallback_service
    degradation_status = fallback_service.get_degradation_status()

    return {
        "status": system_health.overall_status.value,
        "service": "whatsapp-hotel-bot",
        "version": getattr(settings, 'VERSION', '1.0.0'),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": getattr(settings, 'ENVIRONMENT', 'development'),
        "system_health": {
            "overall_status": system_health.overall_status.value,
            "total_check_time_ms": system_health.total_check_time_ms,
            "dependencies": {
                name: {
                    "status": result.status.value,
                    "response_time_ms": result.response_time_ms,
                    "details": result.details,
                    "error": result.error,
                    "metadata": result.metadata
                }
                for name, result in system_health.checks.items()
            }
        },
        "reliability_components": {
            "circuit_breakers": cb_details,
            "degradation": degradation_status
        }
    }


@router.get("/circuit-breakers")
def circuit_breakers_status():
    """
    Get detailed circuit breaker status
    """
    from app.utils.circuit_breaker import get_all_circuit_breakers

    circuit_breakers = get_all_circuit_breakers()
    status = {}

    for name, cb in circuit_breakers.items():
        metrics = cb.get_metrics()
        status[name] = {
            "state": cb.state.value,
            "config": {
                "failure_threshold": cb.config.failure_threshold,
                "recovery_timeout": cb.config.recovery_timeout,
                "success_threshold": cb.config.success_threshold,
                "timeout": cb.config.timeout
            },
            "metrics": {
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": round(metrics.success_rate(), 3),
                "failure_rate": round(metrics.failure_rate(), 3),
                "circuit_open_count": metrics.circuit_open_count,
                "last_failure_time": metrics.last_failure_time.isoformat() if metrics.last_failure_time else None,
                "last_success_time": metrics.last_success_time.isoformat() if metrics.last_success_time else None
            }
        }

    return {
        "circuit_breakers": status,
        "summary": {
            "total": len(circuit_breakers),
            "closed": sum(1 for cb in circuit_breakers.values() if cb.state.value == "closed"),
            "open": sum(1 for cb in circuit_breakers.values() if cb.state.value == "open"),
            "half_open": sum(1 for cb in circuit_breakers.values() if cb.state.value == "half_open")
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/degradation")
async def degradation_status():
    """
    Get current system degradation status
    """
    from app.services.fallback_service import fallback_service
    from app.utils.degradation_handler import get_degradation_handler

    degradation_handler = get_degradation_handler()

    return {
        "current_status": fallback_service.get_degradation_status(),
        "handler_status": degradation_handler.get_status(),
        "recent_events": degradation_handler.get_recent_events(20),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/dlq")
async def dead_letter_queue_status():
    """
    Get dead letter queue status
    """
    from app.tasks.dead_letter_handler import dlq_handler
    from app.services.failed_message_processor import get_failed_message_processor

    processor = get_failed_message_processor()

    dlq_stats = await dlq_handler.get_stats()
    processing_stats = await processor.get_processing_stats()
    failure_analysis = await processor.analyze_failure_patterns()

    return {
        "dlq_stats": dlq_stats,
        "processing_stats": processing_stats,
        "failure_analysis": failure_analysis,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
