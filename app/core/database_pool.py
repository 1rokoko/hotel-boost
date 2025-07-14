"""
Enhanced database connection pool management for WhatsApp Hotel Bot
Provides dynamic pool sizing, health monitoring, and performance optimization
"""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from collections import deque

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
import structlog

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PoolMetrics:
    """Connection pool metrics"""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    pool_size: int = 0
    checked_out: int = 0
    checked_in: int = 0
    overflow: int = 0
    utilization_percent: float = 0.0
    avg_checkout_time_ms: float = 0.0
    total_connections: int = 0
    failed_connections: int = 0
    connection_errors: int = 0


@dataclass
class ConnectionHealth:
    """Individual connection health status"""
    connection_id: str
    created_at: datetime
    last_used: datetime
    total_queries: int = 0
    failed_queries: int = 0
    avg_query_time_ms: float = 0.0
    is_healthy: bool = True
    error_count: int = 0


@dataclass
class PoolConfiguration:
    """Dynamic pool configuration"""
    min_pool_size: int = 5
    max_pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    
    # Dynamic scaling parameters
    scale_up_threshold: float = 0.8  # Scale up when utilization > 80%
    scale_down_threshold: float = 0.3  # Scale down when utilization < 30%
    scale_up_increment: int = 2
    scale_down_increment: int = 1
    min_stable_time: int = 300  # 5 minutes before scaling
    
    # Health check parameters
    health_check_interval: int = 60  # seconds
    max_connection_age: int = 7200  # 2 hours
    max_error_rate: float = 0.1  # 10% error rate threshold
    connection_timeout: int = 10  # seconds


