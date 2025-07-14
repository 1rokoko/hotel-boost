"""
Cache configuration for the enhanced caching system
Provides centralized configuration for cache settings, TTLs, and strategies
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from app.services.cache_service import CacheLevel, CacheStrategy


class CacheProfile(Enum):
    """Predefined cache profiles for different use cases"""
    FAST = "fast"           # Memory-only, short TTL
    BALANCED = "balanced"   # Memory + Redis, medium TTL
    PERSISTENT = "persistent"  # Redis-only, long TTL
    CRITICAL = "critical"   # Both levels, long TTL, write-through


@dataclass
class CacheConfiguration:
    """Cache configuration for specific data types"""
    ttl_seconds: int
    level: CacheLevel
    strategy: CacheStrategy
    compression_enabled: bool = True
    warming_enabled: bool = False
    warming_interval: Optional[int] = None
    invalidation_patterns: List[str] = field(default_factory=list)


class CacheConfigManager:
    """Manages cache configurations for different data types and use cases"""
    
    def __init__(self):
        self.configurations: Dict[str, CacheConfiguration] = {}
        self._setup_default_configurations()
    
    def _setup_default_configurations(self):
        """Setup default cache configurations for common data types"""
        
        # Hotel data configurations
        self.configurations.update({
            "hotel_settings": CacheConfiguration(
                ttl_seconds=3600,  # 1 hour
                level=CacheLevel.BOTH,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                warming_enabled=True,
                warming_interval=1800,  # 30 minutes
                invalidation_patterns=["hotel:*:settings", "hotel:*:config"]
            ),
            
            "hotel_triggers": CacheConfiguration(
                ttl_seconds=1800,  # 30 minutes
                level=CacheLevel.BOTH,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                warming_enabled=True,
                warming_interval=900,  # 15 minutes
                invalidation_patterns=["hotel:*:triggers"]
            ),
            
            "hotel_staff": CacheConfiguration(
                ttl_seconds=7200,  # 2 hours
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["hotel:*:staff"]
            )
        })
        
        # Guest data configurations
        self.configurations.update({
            "guest_profile": CacheConfiguration(
                ttl_seconds=3600,  # 1 hour
                level=CacheLevel.BOTH,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["hotel:*:guest:*:profile"]
            ),
            
            "guest_preferences": CacheConfiguration(
                ttl_seconds=7200,  # 2 hours
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["hotel:*:guest:*:preferences"]
            ),
            
            "guest_conversations": CacheConfiguration(
                ttl_seconds=1800,  # 30 minutes
                level=CacheLevel.MEMORY,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=False,  # Frequently accessed, keep uncompressed
                invalidation_patterns=["hotel:*:guest:*:conversations"]
            )
        })
        
        # Message and conversation configurations
        self.configurations.update({
            "conversation_history": CacheConfiguration(
                ttl_seconds=3600,  # 1 hour
                level=CacheLevel.BOTH,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["conversation:*:history"]
            ),
            
            "message_content": CacheConfiguration(
                ttl_seconds=7200,  # 2 hours
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["message:*:content"]
            ),
            
            "conversation_state": CacheConfiguration(
                ttl_seconds=900,  # 15 minutes
                level=CacheLevel.MEMORY,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=False,
                invalidation_patterns=["conversation:*:state"]
            )
        })
        
        # AI and sentiment analysis configurations
        self.configurations.update({
            "sentiment_analysis": CacheConfiguration(
                ttl_seconds=14400,  # 4 hours
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["sentiment:*"]
            ),
            
            "ai_responses": CacheConfiguration(
                ttl_seconds=7200,  # 2 hours
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["ai:response:*"]
            ),
            
            "deepseek_cache": CacheConfiguration(
                ttl_seconds=3600,  # 1 hour
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["deepseek:*"]
            )
        })
        
        # Template and response configurations
        self.configurations.update({
            "message_templates": CacheConfiguration(
                ttl_seconds=7200,  # 2 hours
                level=CacheLevel.BOTH,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                warming_enabled=True,
                warming_interval=3600,  # 1 hour
                invalidation_patterns=["hotel:*:templates"]
            ),
            
            "auto_responses": CacheConfiguration(
                ttl_seconds=3600,  # 1 hour
                level=CacheLevel.BOTH,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["hotel:*:auto_responses"]
            )
        })
        
        # Analytics and reporting configurations
        self.configurations.update({
            "analytics_daily": CacheConfiguration(
                ttl_seconds=86400,  # 24 hours
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_BEHIND,
                compression_enabled=True,
                invalidation_patterns=["analytics:daily:*"]
            ),
            
            "analytics_hourly": CacheConfiguration(
                ttl_seconds=3600,  # 1 hour
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                invalidation_patterns=["analytics:hourly:*"]
            ),
            
            "performance_metrics": CacheConfiguration(
                ttl_seconds=300,  # 5 minutes
                level=CacheLevel.MEMORY,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=False,
                invalidation_patterns=["metrics:*"]
            )
        })
        
        # Session and authentication configurations
        self.configurations.update({
            "user_sessions": CacheConfiguration(
                ttl_seconds=1800,  # 30 minutes
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=False,
                invalidation_patterns=["session:*"]
            ),
            
            "auth_tokens": CacheConfiguration(
                ttl_seconds=3600,  # 1 hour
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=False,
                invalidation_patterns=["auth:token:*"]
            )
        })
    
    def get_configuration(self, data_type: str) -> Optional[CacheConfiguration]:
        """Get cache configuration for a specific data type"""
        return self.configurations.get(data_type)
    
    def set_configuration(self, data_type: str, config: CacheConfiguration):
        """Set cache configuration for a specific data type"""
        self.configurations[data_type] = config
    
    def get_profile_configuration(self, profile: CacheProfile) -> CacheConfiguration:
        """Get cache configuration for a predefined profile"""
        profile_configs = {
            CacheProfile.FAST: CacheConfiguration(
                ttl_seconds=300,  # 5 minutes
                level=CacheLevel.MEMORY,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=False
            ),
            CacheProfile.BALANCED: CacheConfiguration(
                ttl_seconds=1800,  # 30 minutes
                level=CacheLevel.BOTH,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True
            ),
            CacheProfile.PERSISTENT: CacheConfiguration(
                ttl_seconds=7200,  # 2 hours
                level=CacheLevel.REDIS,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True
            ),
            CacheProfile.CRITICAL: CacheConfiguration(
                ttl_seconds=3600,  # 1 hour
                level=CacheLevel.BOTH,
                strategy=CacheStrategy.WRITE_THROUGH,
                compression_enabled=True,
                warming_enabled=True,
                warming_interval=1800
            )
        }
        
        return profile_configs[profile]
    
    def get_all_configurations(self) -> Dict[str, CacheConfiguration]:
        """Get all cache configurations"""
        return self.configurations.copy()
    
    def get_warming_configurations(self) -> Dict[str, CacheConfiguration]:
        """Get configurations that have warming enabled"""
        return {
            data_type: config
            for data_type, config in self.configurations.items()
            if config.warming_enabled
        }
    
    def get_invalidation_patterns(self) -> Dict[str, List[str]]:
        """Get all invalidation patterns mapped by data type"""
        return {
            data_type: config.invalidation_patterns
            for data_type, config in self.configurations.items()
            if config.invalidation_patterns
        }


# Global cache configuration manager
cache_config_manager = CacheConfigManager()


def get_cache_config_manager() -> CacheConfigManager:
    """Get the global cache configuration manager"""
    return cache_config_manager


def get_cache_config(data_type: str) -> Optional[CacheConfiguration]:
    """Get cache configuration for a data type"""
    return cache_config_manager.get_configuration(data_type)


def get_profile_config(profile: CacheProfile) -> CacheConfiguration:
    """Get cache configuration for a profile"""
    return cache_config_manager.get_profile_configuration(profile)
