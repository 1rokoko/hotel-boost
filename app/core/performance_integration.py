"""
Performance optimization integration module
Integrates all performance optimizations with existing codebase
"""

import asyncio
from typing import Optional

import structlog
from app.core.config import settings
from app.core.logging import get_logger

# Import existing components
from app.database import get_db_session, DatabaseManager

# Import new optimization components
from app.core.database_pool import initialize_enhanced_pool, get_enhanced_pool
from app.services.cache_service import get_cache_service
from app.utils.memory_optimizer import initialize_memory_optimization
from app.utils.async_optimizer import get_async_optimizer
from app.monitoring.performance_dashboard import start_performance_monitoring

logger = get_logger(__name__)


class PerformanceIntegrationManager:
    """Manages integration of performance optimizations with existing system"""
    
    def __init__(self):
        self.logger = logger.bind(component="performance_integration")
        self.initialized = False
        
    async def initialize_all_optimizations(self):
        """Initialize all performance optimizations"""
        if self.initialized:
            self.logger.warning("Performance optimizations already initialized")
            return
        
        try:
            self.logger.info("Starting performance optimization initialization")
            
            # 1. Initialize enhanced database connection pool
            await self._initialize_database_optimizations()
            
            # 2. Initialize enhanced caching
            await self._initialize_cache_optimizations()
            
            # 3. Initialize memory optimization
            await self._initialize_memory_optimizations()
            
            # 4. Initialize async processing optimization
            await self._initialize_async_optimizations()
            
            # 5. Start performance monitoring
            await self._initialize_performance_monitoring()
            
            self.initialized = True
            self.logger.info("All performance optimizations initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize performance optimizations", error=str(e))
            raise
    
    async def _initialize_database_optimizations(self):
        """Initialize database performance optimizations"""
        try:
            # Initialize enhanced connection pool
            enhanced_pool = await initialize_enhanced_pool()
            
            # Start pool monitoring
            await enhanced_pool.start_monitoring()
            
            self.logger.info("Database optimizations initialized",
                           pool_size=enhanced_pool.current_pool_size,
                           max_overflow=enhanced_pool.config.max_overflow)
            
        except Exception as e:
            self.logger.error("Failed to initialize database optimizations", error=str(e))
            raise
    
    async def _initialize_cache_optimizations(self):
        """Initialize cache performance optimizations"""
        try:
            # Initialize enhanced cache service
            cache_service = await get_cache_service()
            
            # Setup cache warming for common data patterns
            await self._setup_cache_warming(cache_service)
            
            self.logger.info("Cache optimizations initialized")
            
        except Exception as e:
            self.logger.error("Failed to initialize cache optimizations", error=str(e))
            raise
    
    async def _setup_cache_warming(self, cache_service):
        """Setup cache warming for common data patterns"""
        try:
            # Register warming functions for frequently accessed data
            
            # Hotel settings warming
            async def warm_hotel_settings():
                # This would typically load active hotel settings
                # For now, we'll just log the warming attempt
                self.logger.debug("Warming hotel settings cache")
                return {"warmed": True}
            
            cache_service.register_warming_function(
                "hotel:*:settings",
                warm_hotel_settings,
                interval_seconds=1800  # 30 minutes
            )
            
            # Active conversations warming
            async def warm_active_conversations():
                self.logger.debug("Warming active conversations cache")
                return {"warmed": True}
            
            cache_service.register_warming_function(
                "hotel:*:active_conversations",
                warm_active_conversations,
                interval_seconds=300  # 5 minutes
            )
            
            self.logger.info("Cache warming configured")
            
        except Exception as e:
            self.logger.error("Failed to setup cache warming", error=str(e))
    
    async def _initialize_memory_optimizations(self):
        """Initialize memory performance optimizations"""
        try:
            # Initialize memory optimization components
            initialize_memory_optimization()
            
            self.logger.info("Memory optimizations initialized")
            
        except Exception as e:
            self.logger.error("Failed to initialize memory optimizations", error=str(e))
            raise
    
    async def _initialize_async_optimizations(self):
        """Initialize async processing optimizations"""
        try:
            # Get async optimizer (initializes automatically)
            async_optimizer = get_async_optimizer()
            
            self.logger.info("Async processing optimizations initialized",
                           max_concurrent_tasks=async_optimizer.limits.max_concurrent_tasks)
            
        except Exception as e:
            self.logger.error("Failed to initialize async optimizations", error=str(e))
            raise
    
    async def _initialize_performance_monitoring(self):
        """Initialize performance monitoring"""
        try:
            # Start performance monitoring with 60-second intervals
            await start_performance_monitoring(interval_seconds=60)
            
            self.logger.info("Performance monitoring initialized")
            
        except Exception as e:
            self.logger.error("Failed to initialize performance monitoring", error=str(e))
            raise
    
    async def get_optimization_status(self) -> dict:
        """Get status of all performance optimizations"""
        status = {
            "initialized": self.initialized,
            "components": {}
        }
        
        try:
            # Database pool status
            if self.initialized:
                enhanced_pool = get_enhanced_pool()
                pool_metrics = await enhanced_pool.get_pool_metrics()
                status["components"]["database_pool"] = {
                    "status": "active",
                    "utilization_percent": pool_metrics.utilization_percent,
                    "pool_size": pool_metrics.pool_size,
                    "checked_out": pool_metrics.checked_out
                }
            
            # Cache service status
            if self.initialized:
                cache_service = await get_cache_service()
                cache_stats = await cache_service.get_cache_stats()
                status["components"]["cache_service"] = {
                    "status": "active",
                    "hit_rate_percent": cache_stats.get("metrics", {}).get("hit_rate_percent", 0),
                    "total_operations": cache_stats.get("metrics", {}).get("total_operations", 0)
                }
            
            # Memory optimization status
            if self.initialized:
                from app.utils.memory_optimizer import get_memory_profiler
                profiler = get_memory_profiler()
                memory_report = profiler.get_memory_report()
                current_snapshot = memory_report.get("current_snapshot", {})
                status["components"]["memory_optimization"] = {
                    "status": "active",
                    "memory_mb": current_snapshot.get("process_memory_mb", 0),
                    "memory_percent": current_snapshot.get("memory_percent", 0)
                }
            
            # Async optimization status
            if self.initialized:
                async_optimizer = get_async_optimizer()
                async_stats = async_optimizer.task_pool.get_performance_stats()
                status["components"]["async_optimization"] = {
                    "status": "active",
                    "active_tasks": async_stats.get("active_tasks", 0),
                    "completed_tasks": async_stats.get("completed_tasks", 0)
                }
            
        except Exception as e:
            self.logger.error("Failed to get optimization status", error=str(e))
            status["error"] = str(e)
        
        return status
    
    async def cleanup_optimizations(self):
        """Cleanup all performance optimizations"""
        try:
            self.logger.info("Cleaning up performance optimizations")
            
            # Stop enhanced pool monitoring
            if self.initialized:
                enhanced_pool = get_enhanced_pool()
                await enhanced_pool.stop_monitoring()
                await enhanced_pool.close()
            
            # Close cache service
            if self.initialized:
                cache_service = await get_cache_service()
                await cache_service.close()
            
            # Stop memory monitoring
            if self.initialized:
                from app.utils.memory_optimizer import get_memory_profiler
                profiler = get_memory_profiler()
                profiler.stop_monitoring()
            
            # Cleanup async optimizer
            if self.initialized:
                async_optimizer = get_async_optimizer()
                await async_optimizer.task_pool.cleanup()
            
            self.initialized = False
            self.logger.info("Performance optimizations cleaned up")
            
        except Exception as e:
            self.logger.error("Failed to cleanup performance optimizations", error=str(e))