class EnhancedConnectionPool:
    """Enhanced connection pool with dynamic sizing and health monitoring"""
    
    def __init__(self, database_url: str, config: Optional[PoolConfiguration] = None):
        self.database_url = database_url
        self.config = config or PoolConfiguration()
        self.logger = logger.bind(component="connection_pool")
        
        # Metrics tracking
        self.metrics_history: deque = deque(maxlen=1000)
        self.connection_health: Dict[str, ConnectionHealth] = {}
        self.checkout_times: deque = deque(maxlen=100)
        
        # Pool state
        self.current_pool_size = self.config.min_pool_size
        self.last_scale_time = datetime.utcnow()
        self.is_monitoring = False
        
        # Create the engine
        self.engine = self._create_engine()
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False
        )
        
        # Setup event listeners
        self._setup_event_listeners()
    
    def _create_engine(self):
        """Create database engine with dynamic configuration"""
        try:
            if "postgresql" in self.database_url:
                engine = create_async_engine(
                    self.database_url,
                    echo=settings.DEBUG,
                    poolclass=QueuePool,
                    pool_size=self.current_pool_size,
                    max_overflow=self.config.max_overflow,
                    pool_pre_ping=self.config.pool_pre_ping,
                    pool_recycle=self.config.pool_recycle,
                    pool_timeout=self.config.pool_timeout,
                    connect_args={
                        "server_settings": {
                            "application_name": "whatsapp-hotel-bot-enhanced",
                            "jit": "off",
                        },
                        "command_timeout": self.config.connection_timeout,
                    }
                )
            elif "sqlite" in self.database_url:
                engine = create_async_engine(
                    self.database_url,
                    echo=settings.DEBUG,
                    poolclass=NullPool,
                    connect_args={"check_same_thread": False}
                )
            else:
                raise ValueError(f"Unsupported database URL: {self.database_url}")
            
            self.logger.info("Enhanced database engine created", 
                           pool_size=self.current_pool_size,
                           max_overflow=self.config.max_overflow)
            return engine
            
        except Exception as e:
            self.logger.error("Failed to create enhanced database engine", error=str(e))
            raise
    
    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for monitoring"""
        
        @event.listens_for(self.engine.sync_engine, "connect")
        def on_connect(dbapi_connection, connection_record):
            """Track new connections"""
            connection_id = str(id(dbapi_connection))
            self.connection_health[connection_id] = ConnectionHealth(
                connection_id=connection_id,
                created_at=datetime.utcnow(),
                last_used=datetime.utcnow()
            )
            self.logger.debug("New database connection created", connection_id=connection_id)
        
        @event.listens_for(self.engine.sync_engine, "checkout")
        def on_checkout(dbapi_connection, connection_record, connection_proxy):
            """Track connection checkouts"""
            connection_id = str(id(dbapi_connection))
            checkout_time = time.time()
            connection_record.info['checkout_time'] = checkout_time
            
            if connection_id in self.connection_health:
                self.connection_health[connection_id].last_used = datetime.utcnow()
        
        @event.listens_for(self.engine.sync_engine, "checkin")
        def on_checkin(dbapi_connection, connection_record):
            """Track connection checkins and calculate checkout duration"""
            if 'checkout_time' in connection_record.info:
                checkout_duration = (time.time() - connection_record.info['checkout_time']) * 1000
                self.checkout_times.append(checkout_duration)
                del connection_record.info['checkout_time']

        @event.listens_for(self.engine.sync_engine, "close")
        def on_close(dbapi_connection, connection_record):
            """Track connection closures"""
            connection_id = str(id(dbapi_connection))
            if connection_id in self.connection_health:
                del self.connection_health[connection_id]
            self.logger.debug("Database connection closed", connection_id=connection_id)

    async def get_session(self) -> AsyncSession:
        """Get a database session from the pool"""
        return self.session_factory()

    @asynccontextmanager
    async def get_session_context(self):
        """Context manager for database sessions with automatic cleanup"""
        session_start_time = time.time()
        async with self.session_factory() as session:
            try:
                yield session
            except Exception as e:
                self.logger.error("Database session error", error=str(e))
                await session.rollback()
                raise
            finally:
                session_duration = (time.time() - session_start_time) * 1000
                self.logger.debug("Database session completed", duration_ms=session_duration)

    async def get_pool_metrics(self) -> PoolMetrics:
        """Get current pool metrics"""
        try:
            pool = self.engine.pool

            # Get basic pool stats
            pool_size = getattr(pool, 'size', lambda: 0)()
            checked_out = getattr(pool, 'checkedout', lambda: 0)()
            checked_in = getattr(pool, 'checkedin', lambda: 0)()
            overflow = getattr(pool, 'overflow', lambda: 0)()

            # Calculate utilization
            total_available = pool_size + overflow
            utilization = (checked_out / max(total_available, 1)) * 100

            # Calculate average checkout time
            avg_checkout_time = 0.0
            if self.checkout_times:
                avg_checkout_time = statistics.mean(self.checkout_times)

            # Count connection errors
            connection_errors = sum(
                1 for health in self.connection_health.values()
                if not health.is_healthy
            )

            metrics = PoolMetrics(
                pool_size=pool_size,
                checked_out=checked_out,
                checked_in=checked_in,
                overflow=overflow,
                utilization_percent=utilization,
                avg_checkout_time_ms=avg_checkout_time,
                total_connections=len(self.connection_health),
                connection_errors=connection_errors
            )

            # Store in history
            self.metrics_history.append(metrics)

            return metrics

        except Exception as e:
            self.logger.error("Failed to get pool metrics", error=str(e))
            return PoolMetrics()

    async def check_connection_health(self) -> Dict[str, Any]:
        """Check health of all connections"""
        healthy_connections = 0
        unhealthy_connections = 0
        old_connections = 0

        current_time = datetime.utcnow()

        for connection_id, health in self.connection_health.items():
            # Check connection age
            age_seconds = (current_time - health.created_at).total_seconds()
            if age_seconds > self.config.max_connection_age:
                old_connections += 1
                health.is_healthy = False

            # Check error rate
            if health.total_queries > 0:
                error_rate = health.failed_queries / health.total_queries
                if error_rate > self.config.max_error_rate:
                    health.is_healthy = False

            if health.is_healthy:
                healthy_connections += 1
            else:
                unhealthy_connections += 1

        return {
            "healthy_connections": healthy_connections,
            "unhealthy_connections": unhealthy_connections,
            "old_connections": old_connections,
            "total_connections": len(self.connection_health),
            "health_percentage": (healthy_connections / max(len(self.connection_health), 1)) * 100
        }

    async def should_scale_pool(self) -> Tuple[bool, str, int]:
        """Determine if pool should be scaled and by how much"""
        metrics = await self.get_pool_metrics()
        current_time = datetime.utcnow()

        # Check if enough time has passed since last scaling
        time_since_scale = (current_time - self.last_scale_time).total_seconds()
        if time_since_scale < self.config.min_stable_time:
            return False, "too_soon", 0

        # Check if we should scale up
        if metrics.utilization_percent > self.config.scale_up_threshold * 100:
            if self.current_pool_size < self.config.max_pool_size:
                new_size = min(
                    self.current_pool_size + self.config.scale_up_increment,
                    self.config.max_pool_size
                )
                return True, "scale_up", new_size

        # Check if we should scale down
        elif metrics.utilization_percent < self.config.scale_down_threshold * 100:
            if self.current_pool_size > self.config.min_pool_size:
                new_size = max(
                    self.current_pool_size - self.config.scale_down_increment,
                    self.config.min_pool_size
                )
                return True, "scale_down", new_size

        return False, "no_change", self.current_pool_size

    async def scale_pool(self, new_size: int, reason: str) -> bool:
        """Scale the connection pool to a new size"""
        try:
            old_size = self.current_pool_size

            # Note: SQLAlchemy doesn't support dynamic pool resizing
            # This would require recreating the engine in a production implementation
            # For now, we'll log the scaling decision and update our tracking

            self.current_pool_size = new_size
            self.last_scale_time = datetime.utcnow()

            self.logger.info("Pool scaling decision made",
                           old_size=old_size,
                           new_size=new_size,
                           reason=reason)

            # In a production implementation, you would:
            # 1. Create a new engine with the new pool size
            # 2. Gradually migrate connections
            # 3. Close the old engine

            return True

        except Exception as e:
            self.logger.error("Failed to scale pool", error=str(e))
            return False

    async def start_monitoring(self, interval: int = None):
        """Start background monitoring of the connection pool"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        interval = interval or self.config.health_check_interval

        self.logger.info("Starting connection pool monitoring", interval=interval)

        async def monitor_loop():
            while self.is_monitoring:
                try:
                    # Collect metrics
                    metrics = await self.get_pool_metrics()
                    health = await self.check_connection_health()

                    # Check if scaling is needed
                    should_scale, reason, new_size = await self.should_scale_pool()
                    if should_scale:
                        await self.scale_pool(new_size, reason)

                    # Log health status
                    self.logger.debug("Pool health check",
                                    utilization=metrics.utilization_percent,
                                    healthy_connections=health["healthy_connections"],
                                    total_connections=health["total_connections"])

                    # Clean up old connection health records
                    await self._cleanup_old_health_records()

                except Exception as e:
                    self.logger.error("Error in pool monitoring", error=str(e))

                await asyncio.sleep(interval)

        # Start monitoring task
        asyncio.create_task(monitor_loop())

    async def stop_monitoring(self):
        """Stop background monitoring"""
        self.is_monitoring = False
        self.logger.info("Stopped connection pool monitoring")

    async def _cleanup_old_health_records(self):
        """Clean up old connection health records"""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=1)  # Keep records for 1 hour

        to_remove = [
            conn_id for conn_id, health in self.connection_health.items()
            if health.last_used < cutoff_time
        ]

        for conn_id in to_remove:
            del self.connection_health[conn_id]

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        metrics = await self.get_pool_metrics()
        health = await self.check_connection_health()

        # Calculate performance statistics
        recent_metrics = list(self.metrics_history)[-10:]  # Last 10 metrics
        avg_utilization = 0.0
        if recent_metrics:
            avg_utilization = statistics.mean(m.utilization_percent for m in recent_metrics)

        avg_checkout_time = 0.0
        if self.checkout_times:
            avg_checkout_time = statistics.mean(self.checkout_times)

        return {
            "current_metrics": {
                "pool_size": metrics.pool_size,
                "utilization_percent": metrics.utilization_percent,
                "checked_out": metrics.checked_out,
                "overflow": metrics.overflow,
                "avg_checkout_time_ms": avg_checkout_time
            },
            "health_status": health,
            "performance": {
                "avg_utilization_percent": avg_utilization,
                "avg_checkout_time_ms": avg_checkout_time,
                "total_metrics_collected": len(self.metrics_history)
            },
            "configuration": {
                "min_pool_size": self.config.min_pool_size,
                "max_pool_size": self.config.max_pool_size,
                "max_overflow": self.config.max_overflow,
                "scale_up_threshold": self.config.scale_up_threshold,
                "scale_down_threshold": self.config.scale_down_threshold
            }
        }

    async def close(self):
        """Close the connection pool and cleanup resources"""
        await self.stop_monitoring()
        await self.engine.dispose()
        self.logger.info("Connection pool closed")


# Global enhanced pool instance
enhanced_pool: Optional[EnhancedConnectionPool] = None


def get_enhanced_pool() -> EnhancedConnectionPool:
    """Get the global enhanced connection pool instance"""
    global enhanced_pool
    if enhanced_pool is None:
        enhanced_pool = EnhancedConnectionPool(settings.DATABASE_URL)
    return enhanced_pool


async def initialize_enhanced_pool(config: Optional[PoolConfiguration] = None):
    """Initialize the enhanced connection pool"""
    global enhanced_pool
    enhanced_pool = EnhancedConnectionPool(settings.DATABASE_URL, config)
    await enhanced_pool.start_monitoring()
    return enhanced_pool
