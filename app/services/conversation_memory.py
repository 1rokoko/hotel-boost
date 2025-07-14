"""
Conversation memory service for managing context and guest preferences
"""

import json
import redis
from typing import Dict, Any, Optional, List, Union
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import structlog

from app.core.config import settings
from app.models.message import Conversation
from app.models.guest import Guest
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConversationMemory:
    """
    Service for managing conversation context and memory with Redis backend
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or self._create_redis_client()
        self.default_ttl = 86400 * 7  # 7 days
        self.context_prefix = "conv_context:"
        self.guest_pref_prefix = "guest_pref:"
        self.session_prefix = "conv_session:"
    
    def _create_redis_client(self) -> redis.Redis:
        """Create Redis client"""
        try:
            client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            client.ping()
            logger.info("Redis connection established")
            return client
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            # Fallback to in-memory storage for development
            return redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    async def store_context(
        self,
        conversation_id: Union[str, UUID],
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store context value for a conversation
        
        Args:
            conversation_id: Conversation ID
            key: Context key
            value: Value to store
            ttl: Time to live in seconds
            
        Returns:
            bool: Success status
        """
        try:
            redis_key = f"{self.context_prefix}{conversation_id}:{key}"
            
            # Serialize value
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value, default=str)
            else:
                serialized_value = str(value)
            
            # Store with TTL
            ttl = ttl or self.default_ttl
            result = self.redis_client.setex(redis_key, ttl, serialized_value)
            
            logger.debug("Context stored",
                        conversation_id=str(conversation_id),
                        key=key,
                        ttl=ttl)
            
            return result
            
        except Exception as e:
            logger.error("Failed to store context",
                        conversation_id=str(conversation_id),
                        key=key,
                        error=str(e))
            return False
    
    async def get_context(
        self,
        conversation_id: Union[str, UUID],
        key: str = None,
        default: Any = None
    ) -> Any:
        """
        Get context value(s) for a conversation
        
        Args:
            conversation_id: Conversation ID
            key: Specific key to get (if None, gets all context)
            default: Default value if key not found
            
        Returns:
            Context value or default
        """
        try:
            if key:
                # Get specific key
                redis_key = f"{self.context_prefix}{conversation_id}:{key}"
                value = self.redis_client.get(redis_key)
                
                if value is None:
                    return default
                
                # Try to deserialize JSON
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            else:
                # Get all context keys for conversation
                pattern = f"{self.context_prefix}{conversation_id}:*"
                keys = self.redis_client.keys(pattern)
                
                if not keys:
                    return default or {}
                
                # Get all values
                context = {}
                for redis_key in keys:
                    # Extract the context key from redis key
                    context_key = redis_key.split(':', 2)[-1]
                    value = self.redis_client.get(redis_key)
                    
                    if value:
                        try:
                            context[context_key] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            context[context_key] = value
                
                return context
                
        except Exception as e:
            logger.error("Failed to get context",
                        conversation_id=str(conversation_id),
                        key=key,
                        error=str(e))
            return default
    
    async def update_context(
        self,
        conversation_id: Union[str, UUID],
        updates: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Update multiple context values
        
        Args:
            conversation_id: Conversation ID
            updates: Dictionary of key-value pairs to update
            ttl: Time to live in seconds
            
        Returns:
            bool: Success status
        """
        try:
            success_count = 0
            
            for key, value in updates.items():
                if await self.store_context(conversation_id, key, value, ttl):
                    success_count += 1
            
            logger.debug("Context updated",
                        conversation_id=str(conversation_id),
                        updated_keys=list(updates.keys()),
                        success_count=success_count)
            
            return success_count == len(updates)
            
        except Exception as e:
            logger.error("Failed to update context",
                        conversation_id=str(conversation_id),
                        error=str(e))
            return False
    
    async def delete_context(
        self,
        conversation_id: Union[str, UUID],
        key: Optional[str] = None
    ) -> bool:
        """
        Delete context key(s) for a conversation
        
        Args:
            conversation_id: Conversation ID
            key: Specific key to delete (if None, deletes all context)
            
        Returns:
            bool: Success status
        """
        try:
            if key:
                # Delete specific key
                redis_key = f"{self.context_prefix}{conversation_id}:{key}"
                result = self.redis_client.delete(redis_key)
                return result > 0
            else:
                # Delete all context for conversation
                pattern = f"{self.context_prefix}{conversation_id}:*"
                keys = self.redis_client.keys(pattern)
                
                if keys:
                    result = self.redis_client.delete(*keys)
                    return result > 0
                
                return True
                
        except Exception as e:
            logger.error("Failed to delete context",
                        conversation_id=str(conversation_id),
                        key=key,
                        error=str(e))
            return False
    
    async def store_guest_preferences(
        self,
        guest_id: Union[str, UUID],
        preferences: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store guest preferences
        
        Args:
            guest_id: Guest ID
            preferences: Preferences dictionary
            ttl: Time to live in seconds
            
        Returns:
            bool: Success status
        """
        try:
            redis_key = f"{self.guest_pref_prefix}{guest_id}"
            
            # Get existing preferences
            existing = await self.get_guest_preferences(guest_id) or {}
            
            # Merge with new preferences
            existing.update(preferences)
            
            # Store updated preferences
            serialized = json.dumps(existing, default=str)
            ttl = ttl or (self.default_ttl * 30)  # 30 days for preferences
            
            result = self.redis_client.setex(redis_key, ttl, serialized)
            
            logger.debug("Guest preferences stored",
                        guest_id=str(guest_id),
                        preferences_count=len(existing))
            
            return result
            
        except Exception as e:
            logger.error("Failed to store guest preferences",
                        guest_id=str(guest_id),
                        error=str(e))
            return False
    
    async def get_guest_preferences(
        self,
        guest_id: Union[str, UUID]
    ) -> Optional[Dict[str, Any]]:
        """
        Get guest preferences
        
        Args:
            guest_id: Guest ID
            
        Returns:
            Preferences dictionary or None
        """
        try:
            redis_key = f"{self.guest_pref_prefix}{guest_id}"
            value = self.redis_client.get(redis_key)
            
            if value:
                return json.loads(value)
            
            return None
            
        except Exception as e:
            logger.error("Failed to get guest preferences",
                        guest_id=str(guest_id),
                        error=str(e))
            return None
    
    async def create_conversation_session(
        self,
        conversation_id: Union[str, UUID],
        session_data: Dict[str, Any],
        ttl: int = 3600  # 1 hour default
    ) -> bool:
        """
        Create a conversation session for temporary data
        
        Args:
            conversation_id: Conversation ID
            session_data: Session data
            ttl: Time to live in seconds
            
        Returns:
            bool: Success status
        """
        try:
            redis_key = f"{self.session_prefix}{conversation_id}"
            
            # Add timestamp
            session_data['created_at'] = datetime.utcnow().isoformat()
            session_data['expires_at'] = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
            
            serialized = json.dumps(session_data, default=str)
            result = self.redis_client.setex(redis_key, ttl, serialized)
            
            logger.debug("Conversation session created",
                        conversation_id=str(conversation_id),
                        ttl=ttl)
            
            return result
            
        except Exception as e:
            logger.error("Failed to create conversation session",
                        conversation_id=str(conversation_id),
                        error=str(e))
            return False
    
    async def get_conversation_session(
        self,
        conversation_id: Union[str, UUID]
    ) -> Optional[Dict[str, Any]]:
        """
        Get conversation session data
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Session data or None
        """
        try:
            redis_key = f"{self.session_prefix}{conversation_id}"
            value = self.redis_client.get(redis_key)
            
            if value:
                return json.loads(value)
            
            return None
            
        except Exception as e:
            logger.error("Failed to get conversation session",
                        conversation_id=str(conversation_id),
                        error=str(e))
            return None
    
    async def extend_session(
        self,
        conversation_id: Union[str, UUID],
        additional_ttl: int = 3600
    ) -> bool:
        """
        Extend conversation session TTL
        
        Args:
            conversation_id: Conversation ID
            additional_ttl: Additional time in seconds
            
        Returns:
            bool: Success status
        """
        try:
            redis_key = f"{self.session_prefix}{conversation_id}"
            result = self.redis_client.expire(redis_key, additional_ttl)
            
            logger.debug("Session extended",
                        conversation_id=str(conversation_id),
                        additional_ttl=additional_ttl)
            
            return result
            
        except Exception as e:
            logger.error("Failed to extend session",
                        conversation_id=str(conversation_id),
                        error=str(e))
            return False
    
    async def cleanup_expired_data(self) -> Dict[str, int]:
        """
        Cleanup expired data (manual cleanup for monitoring)
        
        Returns:
            Dict with cleanup statistics
        """
        try:
            stats = {
                'contexts_cleaned': 0,
                'preferences_cleaned': 0,
                'sessions_cleaned': 0
            }
            
            # Note: Redis automatically handles TTL expiration,
            # this is mainly for monitoring and manual cleanup
            
            # Get all keys with TTL
            for prefix, stat_key in [
                (self.context_prefix, 'contexts_cleaned'),
                (self.guest_pref_prefix, 'preferences_cleaned'),
                (self.session_prefix, 'sessions_cleaned')
            ]:
                pattern = f"{prefix}*"
                keys = self.redis_client.keys(pattern)
                
                for key in keys:
                    ttl = self.redis_client.ttl(key)
                    if ttl == -1:  # No TTL set
                        # Set default TTL
                        self.redis_client.expire(key, self.default_ttl)
                    elif ttl == -2:  # Key doesn't exist (expired)
                        stats[stat_key] += 1
            
            logger.info("Memory cleanup completed", **stats)
            return stats
            
        except Exception as e:
            logger.error("Failed to cleanup expired data", error=str(e))
            return {'error': str(e)}


# Export memory service
__all__ = ['ConversationMemory']