# Global integration manager
performance_integration_manager: Optional[PerformanceIntegrationManager] = None


def get_performance_integration_manager() -> PerformanceIntegrationManager:
    """Get the global performance integration manager"""
    global performance_integration_manager
    if performance_integration_manager is None:
        performance_integration_manager = PerformanceIntegrationManager()
    return performance_integration_manager


async def initialize_performance_optimizations():
    """Initialize all performance optimizations"""
    manager = get_performance_integration_manager()
    await manager.initialize_all_optimizations()


async def cleanup_performance_optimizations():
    """Cleanup all performance optimizations"""
    manager = get_performance_integration_manager()
    await manager.cleanup_optimizations()


async def get_performance_status():
    """Get performance optimization status"""
    manager = get_performance_integration_manager()
    return await manager.get_optimization_status()


# Integration with existing database.py
async def get_optimized_db_session():
    """Get database session using enhanced connection pool"""
    try:
        enhanced_pool = get_enhanced_pool()
        return await enhanced_pool.get_session()
    except Exception:
        # Fallback to original implementation
        return get_db_session()


# Integration with existing cache
async def get_optimized_cache():
    """Get optimized cache service"""
    try:
        return await get_cache_service()
    except Exception as e:
        logger.error("Failed to get optimized cache, using fallback", error=str(e))
        # Return None to indicate cache unavailable
        return None
