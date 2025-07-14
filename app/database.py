"""
Database configuration and session management for WhatsApp Hotel Bot
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import event, text
from typing import AsyncGenerator, Dict, Any, List
import logging
import time
import asyncio
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import get_logger
from app.core.database_logging import setup_database_logging
from app.core.database_security import setup_database_security_events
# Note: db_monitor imports are handled locally to avoid circular imports

logger = get_logger(__name__)

# Enhanced database engine configuration
def create_database_engine():
    """Create database engine with enhanced configuration"""
    try:
        if "postgresql" in settings.DATABASE_URL:
            # PostgreSQL configuration with connection pooling
            engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,  # Log SQL queries in debug mode
                poolclass=QueuePool,
                pool_size=10,  # Number of connections to maintain
                max_overflow=20,  # Additional connections beyond pool_size
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,   # Recycle connections every hour
                pool_timeout=30,  # Timeout for getting connection from pool
                connect_args={
                    "server_settings": {
                        "application_name": "whatsapp-hotel-bot",
                        "jit": "off",  # Disable JIT for better performance in some cases
                    },
                    "command_timeout": 60,
                }
            )
        elif "sqlite" in settings.DATABASE_URL:
            # SQLite configuration
            engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                poolclass=NullPool,
                connect_args={"check_same_thread": False}
            )
        else:
            raise ValueError(f"Unsupported database URL: {settings.DATABASE_URL}")

        logger.info(f"Database engine created successfully for: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'local'}")
        return engine

    except Exception as e:
        logger.warning(f"Failed to create async engine with configured URL, using SQLite fallback: {e}")
        # Fallback to SQLite for development/testing
        fallback_engine = create_async_engine(
            "sqlite+aiosqlite:///./hotel_bot.db",
            echo=settings.DEBUG,
            poolclass=NullPool,
            connect_args={"check_same_thread": False}
        )
        logger.info("Using SQLite fallback database")
        return fallback_engine

# Create the async engine
engine = create_database_engine()

# Set up database logging
setup_database_logging(engine.sync_engine, settings.DEBUG)

# Set up database security monitoring
setup_database_security_events(engine.sync_engine)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

# Create sync session factory for scripts and utilities
SyncSessionLocal = sessionmaker(
    bind=engine.sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Import Base from models to ensure consistency
from app.models.base import Base

# Enhanced database event listeners for monitoring and logging
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance and reliability"""
    if "sqlite" in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=1000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()
        logger.debug("SQLite pragmas configured")

@event.listens_for(engine.sync_engine, "connect")
def log_connection(dbapi_connection, connection_record):
    """Log database connections with enhanced details"""
    connection_info = {
        "event": "database_connection_established",
        "connection_id": id(dbapi_connection),
        "pool_size": getattr(engine.pool, 'size', lambda: None)(),
        "checked_out": getattr(engine.pool, 'checkedout', lambda: None)(),
    }
    logger.debug("Database connection established", extra=connection_info)

@event.listens_for(engine.sync_engine, "close")
def log_disconnection(dbapi_connection, connection_record):
    """Log database disconnections with enhanced details"""
    connection_info = {
        "event": "database_connection_closed",
        "connection_id": id(dbapi_connection),
        "pool_size": getattr(engine.pool, 'size', lambda: None)(),
        "checked_out": getattr(engine.pool, 'checkedout', lambda: None)(),
    }
    logger.debug("Database connection closed", extra=connection_info)

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def log_query_start(conn, cursor, statement, parameters, context, executemany):
    """Log query execution start for performance monitoring"""
    context._query_start_time = time.time()
    if settings.DEBUG:
        logger.debug(f"Executing query: {statement[:100]}...")

