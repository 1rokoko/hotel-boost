"""
Retry configuration for different services and operations
"""

from typing import Dict, Type, Tuple, Optional, Callable
from app.utils.retry_handler import RetryConfig, RetryStrategy
from app.core.config import settings


# Service-specific retry configurations
RETRY_CONFIGS: Dict[str, RetryConfig] = {
    
    # Green API retry configuration
    "green_api": RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # DeepSeek API retry configuration
    "deepseek_api": RetryConfig(
        max_retries=2,  # Fewer retries for AI API
        base_delay=2.0,  # Longer base delay
        max_delay=60.0,
        exponential_base=2.5,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # Database operations retry configuration
    "database": RetryConfig(
        max_retries=5,
        base_delay=0.5,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # Redis operations retry configuration
    "redis": RetryConfig(
        max_retries=3,
        base_delay=0.1,
        max_delay=5.0,
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # HTTP requests retry configuration
    "http_requests": RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # Webhook processing retry configuration
    "webhook_processing": RetryConfig(
        max_retries=2,
        base_delay=0.5,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # Message sending retry configuration
    "message_sending": RetryConfig(
        max_retries=4,
        base_delay=2.0,
        max_delay=120.0,
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # Sentiment analysis retry configuration
    "sentiment_analysis": RetryConfig(
        max_retries=2,
        base_delay=1.5,
        max_delay=45.0,
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # Trigger execution retry configuration
    "trigger_execution": RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=60.0,
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # Celery tasks retry configuration
    "celery_tasks": RetryConfig(
        max_retries=3,
        base_delay=5.0,
        max_delay=300.0,  # 5 minutes
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # File operations retry configuration
    "file_operations": RetryConfig(
        max_retries=3,
        base_delay=0.5,
        max_delay=10.0,
        exponential_base=2.0,
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    ),
    
    # Critical operations retry configuration
    "critical_operations": RetryConfig(
        max_retries=5,
        base_delay=1.0,
        max_delay=60.0,
        exponential_base=1.5,  # More conservative backoff
        jitter=True,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=(Exception,),
        non_retryable_exceptions=()
    )
}


def get_retry_config(service_name: str) -> RetryConfig:
    """
    Get retry configuration for a service
    
    Args:
        service_name: Name of the service
        
    Returns:
        RetryConfig for the service
    """
    return RETRY_CONFIGS.get(service_name, RetryConfig())


def update_retry_config(service_name: str, config: RetryConfig) -> None:
    """
    Update retry configuration for a service
    
    Args:
        service_name: Name of the service
        config: New configuration
    """
    RETRY_CONFIGS[service_name] = config


# Environment-specific adjustments
if hasattr(settings, 'ENVIRONMENT'):
    if settings.ENVIRONMENT == 'production':
        # More aggressive retries for production
        for config in RETRY_CONFIGS.values():
            config.max_retries = min(10, config.max_retries + 2)
            config.max_delay = min(300.0, config.max_delay * 1.5)
    
    elif settings.ENVIRONMENT == 'development':
        # Faster failures for development
        for config in RETRY_CONFIGS.values():
            config.max_retries = max(1, config.max_retries - 1)
            config.max_delay = max(5.0, config.max_delay * 0.5)
    
    elif settings.ENVIRONMENT == 'testing':
        # Minimal retries for testing
        for config in RETRY_CONFIGS.values():
            config.max_retries = 1
            config.base_delay = 0.1
            config.max_delay = 1.0


# Service-specific retry configuration names
class RetryConfigNames:
    """Constants for retry configuration names"""
    GREEN_API = "green_api"
    DEEPSEEK_API = "deepseek_api"
    DATABASE = "database"
    REDIS = "redis"
    HTTP_REQUESTS = "http_requests"
    WEBHOOK_PROCESSING = "webhook_processing"
    MESSAGE_SENDING = "message_sending"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    TRIGGER_EXECUTION = "trigger_execution"
    CELERY_TASKS = "celery_tasks"
    FILE_OPERATIONS = "file_operations"
    CRITICAL_OPERATIONS = "critical_operations"


# Default configurations for common scenarios
DEFAULT_CONFIGS = {
    "quick": RetryConfig(
        max_retries=2,
        base_delay=0.5,
        max_delay=5.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF
    ),
    
    "standard": RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF
    ),
    
    "aggressive": RetryConfig(
        max_retries=5,
        base_delay=2.0,
        max_delay=60.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF
    ),
    
    "patient": RetryConfig(
        max_retries=10,
        base_delay=5.0,
        max_delay=300.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF
    )
}


def get_default_config(config_type: str = "standard") -> RetryConfig:
    """
    Get a default retry configuration
    
    Args:
        config_type: Type of default configuration
        
    Returns:
        Default RetryConfig
    """
    return DEFAULT_CONFIGS.get(config_type, DEFAULT_CONFIGS["standard"])


# Callback functions for common scenarios
def log_retry_attempt(attempt: int, exception: Exception, delay: float) -> None:
    """Default retry callback that logs retry attempts"""
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    
    logger.warning("Retry attempt",
                   attempt=attempt + 1,
                   exception=type(exception).__name__,
                   delay=delay,
                   error=str(exception))


def log_retry_failure(exception: Exception, total_attempts: int) -> None:
    """Default failure callback that logs final failure"""
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    
    logger.error("All retry attempts failed",
                 total_attempts=total_attempts,
                 exception=type(exception).__name__,
                 error=str(exception))


# Add default callbacks to configurations
for config in RETRY_CONFIGS.values():
    if config.on_retry is None:
        config.on_retry = log_retry_attempt
    if config.on_failure is None:
        config.on_failure = log_retry_failure
