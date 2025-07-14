"""
Enhanced multi-level caching service for WhatsApp Hotel Bot
Provides memory + Redis caching with compression, warming, and intelligent invalidation
"""

import asyncio
import json
import gzip
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from collections import OrderedDict
from contextlib import asynccontextmanager
from enum import Enum

import redis.asyncio as redis
import structlog
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import track_cache_operation

logger = get_logger(__name__)

T = TypeVar('T')


class CacheLevel(Enum):
    """Cache level enumeration"""
    MEMORY = "memory"
    REDIS = "redis"
    BOTH = "both"


class CacheStrategy(Enum):
    """Cache strategy enumeration"""
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    WRITE_AROUND = "write_around"


@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    memory_usage_bytes: int = 0
    redis_usage_bytes: int = 0
    avg_get_time_ms: float = 0.0
    avg_set_time_ms: float = 0.0


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: Optional[int] = None
    access_count: int = 0
    size_bytes: int = 0
    compressed: bool = False
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.ttl_seconds is None:
            return False
        return (datetime.utcnow() - self.created_at).total_seconds() > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds"""
        return (datetime.utcnow() - self.created_at).total_seconds()


class LRUCache(Generic[T]):
    """Thread-safe LRU cache implementation"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[T]:
        """Get value from LRU cache"""
        async with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                if entry.is_expired:
                    del self.cache[key]
                    return None
                
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                entry.accessed_at = datetime.utcnow()
                entry.access_count += 1
                return entry.value
            return None
    
    async def set(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> None:
        """Set value in LRU cache"""
        async with self._lock:
            # Calculate size
            size_bytes = len(str(value).encode('utf-8'))
            
            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl_seconds,
                size_bytes=size_bytes
            )
            
            self.cache[key] = entry
            self.cache.move_to_end(key)
            
            # Evict oldest entries if over capacity
            while len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
    
    async def delete(self, key: str) -> bool:
        """Delete value from LRU cache"""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all entries from cache"""
        async with self._lock:
            self.cache.clear()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        async with self._lock:
            total_size = sum(entry.size_bytes for entry in self.cache.values())
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "memory_usage_bytes": total_size,
                "utilization_percent": (len(self.cache) / self.max_size) * 100
            }


class EnhancedCacheService:
    """Enhanced multi-level caching service"""
    
    def __init__(
        self,
        redis_url: str = None,
        memory_cache_size: int = 1000,
        default_ttl: int = 3600,
        compression_threshold: int = 1024,
        enable_compression: bool = True
    ):
        self.redis_url = redis_url or settings.REDIS_URL
        self.default_ttl = default_ttl
        self.compression_threshold = compression_threshold
        self.enable_compression = enable_compression
        self.logger = logger.bind(component="cache_service")
        
        # Initialize memory cache
        self.memory_cache = LRUCache[Any](memory_cache_size)
        
        # Initialize Redis client
        self.redis_client: Optional[redis.Redis] = None
        
        # Cache metrics
        self.metrics = CacheMetrics()
        
        # Cache warming configuration
        self.warming_functions: Dict[str, Callable] = {}
        self.warming_schedules: Dict[str, int] = {}  # key -> interval in seconds
        
        # Invalidation patterns
        self.invalidation_patterns: Dict[str, List[str]] = {}
    
    async def initialize(self):
        """Initialize the cache service"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # We handle encoding ourselves for compression
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test Redis connection
            await self.redis_client.ping()
            self.logger.info("Enhanced cache service initialized with Redis")
            
        except Exception as e:
            self.logger.error("Failed to initialize Redis for caching", error=str(e))
            self.redis_client = None
    
    async def get(
        self,
        key: str,
        level: CacheLevel = CacheLevel.BOTH,
        deserializer: Optional[Callable] = None
    ) -> Optional[Any]:
        """Get value from cache with multi-level support"""
        start_time = time.time()
        
        try:
            # Try memory cache first
            if level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
                value = await self.memory_cache.get(key)
                if value is not None:
                    self.metrics.hits += 1
                    track_cache_operation("get", "memory", True, (time.time() - start_time) * 1000)
                    return self._deserialize_value(value, deserializer)
            
            # Try Redis cache
            if level in [CacheLevel.REDIS, CacheLevel.BOTH] and self.redis_client:
                try:
                    cached_data = await self.redis_client.get(key)
                    if cached_data:
                        value = self._decompress_and_deserialize(cached_data, deserializer)
                        
                        # Store in memory cache for faster access
                        if level == CacheLevel.BOTH:
                            await self.memory_cache.set(key, value, self.default_ttl)
                        
                        self.metrics.hits += 1
                        track_cache_operation("get", "redis", True, (time.time() - start_time) * 1000)
                        return value
                        
                except Exception as e:
                    self.logger.warning("Redis cache get failed", key=key, error=str(e))
            
            # Cache miss
            self.metrics.misses += 1
            track_cache_operation("get", "miss", False, (time.time() - start_time) * 1000)
            return None
            
        except Exception as e:
            self.logger.error("Cache get operation failed", key=key, error=str(e))
            self.metrics.misses += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        level: CacheLevel = CacheLevel.BOTH,
        strategy: CacheStrategy = CacheStrategy.WRITE_THROUGH,
        serializer: Optional[Callable] = None
    ) -> bool:
        """Set value in cache with multi-level support"""
        start_time = time.time()
        ttl = ttl or self.default_ttl
        success = True
        
        try:
            serialized_value = self._serialize_value(value, serializer)
            
            # Set in memory cache
            if level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
                await self.memory_cache.set(key, serialized_value, ttl)
            
            # Set in Redis cache
            if level in [CacheLevel.REDIS, CacheLevel.BOTH] and self.redis_client:
                try:
                    compressed_data = self._compress_and_serialize(serialized_value)
                    await self.redis_client.setex(key, ttl, compressed_data)
                except Exception as e:
                    self.logger.warning("Redis cache set failed", key=key, error=str(e))
                    success = False
            
            if success:
                self.metrics.sets += 1
                track_cache_operation("set", "success", True, (time.time() - start_time) * 1000)
            
            return success
            
        except Exception as e:
            self.logger.error("Cache set operation failed", key=key, error=str(e))
            return False

    async def delete(self, key: str, level: CacheLevel = CacheLevel.BOTH) -> bool:
        """Delete value from cache"""
        success = True

        try:
            # Delete from memory cache
            if level in [CacheLevel.MEMORY, CacheLevel.BOTH]:
                await self.memory_cache.delete(key)

            # Delete from Redis cache
            if level in [CacheLevel.REDIS, CacheLevel.BOTH] and self.redis_client:
                try:
                    await self.redis_client.delete(key)
                except Exception as e:
                    self.logger.warning("Redis cache delete failed", key=key, error=str(e))
                    success = False

            if success:
                self.metrics.deletes += 1

            return success

        except Exception as e:
            self.logger.error("Cache delete operation failed", key=key, error=str(e))
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern"""
        invalidated_count = 0

        try:
            if self.redis_client:
                # Get all keys matching pattern
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                    invalidated_count = len(keys)

            # For memory cache, we need to iterate through keys
            # This is less efficient but necessary for pattern matching
            memory_stats = await self.memory_cache.get_stats()
            # Note: LRUCache doesn't expose keys directly, would need enhancement

            self.logger.info("Cache pattern invalidated",
                           pattern=pattern,
                           invalidated_count=invalidated_count)

            return invalidated_count

        except Exception as e:
            self.logger.error("Cache pattern invalidation failed", pattern=pattern, error=str(e))
            return 0

    def _serialize_value(self, value: Any, serializer: Optional[Callable] = None) -> bytes:
        """Serialize value for caching"""
        if serializer:
            return serializer(value)

        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value).encode('utf-8')
        elif isinstance(value, BaseModel):
            return value.model_dump_json().encode('utf-8')
        else:
            return json.dumps(value, default=str).encode('utf-8')

    def _deserialize_value(self, data: bytes, deserializer: Optional[Callable] = None) -> Any:
        """Deserialize value from cache"""
        if deserializer:
            return deserializer(data)

        try:
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return data

    def _compress_and_serialize(self, data: bytes) -> bytes:
        """Compress data if it exceeds threshold"""
        if self.enable_compression and len(data) > self.compression_threshold:
            return gzip.compress(data)
        return data

    def _decompress_and_deserialize(self, data: bytes, deserializer: Optional[Callable] = None) -> Any:
        """Decompress and deserialize data"""
        try:
            # Try to decompress first
            if data.startswith(b'\x1f\x8b'):  # gzip magic number
                data = gzip.decompress(data)
        except Exception:
            pass  # Not compressed or decompression failed

        return self._deserialize_value(data, deserializer)

    async def warm_cache(self, key: str, warm_func: Callable, ttl: Optional[int] = None) -> bool:
        """Warm cache with data from warming function"""
        try:
            value = await warm_func() if asyncio.iscoroutinefunction(warm_func) else warm_func()
            return await self.set(key, value, ttl)
        except Exception as e:
            self.logger.error("Cache warming failed", key=key, error=str(e))
            return False

    def register_warming_function(self, key_pattern: str, warm_func: Callable, interval_seconds: int):
        """Register a function for cache warming"""
        self.warming_functions[key_pattern] = warm_func
        self.warming_schedules[key_pattern] = interval_seconds

    def register_invalidation_pattern(self, trigger_key: str, invalidation_patterns: List[str]):
        """Register invalidation patterns for a trigger key"""
        self.invalidation_patterns[trigger_key] = invalidation_patterns

    async def trigger_invalidation(self, trigger_key: str) -> int:
        """Trigger invalidation based on registered patterns"""
        total_invalidated = 0

        if trigger_key in self.invalidation_patterns:
            for pattern in self.invalidation_patterns[trigger_key]:
                count = await self.invalidate_pattern(pattern)
                total_invalidated += count

        return total_invalidated

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        memory_stats = await self.memory_cache.get_stats()

        redis_stats = {}
        if self.redis_client:
            try:
                redis_info = await self.redis_client.info('memory')
                redis_stats = {
                    "used_memory": redis_info.get('used_memory', 0),
                    "used_memory_human": redis_info.get('used_memory_human', '0B'),
                    "maxmemory": redis_info.get('maxmemory', 0)
                }
            except Exception as e:
                self.logger.warning("Failed to get Redis stats", error=str(e))

        hit_rate = 0.0
        total_operations = self.metrics.hits + self.metrics.misses
        if total_operations > 0:
            hit_rate = (self.metrics.hits / total_operations) * 100

        return {
            "memory_cache": memory_stats,
            "redis_cache": redis_stats,
            "metrics": {
                "hits": self.metrics.hits,
                "misses": self.metrics.misses,
                "sets": self.metrics.sets,
                "deletes": self.metrics.deletes,
                "hit_rate_percent": hit_rate,
                "total_operations": total_operations
            },
            "warming_functions": len(self.warming_functions),
            "invalidation_patterns": len(self.invalidation_patterns)
        }

    async def close(self):
        """Close cache service and cleanup resources"""
        if self.redis_client:
            await self.redis_client.close()
        await self.memory_cache.clear()
        self.logger.info("Cache service closed")


# Global cache service instance
cache_service: Optional[EnhancedCacheService] = None


# Alias for backward compatibility
CacheService = EnhancedCacheService


async def get_cache_service() -> EnhancedCacheService:
    """Get the global cache service instance"""
    global cache_service
    if cache_service is None:
        cache_service = EnhancedCacheService()
        await cache_service.initialize()
    return cache_service
