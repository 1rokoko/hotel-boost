"""
Redis caching service for DeepSeek AI responses
"""

import json
import hashlib
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import structlog
import redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.schemas.deepseek import (
    CacheKey,
    CachedResponse,
    SentimentAnalysisResult,
    ResponseGenerationResult
)

logger = structlog.get_logger(__name__)


class DeepSeekCacheService:
    """Redis-based caching service for DeepSeek AI responses"""
    
    def __init__(self):
        self.redis_client = self._create_redis_client()
        self.default_ttl = getattr(settings, 'DEEPSEEK_CACHE_TTL', 3600)  # 1 hour
        self.cache_enabled = getattr(settings, 'DEEPSEEK_CACHE_ENABLED', True)
        
        # Cache key prefixes
        self.prefixes = {
            'sentiment': 'deepseek:sentiment:',
            'response': 'deepseek:response:',
            'conversation': 'deepseek:conversation:',
            'metrics': 'deepseek:metrics:',
            'config': 'deepseek:config:'
        }
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'errors': 0
        }
    
    def _create_redis_client(self) -> redis.Redis:
        """Create Redis client connection"""
        try:
            client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                password=getattr(settings, 'REDIS_PASSWORD', None),
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            client.ping()
            logger.info("Redis connection established for DeepSeek cache")
            
            return client
            
        except Exception as e:
            logger.error("Failed to connect to Redis for DeepSeek cache", error=str(e))
            # Return a mock client that does nothing
            return MockRedisClient()
    
    def _create_cache_key(
        self,
        operation_type: str,
        content: str,
        model: str = "deepseek-chat",
        **kwargs
    ) -> str:
        """Create cache key for content"""
        # Create content hash
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Create parameters hash
        params_str = json.dumps(kwargs, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        
        # Combine into cache key
        cache_key = f"{self.prefixes[operation_type]}{model}:{content_hash}:{params_hash}"
        
        return cache_key
    
    def _serialize_response(self, response: Any) -> str:
        """Serialize response for caching"""
        try:
            if hasattr(response, 'dict'):
                # Pydantic model
                return json.dumps(response.dict())
            elif isinstance(response, dict):
                return json.dumps(response)
            else:
                return json.dumps(str(response))
        except Exception as e:
            logger.error("Failed to serialize response for caching", error=str(e))
            return json.dumps({"error": "serialization_failed"})
    
    def _deserialize_response(self, data: str, response_type: str) -> Any:
        """Deserialize cached response"""
        try:
            parsed_data = json.loads(data)
            
            if response_type == 'sentiment':
                return SentimentAnalysisResult(**parsed_data)
            elif response_type == 'response':
                return ResponseGenerationResult(**parsed_data)
            else:
                return parsed_data
                
        except Exception as e:
            logger.error("Failed to deserialize cached response", error=str(e))
            return None
    
    async def get_sentiment_cache(
        self,
        text: str,
        model: str = "deepseek-chat",
        **kwargs
    ) -> Optional[SentimentAnalysisResult]:
        """Get cached sentiment analysis result"""
        if not self.cache_enabled:
            return None
        
        try:
            cache_key = self._create_cache_key('sentiment', text, model, **kwargs)
            
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                self.stats['hits'] += 1
                
                # Update hit count
                hit_count_key = f"{cache_key}:hits"
                self.redis_client.incr(hit_count_key)
                self.redis_client.expire(hit_count_key, self.default_ttl)
                
                result = self._deserialize_response(cached_data, 'sentiment')
                
                logger.debug("Sentiment cache hit",
                           cache_key=cache_key,
                           text_length=len(text))
                
                return result
            else:
                self.stats['misses'] += 1
                return None
                
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error("Redis error in sentiment cache get", error=str(e))
            return None
        except Exception as e:
            self.stats['errors'] += 1
            logger.error("Error getting sentiment cache", error=str(e))
            return None
    
    async def set_sentiment_cache(
        self,
        text: str,
        result: SentimentAnalysisResult,
        model: str = "deepseek-chat",
        ttl: Optional[int] = None,
        **kwargs
    ) -> bool:
        """Cache sentiment analysis result"""
        if not self.cache_enabled:
            return False
        
        try:
            cache_key = self._create_cache_key('sentiment', text, model, **kwargs)
            serialized_data = self._serialize_response(result)
            
            ttl = ttl or self.default_ttl
            
            success = self.redis_client.setex(cache_key, ttl, serialized_data)
            
            if success:
                self.stats['sets'] += 1
                
                # Set metadata
                metadata = {
                    'cached_at': datetime.utcnow().isoformat(),
                    'ttl': ttl,
                    'text_length': len(text),
                    'sentiment_type': result.sentiment.value,
                    'confidence': result.confidence
                }
                
                metadata_key = f"{cache_key}:meta"
                self.redis_client.setex(metadata_key, ttl, json.dumps(metadata))
                
                logger.debug("Sentiment result cached",
                           cache_key=cache_key,
                           ttl=ttl,
                           sentiment=result.sentiment.value)
            
            return success
            
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error("Redis error in sentiment cache set", error=str(e))
            return False
        except Exception as e:
            self.stats['errors'] += 1
            logger.error("Error setting sentiment cache", error=str(e))
            return False
    
    async def get_response_cache(
        self,
        message: str,
        context_hash: str,
        model: str = "deepseek-chat",
        **kwargs
    ) -> Optional[ResponseGenerationResult]:
        """Get cached response generation result"""
        if not self.cache_enabled:
            return None
        
        try:
            # Include context in cache key
            cache_content = f"{message}|{context_hash}"
            cache_key = self._create_cache_key('response', cache_content, model, **kwargs)
            
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                self.stats['hits'] += 1
                
                # Update hit count
                hit_count_key = f"{cache_key}:hits"
                self.redis_client.incr(hit_count_key)
                self.redis_client.expire(hit_count_key, self.default_ttl)
                
                result = self._deserialize_response(cached_data, 'response')
                
                logger.debug("Response cache hit",
                           cache_key=cache_key,
                           message_length=len(message))
                
                return result
            else:
                self.stats['misses'] += 1
                return None
                
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error("Redis error in response cache get", error=str(e))
            return None
        except Exception as e:
            self.stats['errors'] += 1
            logger.error("Error getting response cache", error=str(e))
            return None
    
    async def set_response_cache(
        self,
        message: str,
        context_hash: str,
        result: ResponseGenerationResult,
        model: str = "deepseek-chat",
        ttl: Optional[int] = None,
        **kwargs
    ) -> bool:
        """Cache response generation result"""
        if not self.cache_enabled:
            return False
        
        try:
            # Include context in cache key
            cache_content = f"{message}|{context_hash}"
            cache_key = self._create_cache_key('response', cache_content, model, **kwargs)
            serialized_data = self._serialize_response(result)
            
            ttl = ttl or self.default_ttl
            
            success = self.redis_client.setex(cache_key, ttl, serialized_data)
            
            if success:
                self.stats['sets'] += 1
                
                # Set metadata
                metadata = {
                    'cached_at': datetime.utcnow().isoformat(),
                    'ttl': ttl,
                    'message_length': len(message),
                    'response_type': result.response_type,
                    'confidence': result.confidence
                }
                
                metadata_key = f"{cache_key}:meta"
                self.redis_client.setex(metadata_key, ttl, json.dumps(metadata))
                
                logger.debug("Response result cached",
                           cache_key=cache_key,
                           ttl=ttl,
                           response_type=result.response_type)
            
            return success
            
        except RedisError as e:
            self.stats['errors'] += 1
            logger.error("Redis error in response cache set", error=str(e))
            return False
        except Exception as e:
            self.stats['errors'] += 1
            logger.error("Error setting response cache", error=str(e))
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            # Get Redis info
            redis_info = self.redis_client.info()
            
            # Calculate hit rate
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'enabled': self.cache_enabled,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'sets': self.stats['sets'],
                'errors': self.stats['errors'],
                'hit_rate_percent': round(hit_rate, 2),
                'redis_memory_used': redis_info.get('used_memory_human', 'unknown'),
                'redis_connected_clients': redis_info.get('connected_clients', 0),
                'redis_keyspace_hits': redis_info.get('keyspace_hits', 0),
                'redis_keyspace_misses': redis_info.get('keyspace_misses', 0)
            }
            
        except Exception as e:
            logger.error("Error getting cache stats", error=str(e))
            return {
                'enabled': self.cache_enabled,
                'error': str(e)
            }
    
    def clear_cache(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries"""
        try:
            if pattern:
                # Clear specific pattern
                keys = self.redis_client.keys(pattern)
                if keys:
                    deleted = self.redis_client.delete(*keys)
                    logger.info("Cache cleared by pattern",
                               pattern=pattern,
                               deleted_keys=deleted)
                    return deleted
                return 0
            else:
                # Clear all DeepSeek cache
                total_deleted = 0
                for prefix in self.prefixes.values():
                    keys = self.redis_client.keys(f"{prefix}*")
                    if keys:
                        deleted = self.redis_client.delete(*keys)
                        total_deleted += deleted
                
                logger.info("All DeepSeek cache cleared",
                           deleted_keys=total_deleted)
                return total_deleted
                
        except Exception as e:
            logger.error("Error clearing cache", error=str(e))
            return 0
    
    def get_cache_keys_info(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get information about cached keys"""
        try:
            keys_info = []
            
            for operation_type, prefix in self.prefixes.items():
                keys = self.redis_client.keys(f"{prefix}*")[:limit]
                
                for key in keys:
                    if not key.endswith(':meta') and not key.endswith(':hits'):
                        try:
                            ttl = self.redis_client.ttl(key)
                            size = len(self.redis_client.get(key) or '')
                            
                            # Get metadata if available
                            meta_key = f"{key}:meta"
                            metadata = {}
                            if self.redis_client.exists(meta_key):
                                meta_data = self.redis_client.get(meta_key)
                                if meta_data:
                                    metadata = json.loads(meta_data)
                            
                            # Get hit count
                            hit_count_key = f"{key}:hits"
                            hit_count = self.redis_client.get(hit_count_key) or 0
                            
                            keys_info.append({
                                'key': key,
                                'operation_type': operation_type,
                                'ttl_seconds': ttl,
                                'size_bytes': size,
                                'hit_count': int(hit_count),
                                'metadata': metadata
                            })
                            
                        except Exception as e:
                            logger.error("Error getting key info", key=key, error=str(e))
            
            return keys_info
            
        except Exception as e:
            logger.error("Error getting cache keys info", error=str(e))
            return []


class MockRedisClient:
    """Mock Redis client for when Redis is unavailable"""
    
    def __init__(self):
        self.data = {}
    
    def get(self, key):
        return None
    
    def setex(self, key, ttl, value):
        return False
    
    def delete(self, *keys):
        return 0
    
    def keys(self, pattern):
        return []
    
    def exists(self, key):
        return False
    
    def incr(self, key):
        return 1
    
    def expire(self, key, ttl):
        return True
    
    def ttl(self, key):
        return -1
    
    def ping(self):
        return True
    
    def info(self):
        return {}


# Global cache service instance
_global_cache_service: Optional[DeepSeekCacheService] = None


def get_cache_service() -> DeepSeekCacheService:
    """Get global cache service instance"""
    global _global_cache_service
    if _global_cache_service is None:
        _global_cache_service = DeepSeekCacheService()
    return _global_cache_service


# Export main components
__all__ = [
    'DeepSeekCacheService',
    'MockRedisClient',
    'get_cache_service'
]