@event.listens_for(engine.sync_engine, "after_cursor_execute")
def log_query_end(conn, cursor, statement, parameters, context, executemany):
    """Log query execution end with timing"""
    if hasattr(context, '_query_start_time'):
        execution_time = (time.time() - context._query_start_time) * 1000

        # Record metrics in performance monitor
        try:
            from app.utils.db_monitor import performance_monitor
            performance_monitor.record_query(statement, execution_time)
        except ImportError:
            pass  # Skip if db_monitor not available

        if execution_time > 1000:  # Log slow queries (>1 second)
            logger.warning(f"Slow query detected: {execution_time:.2f}ms - {statement[:100]}...")
        elif settings.DEBUG:
            logger.debug(f"Query completed in {execution_time:.2f}ms")

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions with enhanced error handling

    Yields:
        AsyncSession: Database session
    """
    session_start_time = time.time()
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("Database session created")
            yield session
        except Exception as e:
            logger.error(f"Database session error: {str(e)}")
            await session.rollback()
            raise
        finally:
            session_duration = (time.time() - session_start_time) * 1000
            logger.debug(f"Database session closed after {session_duration:.2f}ms")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to get database session

    Yields:
        AsyncSession: Database session
    """
    async with get_db_session() as session:
        yield session


def get_sync_db_session() -> Session:
    """
    Get synchronous database session for scripts and utilities

    Returns:
        Session: Synchronous database session
    """
    return SyncSessionLocal()

async def init_db() -> None:
    """
    Initialize database tables

    This function creates all tables defined in the models.
    Should be called on application startup.
    """
    try:
        logger.info("Initializing database...")

        # Import all models to ensure they are registered with Base
        # Note: Import models here when they are created
        # from app.models import hotel, guest, message, conversation  # noqa: F401

        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

async def close_db() -> None:
    """
    Close database connections
    
    Should be called on application shutdown.
    """
    try:
        logger.info("Closing database connections...")
        await engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {str(e)}")
        raise

async def check_db_connection() -> bool:
    """
    Check if database connection is working

    Returns:
        bool: True if connection is working, False otherwise
    """
    try:
        async with get_db_session() as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {str(e)}")
        return False

async def get_connection_pool_stats() -> Dict[str, Any]:
    """
    Get connection pool statistics

    Returns:
        Dict[str, Any]: Pool statistics
    """
    try:
        pool = engine.pool
        return {
            "pool_size": getattr(pool, 'size', lambda: None)(),
            "checked_out": getattr(pool, 'checkedout', lambda: None)(),
            "overflow": getattr(pool, 'overflow', lambda: None)(),
            "checked_in": getattr(pool, 'checkedin', lambda: None)(),
        }
    except Exception as e:
        logger.error(f"Failed to get pool stats: {str(e)}")
        return {}

class DatabaseManager:
    """Database manager for handling connections and transactions"""
    
    def __init__(self):
        self.engine = engine
        self.session_factory = AsyncSessionLocal
    
    async def get_session(self) -> AsyncSession:
        """Get a new database session"""
        return self.session_factory()
    
    async def execute_in_transaction(self, func, *args, **kwargs):
        """
        Execute a function within a database transaction
        
        Args:
            func: Async function to execute
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function execution
        """
        async with self.session_factory() as session:
            try:
                async with session.begin():
                    result = await func(session, *args, **kwargs)
                    return result
            except Exception as e:
                logger.error(f"Transaction failed: {str(e)}")
                raise
    
    async def health_check(self) -> dict:
        """
        Perform comprehensive database health check

        Returns:
            dict: Health check results
        """
        try:
            async with get_db_session() as session:
                # Use the enhanced health checker
                try:
                    from app.utils.db_monitor import health_checker, performance_monitor
                    health_data = await health_checker.check_database_health(session)

                    # Add additional database manager specific info
                    pool_stats = await get_connection_pool_stats()
                    performance_metrics = performance_monitor.get_database_metrics()
                except ImportError:
                    # Fallback if db_monitor not available
                    health_data = {"status": "unknown", "checks": {}}
                    pool_stats = {}
                    performance_metrics = {}

                health_data.update({
                    "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "local",
                    "engine_echo": engine.echo,
                    "database_type": "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite",
                    "pool_stats": pool_stats,
                    "performance_metrics": performance_metrics
                })

                return health_data

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "local",
                "timestamp": time.time()
            }

# Global database manager instance
db_manager = DatabaseManager()

