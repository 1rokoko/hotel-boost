"""
DeepSeek API configuration for WhatsApp Hotel Bot
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class DeepSeekModel(str, Enum):
    """Available DeepSeek models"""
    CHAT = "deepseek-chat"
    REASONER = "deepseek-reasoner"


class DeepSeekConfig(BaseModel):
    """DeepSeek API configuration"""
    
    api_key: str = Field(..., description="DeepSeek API key")
    base_url: str = Field(default="https://api.deepseek.com", description="DeepSeek API base URL")
    default_model: DeepSeekModel = Field(default=DeepSeekModel.CHAT, description="Default model to use")
    max_tokens: int = Field(default=4096, ge=1, le=8192, description="Maximum tokens per request")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    timeout: int = Field(default=60, ge=1, le=300, description="Request timeout in seconds")
    
    # Rate limiting
    max_requests_per_minute: int = Field(default=50, ge=1, description="Max requests per minute")
    max_tokens_per_minute: int = Field(default=100000, ge=1000, description="Max tokens per minute")
    
    # Retry configuration
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="Base retry delay in seconds")
    retry_exponential_base: float = Field(default=2.0, ge=1.0, le=10.0, description="Exponential backoff base")
    
    # Caching
    cache_enabled: bool = Field(default=True, description="Enable response caching")
    cache_ttl: int = Field(default=3600, ge=60, description="Cache TTL in seconds")
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError("DeepSeek API key must be at least 10 characters long")
        return v
    
    @validator('base_url')
    def validate_base_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Base URL must start with http:// or https://")
        return v.rstrip('/')
    
    class Config:
        env_prefix = "DEEPSEEK_"


class SentimentConfig(BaseModel):
    """Configuration for sentiment analysis"""
    
    # Sentiment thresholds
    positive_threshold: float = Field(default=0.3, ge=-1.0, le=1.0, description="Positive sentiment threshold")
    negative_threshold: float = Field(default=-0.3, ge=-1.0, le=1.0, description="Negative sentiment threshold")
    attention_threshold: float = Field(default=-0.7, ge=-1.0, le=1.0, description="Requires attention threshold")
    
    # Confidence thresholds
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0, description="Minimum confidence for sentiment")
    
    # Notification settings
    notify_on_negative: bool = Field(default=True, description="Send notifications for negative sentiment")
    notify_on_attention: bool = Field(default=True, description="Send notifications for attention-required sentiment")
    
    # Language settings
    supported_languages: List[str] = Field(
        default=["en", "ru", "es", "fr", "de"], 
        description="Supported languages for sentiment analysis"
    )
    default_language: str = Field(default="en", description="Default language for analysis")


class ResponseGenerationConfig(BaseModel):
    """Configuration for response generation"""
    
    # Generation parameters
    max_response_tokens: int = Field(default=500, ge=50, le=2000, description="Max tokens for generated responses")
    response_temperature: float = Field(default=0.8, ge=0.0, le=2.0, description="Temperature for response generation")
    
    # Context settings
    max_context_messages: int = Field(default=10, ge=1, le=50, description="Max messages to include in context")
    include_guest_history: bool = Field(default=True, description="Include guest conversation history")
    
    # Response quality
    min_response_length: int = Field(default=10, ge=1, description="Minimum response length in characters")
    max_response_length: int = Field(default=1000, ge=100, description="Maximum response length in characters")
    
    # Personalization
    use_guest_preferences: bool = Field(default=True, description="Use guest preferences for personalization")
    use_hotel_branding: bool = Field(default=True, description="Include hotel branding in responses")


def get_deepseek_config() -> DeepSeekConfig:
    """Get DeepSeek configuration from environment"""
    try:
        config = DeepSeekConfig(
            api_key=settings.DEEPSEEK_API_KEY or "",
            base_url=settings.DEEPSEEK_API_URL,
            max_tokens=getattr(settings, 'DEEPSEEK_MAX_TOKENS', 4096),
            temperature=getattr(settings, 'DEEPSEEK_TEMPERATURE', 0.7),
            timeout=getattr(settings, 'DEEPSEEK_TIMEOUT', 60),
            max_requests_per_minute=getattr(settings, 'DEEPSEEK_MAX_REQUESTS_PER_MINUTE', 50),
            max_tokens_per_minute=getattr(settings, 'DEEPSEEK_MAX_TOKENS_PER_MINUTE', 100000),
            max_retries=getattr(settings, 'DEEPSEEK_MAX_RETRIES', 3),
            retry_delay=getattr(settings, 'DEEPSEEK_RETRY_DELAY', 1.0),
            cache_enabled=getattr(settings, 'DEEPSEEK_CACHE_ENABLED', True),
            cache_ttl=getattr(settings, 'DEEPSEEK_CACHE_TTL', 3600)
        )
        
        logger.info("DeepSeek configuration loaded successfully", 
                   model=config.default_model.value,
                   max_tokens=config.max_tokens,
                   cache_enabled=config.cache_enabled)
        
        return config
        
    except Exception as e:
        logger.error("Failed to load DeepSeek configuration", error=str(e))
        raise


def get_sentiment_config() -> SentimentConfig:
    """Get sentiment analysis configuration"""
    try:
        config = SentimentConfig(
            positive_threshold=getattr(settings, 'SENTIMENT_POSITIVE_THRESHOLD', 0.3),
            negative_threshold=getattr(settings, 'SENTIMENT_NEGATIVE_THRESHOLD', -0.3),
            attention_threshold=getattr(settings, 'SENTIMENT_ATTENTION_THRESHOLD', -0.7),
            min_confidence=getattr(settings, 'SENTIMENT_MIN_CONFIDENCE', 0.6),
            notify_on_negative=getattr(settings, 'SENTIMENT_NOTIFY_ON_NEGATIVE', True),
            notify_on_attention=getattr(settings, 'SENTIMENT_NOTIFY_ON_ATTENTION', True),
            default_language=getattr(settings, 'SENTIMENT_DEFAULT_LANGUAGE', 'en')
        )
        
        logger.info("Sentiment configuration loaded successfully",
                   positive_threshold=config.positive_threshold,
                   negative_threshold=config.negative_threshold,
                   notify_on_negative=config.notify_on_negative)
        
        return config
        
    except Exception as e:
        logger.error("Failed to load sentiment configuration", error=str(e))
        raise


def get_response_generation_config() -> ResponseGenerationConfig:
    """Get response generation configuration"""
    try:
        config = ResponseGenerationConfig(
            max_response_tokens=getattr(settings, 'RESPONSE_MAX_TOKENS', 500),
            response_temperature=getattr(settings, 'RESPONSE_TEMPERATURE', 0.8),
            max_context_messages=getattr(settings, 'RESPONSE_MAX_CONTEXT_MESSAGES', 10),
            include_guest_history=getattr(settings, 'RESPONSE_INCLUDE_GUEST_HISTORY', True),
            min_response_length=getattr(settings, 'RESPONSE_MIN_LENGTH', 10),
            max_response_length=getattr(settings, 'RESPONSE_MAX_LENGTH', 1000),
            use_guest_preferences=getattr(settings, 'RESPONSE_USE_GUEST_PREFERENCES', True),
            use_hotel_branding=getattr(settings, 'RESPONSE_USE_HOTEL_BRANDING', True)
        )
        
        logger.info("Response generation configuration loaded successfully",
                   max_tokens=config.max_response_tokens,
                   temperature=config.response_temperature,
                   max_context=config.max_context_messages)
        
        return config
        
    except Exception as e:
        logger.error("Failed to load response generation configuration", error=str(e))
        raise


# Global configuration instances
_deepseek_config: Optional[DeepSeekConfig] = None
_sentiment_config: Optional[SentimentConfig] = None
_response_config: Optional[ResponseGenerationConfig] = None


def get_global_deepseek_config() -> DeepSeekConfig:
    """Get global DeepSeek configuration instance"""
    global _deepseek_config
    if _deepseek_config is None:
        _deepseek_config = get_deepseek_config()
    return _deepseek_config


def get_global_sentiment_config() -> SentimentConfig:
    """Get global sentiment configuration instance"""
    global _sentiment_config
    if _sentiment_config is None:
        _sentiment_config = get_sentiment_config()
    return _sentiment_config


def get_global_response_config() -> ResponseGenerationConfig:
    """Get global response generation configuration instance"""
    global _response_config
    if _response_config is None:
        _response_config = get_response_generation_config()
    return _response_config


def reload_configurations():
    """Reload all configurations from environment"""
    global _deepseek_config, _sentiment_config, _response_config
    _deepseek_config = None
    _sentiment_config = None
    _response_config = None

    logger.info("DeepSeek configurations reloaded")


# Hotel-specific configuration functions
def create_hotel_deepseek_config(
    hotel_id: str,
    hotel_settings: Dict[str, Any],
    base_config: Optional[DeepSeekConfig] = None
) -> DeepSeekConfig:
    """
    Create hotel-specific DeepSeek configuration

    Args:
        hotel_id: Hotel identifier
        hotel_settings: Hotel's DeepSeek settings from database
        base_config: Base configuration to override (uses global if None)

    Returns:
        DeepSeekConfig: Hotel-specific configuration
    """
    if base_config is None:
        base_config = get_global_deepseek_config()

    # Start with base config
    config_dict = base_config.dict()

    # Override with hotel-specific settings
    if hotel_settings.get("api_key"):
        config_dict["api_key"] = hotel_settings["api_key"]

    if hotel_settings.get("model"):
        config_dict["default_model"] = hotel_settings["model"]

    if hotel_settings.get("max_tokens"):
        config_dict["max_tokens"] = hotel_settings["max_tokens"]

    if hotel_settings.get("temperature") is not None:
        config_dict["temperature"] = hotel_settings["temperature"]

    if hotel_settings.get("timeout"):
        config_dict["timeout"] = hotel_settings["timeout"]

    if hotel_settings.get("max_requests_per_minute"):
        config_dict["max_requests_per_minute"] = hotel_settings["max_requests_per_minute"]

    if hotel_settings.get("max_tokens_per_minute"):
        config_dict["max_tokens_per_minute"] = hotel_settings["max_tokens_per_minute"]

    if hotel_settings.get("cache_enabled") is not None:
        config_dict["cache_enabled"] = hotel_settings["cache_enabled"]

    if hotel_settings.get("cache_ttl"):
        config_dict["cache_ttl"] = hotel_settings["cache_ttl"]

    logger.info(
        "Created hotel-specific DeepSeek configuration",
        hotel_id=hotel_id,
        model=config_dict["default_model"],
        has_api_key=bool(config_dict.get("api_key"))
    )

    return DeepSeekConfig(**config_dict)


def create_hotel_sentiment_config(
    hotel_id: str,
    hotel_settings: Dict[str, Any],
    base_config: Optional[SentimentConfig] = None
) -> SentimentConfig:
    """
    Create hotel-specific sentiment analysis configuration

    Args:
        hotel_id: Hotel identifier
        hotel_settings: Hotel's sentiment settings from database
        base_config: Base configuration to override (uses global if None)

    Returns:
        SentimentConfig: Hotel-specific sentiment configuration
    """
    if base_config is None:
        base_config = get_global_sentiment_config()

    # Start with base config
    config_dict = base_config.dict()

    # Get sentiment analysis settings from hotel
    sentiment_settings = hotel_settings.get("sentiment_analysis", {})

    if sentiment_settings.get("threshold") is not None:
        config_dict["negative_threshold"] = sentiment_settings["threshold"]
        config_dict["positive_threshold"] = 1.0 - sentiment_settings["threshold"]

    if sentiment_settings.get("confidence_threshold") is not None:
        config_dict["confidence_threshold"] = sentiment_settings["confidence_threshold"]

    logger.info(
        "Created hotel-specific sentiment configuration",
        hotel_id=hotel_id,
        threshold=config_dict["negative_threshold"]
    )

    return SentimentConfig(**config_dict)


def create_hotel_response_config(
    hotel_id: str,
    hotel_settings: Dict[str, Any],
    base_config: Optional[ResponseGenerationConfig] = None
) -> ResponseGenerationConfig:
    """
    Create hotel-specific response generation configuration

    Args:
        hotel_id: Hotel identifier
        hotel_settings: Hotel's response generation settings from database
        base_config: Base configuration to override (uses global if None)

    Returns:
        ResponseGenerationConfig: Hotel-specific response configuration
    """
    if base_config is None:
        base_config = get_global_response_config()

    # Start with base config
    config_dict = base_config.dict()

    # Get response generation settings from hotel
    response_settings = hotel_settings.get("response_generation", {})

    if response_settings.get("max_response_tokens"):
        config_dict["max_response_tokens"] = response_settings["max_response_tokens"]

    if response_settings.get("response_temperature") is not None:
        config_dict["response_temperature"] = response_settings["response_temperature"]

    if response_settings.get("max_context_messages"):
        config_dict["max_context_messages"] = response_settings["max_context_messages"]

    if response_settings.get("include_guest_history") is not None:
        config_dict["include_guest_history"] = response_settings["include_guest_history"]

    if response_settings.get("use_hotel_branding") is not None:
        config_dict["use_hotel_branding"] = response_settings["use_hotel_branding"]

    logger.info(
        "Created hotel-specific response configuration",
        hotel_id=hotel_id,
        max_tokens=config_dict["max_response_tokens"],
        temperature=config_dict["response_temperature"]
    )

    return ResponseGenerationConfig(**config_dict)


# Export main components
__all__ = [
    'DeepSeekModel',
    'DeepSeekConfig',
    'SentimentConfig', 
    'ResponseGenerationConfig',
    'get_deepseek_config',
    'get_sentiment_config',
    'get_response_generation_config',
    'get_global_deepseek_config',
    'get_global_sentiment_config',
    'get_global_response_config',
    'reload_configurations'
]
