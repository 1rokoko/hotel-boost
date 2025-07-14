"""
Cache decorators for easy integration with the enhanced caching system
Provides function-level caching with automatic key generation and invalidation
"""

import asyncio
import functools
import hashlib
import inspect
from typing import Any, Callable, Optional, Union, Dict, List
from datetime import datetime, timedelta

import structlog
from pydantic import BaseModel

from app.services.cache_service import get_cache_service, CacheLevel, CacheStrategy
from app.core.logging import get_logger

logger = get_logger(__name__)


def cache_key_generator(func: Callable, *args, **kwargs) -> str:
    """Generate cache key from function name and arguments"""
    # Get function module and name
    module = func.__module__
    name = func.__name__
    
    # Create a hash of the arguments
    arg_str = ""
    
    # Handle positional arguments
    if args:
        arg_str += str(args)
    
    # Handle keyword arguments (sorted for consistency)
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        arg_str += str(sorted_kwargs)
    
    # Create hash of arguments
    arg_hash = hashlib.md5(arg_str.encode()).hexdigest()[:16]
    
    return f"cache:{module}:{name}:{arg_hash}"


def cached(
    ttl: int = 3600,
    level: CacheLevel = CacheLevel.BOTH,
    strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
    key_generator: Optional[Callable] = None,
    invalidate_on: Optional[List[str]] = None,
    warm_on_miss: bool = False,
    serialize_result: bool = True
):
    """
    Decorator for caching function results
    
    Args:
        ttl: Time to live in seconds
        level: Cache level (memory, redis, or both)
        strategy: Cache strategy
        key_generator: Custom key generation function
        invalidate_on: List of events that should invalidate this cache
        warm_on_miss: Whether to warm cache on miss
        serialize_result: Whether to serialize the result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_service = await get_cache_service()
            
            # Generate cache key
            if key_generator:
                cache_key = key_generator(func, *args, **kwargs)
            else:
                cache_key = cache_key_generator(func, *args, **kwargs)
            
            # Try to get from cache
            cached_result = await cache_service.get(cache_key, level)
            if cached_result is not None:
                logger.debug("Cache hit", function=func.__name__, key=cache_key)
                return cached_result
            
            # Cache miss - execute function
            logger.debug("Cache miss", function=func.__name__, key=cache_key)
            result = await func(*args, **kwargs)
            
            # Store result in cache
            await cache_service.set(
                cache_key,
                result,
                ttl=ttl,
                level=level,
                strategy=strategy
            )
            
            # Register invalidation patterns if specified
            if invalidate_on:
                for pattern in invalidate_on:
                    cache_service.register_invalidation_pattern(pattern, [cache_key])
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we need to run in event loop
            try:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(async_wrapper(*args, **kwargs))
            except RuntimeError:
                # No event loop running, create one
                return asyncio.run(async_wrapper(*args, **kwargs))
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def cache_invalidate(*patterns: str):
    """
    Decorator for functions that should invalidate cache patterns
    
    Args:
        patterns: Cache key patterns to invalidate
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Invalidate cache patterns after successful execution
            cache_service = await get_cache_service()
            for pattern in patterns:
                await cache_service.invalidate_pattern(pattern)
                logger.debug("Cache invalidated", pattern=pattern, function=func.__name__)
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Invalidate cache patterns after successful execution
            async def invalidate():
                cache_service = await get_cache_service()
                for pattern in patterns:
                    await cache_service.invalidate_pattern(pattern)
                    logger.debug("Cache invalidated", pattern=pattern, function=func.__name__)
            
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(invalidate())
            except RuntimeError:
                asyncio.run(invalidate())
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def cache_warm(
    key_pattern: str,
    interval_seconds: int = 3600,
    ttl: Optional[int] = None
):
    """
    Decorator for functions that should be used for cache warming
    
    Args:
        key_pattern: Pattern for cache keys to warm
        interval_seconds: How often to warm the cache
        ttl: TTL for warmed cache entries
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_service = await get_cache_service()
            
            # Register this function for cache warming
            cache_service.register_warming_function(
                key_pattern,
                lambda: func(*args, **kwargs),
                interval_seconds
            )
            
            # Execute the function normally
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


class CacheManager:
    """High-level cache manager for common caching patterns"""
    
    def __init__(self):
        self.logger = logger.bind(component="cache_manager")
    
    async def cache_hotel_data(self, hotel_id: str, data: Any, ttl: int = 3600) -> bool:
        """Cache hotel-specific data"""
        cache_service = await get_cache_service()
        key = f"hotel:{hotel_id}:data"
        return await cache_service.set(key, data, ttl=ttl)
    
    async def get_hotel_data(self, hotel_id: str) -> Optional[Any]:
        """Get cached hotel data"""
        cache_service = await get_cache_service()
        key = f"hotel:{hotel_id}:data"
        return await cache_service.get(key)
    
    async def cache_guest_conversations(self, hotel_id: str, guest_id: str, conversations: List[Any], ttl: int = 1800) -> bool:
        """Cache guest conversations"""
        cache_service = await get_cache_service()
        key = f"hotel:{hotel_id}:guest:{guest_id}:conversations"
        return await cache_service.set(key, conversations, ttl=ttl)
    
    async def get_guest_conversations(self, hotel_id: str, guest_id: str) -> Optional[List[Any]]:
        """Get cached guest conversations"""
        cache_service = await get_cache_service()
        key = f"hotel:{hotel_id}:guest:{guest_id}:conversations"
        return await cache_service.get(key)
    
    async def cache_sentiment_analysis(self, message_id: str, analysis: Any, ttl: int = 7200) -> bool:
        """Cache sentiment analysis results"""
        cache_service = await get_cache_service()
        key = f"sentiment:message:{message_id}"
        return await cache_service.set(key, analysis, ttl=ttl)
    
    async def get_sentiment_analysis(self, message_id: str) -> Optional[Any]:
        """Get cached sentiment analysis"""
        cache_service = await get_cache_service()
        key = f"sentiment:message:{message_id}"
        return await cache_service.get(key)
    
    async def cache_trigger_results(self, hotel_id: str, trigger_id: str, results: Any, ttl: int = 3600) -> bool:
        """Cache trigger execution results"""
        cache_service = await get_cache_service()
        key = f"hotel:{hotel_id}:trigger:{trigger_id}:results"
        return await cache_service.set(key, results, ttl=ttl)
    
    async def invalidate_hotel_cache(self, hotel_id: str) -> int:
        """Invalidate all cache entries for a hotel"""
        cache_service = await get_cache_service()
        pattern = f"hotel:{hotel_id}:*"
        return await cache_service.invalidate_pattern(pattern)
    
    async def invalidate_guest_cache(self, hotel_id: str, guest_id: str) -> int:
        """Invalidate all cache entries for a guest"""
        cache_service = await get_cache_service()
        pattern = f"hotel:{hotel_id}:guest:{guest_id}:*"
        return await cache_service.invalidate_pattern(pattern)
    
    async def warm_common_caches(self, hotel_id: str):
        """Warm commonly accessed caches for a hotel"""
        cache_service = await get_cache_service()
        
        # This would typically call functions that load commonly accessed data
        # For example:
        # - Recent conversations
        # - Active triggers
        # - Hotel settings
        # - Guest preferences
        
        self.logger.info("Cache warming initiated", hotel_id=hotel_id)
    
    async def setup_cache_warming_schedule(self):
        """Setup automatic cache warming schedules"""
        cache_service = await get_cache_service()
        
        # Register warming functions for common data patterns
        cache_service.register_warming_function(
            "hotel:*:active_conversations",
            self._warm_active_conversations,
            interval_seconds=300  # Every 5 minutes
        )
        
        cache_service.register_warming_function(
            "hotel:*:triggers",
            self._warm_hotel_triggers,
            interval_seconds=600  # Every 10 minutes
        )
    
    async def _warm_active_conversations(self):
        """Warm cache with active conversations"""
        # Implementation would load active conversations
        pass
    
    async def _warm_hotel_triggers(self):
        """Warm cache with hotel triggers"""
        # Implementation would load hotel triggers
        pass


# Global cache manager instance
cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance"""
    return cache_manager