# Connection monitoring utilities
class ConnectionMonitor:
    """Monitor database connections and performance"""

    def __init__(self):
        self.query_count = 0
        self.slow_query_count = 0
        self.connection_count = 0
        self.error_count = 0

    def record_query(self, execution_time_ms: float):
        """Record query execution"""
        self.query_count += 1
        if execution_time_ms > 1000:
            self.slow_query_count += 1

    def record_connection(self):
        """Record new connection"""
        self.connection_count += 1

    def record_error(self):
        """Record database error"""
        self.error_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        return {
            "total_queries": self.query_count,
            "slow_queries": self.slow_query_count,
            "total_connections": self.connection_count,
            "total_errors": self.error_count,
            "slow_query_percentage": (self.slow_query_count / max(self.query_count, 1)) * 100
        }

# Global connection monitor
connection_monitor = ConnectionMonitor()

# Enhanced monitoring functions
async def get_database_performance_summary() -> Dict[str, Any]:
    """
    Get comprehensive database performance summary

    Returns:
        Dict[str, Any]: Performance summary
    """
    try:
        from app.utils.db_monitor import performance_monitor, connection_monitor

        # Record current connection metrics
        await performance_monitor.record_connection_metrics()

        # Get performance summary
        summary = performance_monitor.get_performance_summary()

        # Add connection monitor stats
        summary["connection_monitor_stats"] = connection_monitor.get_stats()

        return summary

    except Exception as e:
        logger.error(f"Failed to get performance summary: {str(e)}")
        return {"error": str(e)}

async def get_slow_queries_report(limit: int = 10) -> Dict[str, Any]:
    """
    Get slow queries report

    Args:
        limit: Number of slow queries to return

    Returns:
        Dict[str, Any]: Slow queries report
    """
    try:
        from app.utils.db_monitor import performance_monitor

        slow_queries = performance_monitor.get_slow_queries(limit)

        return {
            "slow_queries": slow_queries,
            "total_slow_queries": performance_monitor.slow_queries,
            "slow_query_threshold_ms": performance_monitor.slow_query_threshold,
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Failed to get slow queries report: {str(e)}")
        return {"error": str(e)}

async def reset_performance_metrics() -> Dict[str, Any]:
    """
    Reset all performance metrics

    Returns:
        Dict[str, Any]: Reset confirmation
    """
    try:
        from app.utils.db_monitor import performance_monitor, connection_monitor

        old_stats = performance_monitor.get_database_metrics()
        performance_monitor.reset_metrics()
        connection_monitor.__init__()  # Reset connection monitor

        return {
            "status": "success",
            "message": "Performance metrics reset",
            "previous_stats": old_stats,
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Failed to reset performance metrics: {str(e)}")
        return {"error": str(e)}

async def get_connection_pool_health() -> Dict[str, Any]:
    """
    Get detailed connection pool health information

    Returns:
        Dict[str, Any]: Connection pool health
    """
    try:
        pool_stats = await get_connection_pool_stats()

        if not pool_stats:
            return {"status": "unknown", "message": "Pool stats not available"}

        # Calculate health metrics
        total_connections = pool_stats.get('pool_size', 0) + pool_stats.get('overflow', 0)
        utilization = 0
        if total_connections > 0:
            utilization = (pool_stats.get('checked_out', 0) / total_connections) * 100

        # Determine health status
        status = "healthy"
        if utilization > 90:
            status = "critical"
        elif utilization > 75:
            status = "warning"

        return {
            "status": status,
            "utilization_percent": round(utilization, 2),
            "pool_stats": pool_stats,
            "recommendations": _get_pool_recommendations(utilization, pool_stats),
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Failed to get connection pool health: {str(e)}")
        return {"error": str(e)}

def _get_pool_recommendations(utilization: float, pool_stats: Dict[str, Any]) -> List[str]:
    """
    Get recommendations based on pool utilization

    Args:
        utilization: Pool utilization percentage
        pool_stats: Pool statistics

    Returns:
        List[str]: Recommendations
    """
    recommendations = []

    if utilization > 90:
        recommendations.append("Critical: Pool utilization is very high. Consider increasing pool size.")
    elif utilization > 75:
        recommendations.append("Warning: Pool utilization is high. Monitor for potential bottlenecks.")

    if pool_stats.get('overflow', 0) > 0:
        recommendations.append("Overflow connections are being used. Consider increasing base pool size.")

    if utilization < 10:
        recommendations.append("Pool utilization is very low. Consider reducing pool size to save resources.")

    return recommendations
