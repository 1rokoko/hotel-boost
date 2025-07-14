"""
Circuit breaker configuration for different services
"""

from typing import Dict
from app.utils.circuit_breaker import CircuitBreakerConfig
from app.core.config import settings


# Circuit breaker configurations for different services
CIRCUIT_BREAKER_CONFIGS: Dict[str, CircuitBreakerConfig] = {
    
    # Green API circuit breaker
    "green_api": CircuitBreakerConfig(
        failure_threshold=5,  # Open after 5 failures in window
        recovery_timeout=60.0,  # Wait 60 seconds before trying again
        success_threshold=3,  # Need 3 successes to close
        timeout=30.0,  # 30 second timeout for requests
        expected_exception=(Exception,),
        window_size=50,  # Track last 50 requests
        minimum_requests=10  # Need at least 10 requests to calculate failure rate
    ),
    
    # DeepSeek API circuit breaker
    "deepseek_api": CircuitBreakerConfig(
        failure_threshold=3,  # More sensitive for AI API
        recovery_timeout=120.0,  # Longer recovery time for AI
        success_threshold=2,  # Fewer successes needed
        timeout=45.0,  # Longer timeout for AI processing
        expected_exception=(Exception,),
        window_size=30,  # Smaller window for AI
        minimum_requests=5  # Fewer minimum requests
    ),
    
    # Database circuit breaker
    "database": CircuitBreakerConfig(
        failure_threshold=10,  # More tolerant for database
        recovery_timeout=30.0,  # Quick recovery for database
        success_threshold=5,  # More successes needed for database
        timeout=10.0,  # Short timeout for database
        expected_exception=(Exception,),
        window_size=100,  # Larger window for database
        minimum_requests=20  # More minimum requests for database
    ),
    
    # Redis circuit breaker
    "redis": CircuitBreakerConfig(
        failure_threshold=8,
        recovery_timeout=20.0,  # Quick recovery for cache
        success_threshold=3,
        timeout=5.0,  # Very short timeout for cache
        expected_exception=(Exception,),
        window_size=50,
        minimum_requests=10
    ),
    
    # Webhook processing circuit breaker
    "webhook_processing": CircuitBreakerConfig(
        failure_threshold=15,  # More tolerant for webhook processing
        recovery_timeout=45.0,
        success_threshold=5,
        timeout=20.0,
        expected_exception=(Exception,),
        window_size=100,
        minimum_requests=15
    ),
    
    # Message sending circuit breaker
    "message_sending": CircuitBreakerConfig(
        failure_threshold=7,
        recovery_timeout=90.0,  # Longer recovery for message sending
        success_threshold=4,
        timeout=25.0,
        expected_exception=(Exception,),
        window_size=75,
        minimum_requests=12
    ),
    
    # Sentiment analysis circuit breaker
    "sentiment_analysis": CircuitBreakerConfig(
        failure_threshold=4,
        recovery_timeout=60.0,
        success_threshold=2,
        timeout=30.0,
        expected_exception=(Exception,),
        window_size=40,
        minimum_requests=8
    ),
    
    # Trigger execution circuit breaker
    "trigger_execution": CircuitBreakerConfig(
        failure_threshold=6,
        recovery_timeout=75.0,
        success_threshold=3,
        timeout=35.0,
        expected_exception=(Exception,),
        window_size=60,
        minimum_requests=10
    )
}


def get_circuit_breaker_config(service_name: str) -> CircuitBreakerConfig:
    """
    Get circuit breaker configuration for a service
    
    Args:
        service_name: Name of the service
        
    Returns:
        CircuitBreakerConfig for the service
    """
    return CIRCUIT_BREAKER_CONFIGS.get(service_name, CircuitBreakerConfig())


def update_circuit_breaker_config(service_name: str, config: CircuitBreakerConfig) -> None:
    """
    Update circuit breaker configuration for a service
    
    Args:
        service_name: Name of the service
        config: New configuration
    """
    CIRCUIT_BREAKER_CONFIGS[service_name] = config


# Environment-specific adjustments
if hasattr(settings, 'ENVIRONMENT'):
    if settings.ENVIRONMENT == 'production':
        # More conservative settings for production
        for config in CIRCUIT_BREAKER_CONFIGS.values():
            config.failure_threshold = max(3, config.failure_threshold - 2)
            config.recovery_timeout = min(300.0, config.recovery_timeout * 1.5)
            config.timeout = min(60.0, config.timeout * 1.2)
    
    elif settings.ENVIRONMENT == 'development':
        # More lenient settings for development
        for config in CIRCUIT_BREAKER_CONFIGS.values():
            config.failure_threshold = config.failure_threshold + 3
            config.recovery_timeout = max(10.0, config.recovery_timeout * 0.5)
            config.timeout = config.timeout * 2.0


# Service-specific circuit breaker names
class CircuitBreakerNames:
    """Constants for circuit breaker names"""
    GREEN_API = "green_api"
    DEEPSEEK_API = "deepseek_api"
    DATABASE = "database"
    REDIS = "redis"
    WEBHOOK_PROCESSING = "webhook_processing"
    MESSAGE_SENDING = "message_sending"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    TRIGGER_EXECUTION = "trigger_execution"


# Default fallback configuration
DEFAULT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=3,
    timeout=30.0,
    expected_exception=(Exception,),
    window_size=50,
    minimum_requests=10
)
