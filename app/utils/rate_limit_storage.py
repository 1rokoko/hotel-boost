"""
Rate limit storage utilities for distributed rate limiting

This module provides Redis-based storage for rate limiting with support for
sliding window algorithms, token buckets, and distributed rate limiting.
"""

import time
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import redis.asyncio as redis
import structlog

from app.core.config import settings
from app.core.rate_limit_config import RateLimitAlgorithm, RateLimitRule

logger = structlog.get_logger(__name__)


class RateLimitStorageError(Exception):
    """Exception raised when rate limit storage operations fail"""
    pass


class RateLimitStorage(ABC):
    """Abstract base class for rate limit storage backends"""
    
    @abstractmethod
    async def check_rate_limit(
        self,
        key: str,
        rule: RateLimitRule,
        current_time: Optional[float] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit
        
        Args:
            key: Rate limit key
            rule: Rate limit rule
            current_time: Current timestamp (uses time.time() if None)
            
        Returns:
            Tuple of (allowed, metadata)
        """
        pass
    
    @abstractmethod
    async def increment_counter(
        self,
        key: str,
        rule: RateLimitRule,
        current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Increment rate limit counter
        
        Args:
            key: Rate limit key
            rule: Rate limit rule
            current_time: Current timestamp
            
        Returns:
            Dict with counter metadata
        """
        pass
    
    @abstractmethod
    async def get_stats(self, key: str) -> Dict[str, Any]:
        """Get rate limit statistics for key"""
        pass
    
    @abstractmethod
    async def reset_counter(self, key: str) -> bool:
        """Reset rate limit counter for key"""
        pass


class RedisRateLimitStorage(RateLimitStorage):
    """Redis-based rate limit storage with sliding window support"""
    
    def __init__(self, redis_url: Optional[str] = None, key_prefix: str = "rate_limit:"):
        self.redis_url = redis_url or settings.REDIS_URL
        self.key_prefix = key_prefix
        self.redis_client: Optional[redis.Redis] = None
        self._connection_lock = asyncio.Lock()
    
    async def _get_redis_client(self) -> redis.Redis:
        """Get or create Redis client"""
        if self.redis_client is None:
            async with self._connection_lock:
                if self.redis_client is None:
                    try:
                        self.redis_client = redis.from_url(
                            self.redis_url,
                            decode_responses=True,
                            socket_timeout=5,
                            socket_connect_timeout=5,
                            retry_on_timeout=True,
                            health_check_interval=30
                        )
                        # Test connection
                        await self.redis_client.ping()
                        logger.info("Redis connection established for rate limiting")
                    except Exception as e:
                        logger.error("Failed to connect to Redis for rate limiting", error=str(e))
                        raise RateLimitStorageError(f"Redis connection failed: {str(e)}")
        
        return self.redis_client
    
    def _get_key(self, key: str, window_type: str = "") -> str:
        """Generate Redis key with prefix"""
        if window_type:
            return f"{self.key_prefix}{key}:{window_type}"
        return f"{self.key_prefix}{key}"
    
    async def check_rate_limit(
        self,
        key: str,
        rule: RateLimitRule,
        current_time: Optional[float] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit using sliding window algorithm
        
        Args:
            key: Rate limit key
            rule: Rate limit rule
            current_time: Current timestamp
            
        Returns:
            Tuple of (allowed, metadata)
        """
        if current_time is None:
            current_time = time.time()
        
        try:
            client = await self._get_redis_client()
            
            # Check different time windows
            checks = []
            
            if rule.requests_per_second:
                allowed, meta = await self._check_sliding_window(
                    client, key, rule.requests_per_second, 1, current_time, "second"
                )
                checks.append(("second", allowed, meta))
            
            if rule.requests_per_minute:
                allowed, meta = await self._check_sliding_window(
                    client, key, rule.requests_per_minute, 60, current_time, "minute"
                )
                checks.append(("minute", allowed, meta))
            
            if rule.requests_per_hour:
                allowed, meta = await self._check_sliding_window(
                    client, key, rule.requests_per_hour, 3600, current_time, "hour"
                )
                checks.append(("hour", allowed, meta))
            
            if rule.requests_per_day:
                allowed, meta = await self._check_sliding_window(
                    client, key, rule.requests_per_day, 86400, current_time, "day"
                )
                checks.append(("day", allowed, meta))
            
            # Check burst limit
            burst_allowed = True
            burst_meta = {}
            if rule.burst_limit:
                burst_allowed, burst_meta = await self._check_sliding_window(
                    client, key, rule.burst_limit, rule.burst_window_seconds, current_time, "burst"
                )
                checks.append(("burst", burst_allowed, burst_meta))
            
            # Overall result - all checks must pass
            overall_allowed = all(allowed for _, allowed, _ in checks)
            
            # Compile metadata
            metadata = {
                "timestamp": current_time,
                "rule_name": rule.name,
                "checks": {window: meta for window, allowed, meta in checks},
                "overall_allowed": overall_allowed
            }
            
            return overall_allowed, metadata
            
        except Exception as e:
            logger.error("Rate limit check failed", key=key, error=str(e))
            # In case of error, allow request but log warning
            return True, {"error": str(e), "fallback": True}
    
    async def _check_sliding_window(
        self,
        client: redis.Redis,
        key: str,
        limit: int,
        window_seconds: int,
        current_time: float,
        window_type: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check sliding window rate limit"""
        redis_key = self._get_key(key, window_type)
        window_start = current_time - window_seconds
        
        # Use Redis pipeline for atomic operations
        pipe = client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(redis_key, 0, window_start)
        
        # Count current entries
        pipe.zcard(redis_key)
        
        # Execute pipeline
        results = await pipe.execute()
        current_count = results[1]
        
        # Check if limit exceeded
        allowed = current_count < limit
        
        # Calculate reset time
        reset_time = current_time + window_seconds
        
        metadata = {
            "limit": limit,
            "current": current_count,
            "remaining": max(0, limit - current_count),
            "reset_time": reset_time,
            "window_seconds": window_seconds,
            "allowed": allowed
        }
        
        return allowed, metadata
    
    async def increment_counter(
        self,
        key: str,
        rule: RateLimitRule,
        current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Increment rate limit counters for all applicable windows
        
        Args:
            key: Rate limit key
            rule: Rate limit rule
            current_time: Current timestamp
            
        Returns:
            Dict with updated counter metadata
        """
        if current_time is None:
            current_time = time.time()
        
        try:
            client = await self._get_redis_client()
            
            # Increment counters for all applicable windows
            increments = []
            
            if rule.requests_per_second:
                meta = await self._increment_sliding_window(
                    client, key, 1, current_time, "second"
                )
                increments.append(("second", meta))
            
            if rule.requests_per_minute:
                meta = await self._increment_sliding_window(
                    client, key, 60, current_time, "minute"
                )
                increments.append(("minute", meta))
            
            if rule.requests_per_hour:
                meta = await self._increment_sliding_window(
                    client, key, 3600, current_time, "hour"
                )
                increments.append(("hour", meta))
            
            if rule.requests_per_day:
                meta = await self._increment_sliding_window(
                    client, key, 86400, current_time, "day"
                )
                increments.append(("day", meta))
            
            if rule.burst_limit:
                meta = await self._increment_sliding_window(
                    client, key, rule.burst_window_seconds, current_time, "burst"
                )
                increments.append(("burst", meta))
            
            return {
                "timestamp": current_time,
                "rule_name": rule.name,
                "increments": {window: meta for window, meta in increments}
            }
            
        except Exception as e:
            logger.error("Rate limit increment failed", key=key, error=str(e))
            raise RateLimitStorageError(f"Failed to increment counter: {str(e)}")
    
    async def _increment_sliding_window(
        self,
        client: redis.Redis,
        key: str,
        window_seconds: int,
        current_time: float,
        window_type: str
    ) -> Dict[str, Any]:
        """Increment sliding window counter"""
        redis_key = self._get_key(key, window_type)
        window_start = current_time - window_seconds
        
        # Use Redis pipeline for atomic operations
        pipe = client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(redis_key, 0, window_start)
        
        # Add current request
        pipe.zadd(redis_key, {str(current_time): current_time})
        
        # Set expiration
        pipe.expire(redis_key, window_seconds + 60)  # Extra buffer
        
        # Count current entries
        pipe.zcard(redis_key)
        
        # Execute pipeline
        results = await pipe.execute()
        current_count = results[3]
        
        return {
            "current_count": current_count,
            "window_seconds": window_seconds,
            "timestamp": current_time
        }
    
    async def get_stats(self, key: str) -> Dict[str, Any]:
        """Get rate limit statistics for key"""
        try:
            client = await self._get_redis_client()
            
            stats = {}
            windows = ["second", "minute", "hour", "day", "burst"]
            
            for window in windows:
                redis_key = self._get_key(key, window)
                count = await client.zcard(redis_key)
                if count > 0:
                    # Get oldest and newest entries
                    oldest = await client.zrange(redis_key, 0, 0, withscores=True)
                    newest = await client.zrange(redis_key, -1, -1, withscores=True)
                    
                    stats[window] = {
                        "count": count,
                        "oldest": oldest[0][1] if oldest else None,
                        "newest": newest[0][1] if newest else None
                    }
                else:
                    stats[window] = {"count": 0}
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get rate limit stats", key=key, error=str(e))
            return {"error": str(e)}
    
    async def reset_counter(self, key: str) -> bool:
        """Reset all rate limit counters for key"""
        try:
            client = await self._get_redis_client()
            
            windows = ["second", "minute", "hour", "day", "burst"]
            keys_to_delete = [self._get_key(key, window) for window in windows]
            
            deleted = await client.delete(*keys_to_delete)
            
            logger.info("Rate limit counters reset", key=key, deleted_keys=deleted)
            return True
            
        except Exception as e:
            logger.error("Failed to reset rate limit counters", key=key, error=str(e))
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None


class MemoryRateLimitStorage(RateLimitStorage):
    """In-memory rate limit storage for development/testing"""
    
    def __init__(self):
        self.storage: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(
        self,
        key: str,
        rule: RateLimitRule,
        current_time: Optional[float] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit using in-memory storage"""
        if current_time is None:
            current_time = time.time()
        
        async with self._lock:
            # Clean old entries
            await self._cleanup_old_entries(key, current_time)
            
            # Get current count
            current_count = len(self.storage.get(key, []))
            
            # Check against the most restrictive limit
            limit = min(filter(None, [
                rule.requests_per_second,
                rule.requests_per_minute,
                rule.requests_per_hour,
                rule.requests_per_day
            ]))
            
            allowed = current_count < limit
            
            return allowed, {
                "limit": limit,
                "current": current_count,
                "remaining": max(0, limit - current_count),
                "allowed": allowed
            }
    
    async def increment_counter(
        self,
        key: str,
        rule: RateLimitRule,
        current_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """Increment in-memory counter"""
        if current_time is None:
            current_time = time.time()
        
        async with self._lock:
            if key not in self.storage:
                self.storage[key] = []
            
            self.storage[key].append(current_time)
            
            return {
                "timestamp": current_time,
                "count": len(self.storage[key])
            }
    
    async def _cleanup_old_entries(self, key: str, current_time: float):
        """Remove old entries from memory storage"""
        if key in self.storage:
            # Keep entries from last hour
            cutoff = current_time - 3600
            self.storage[key] = [
                timestamp for timestamp in self.storage[key]
                if timestamp > cutoff
            ]
    
    async def get_stats(self, key: str) -> Dict[str, Any]:
        """Get stats from memory storage"""
        async with self._lock:
            entries = self.storage.get(key, [])
            return {
                "count": len(entries),
                "oldest": min(entries) if entries else None,
                "newest": max(entries) if entries else None
            }
    
    async def reset_counter(self, key: str) -> bool:
        """Reset memory counter"""
        async with self._lock:
            if key in self.storage:
                del self.storage[key]
            return True


# Factory function to create storage backend
def create_rate_limit_storage(backend: str = "redis", **kwargs) -> RateLimitStorage:
    """
    Create rate limit storage backend
    
    Args:
        backend: Storage backend type ("redis" or "memory")
        **kwargs: Additional arguments for storage backend
        
    Returns:
        RateLimitStorage: Storage backend instance
    """
    if backend == "redis":
        return RedisRateLimitStorage(**kwargs)
    elif backend == "memory":
        return MemoryRateLimitStorage()
    else:
        raise ValueError(f"Unknown storage backend: {backend}")


# Export main classes and functions
__all__ = [
    'RateLimitStorage',
    'RedisRateLimitStorage',
    'MemoryRateLimitStorage',
    'RateLimitStorageError',
    'create_rate_limit_storage'
]
