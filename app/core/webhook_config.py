"""
Webhook security configuration for Green API and other webhook providers

This module provides configuration classes for webhook security settings,
including signature validation, timestamp verification, and replay attack prevention.
"""

from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field, validator
import structlog

logger = structlog.get_logger(__name__)


class WebhookSecurityConfig(BaseModel):
    """Configuration for webhook security validation"""
    
    # Signature validation settings
    signature_algorithm: str = Field(
        default="sha256",
        description="HMAC algorithm for signature validation"
    )
    
    signature_header: str = Field(
        default="X-Green-Api-Signature",
        description="HTTP header containing the webhook signature"
    )
    
    signature_prefix: str = Field(
        default="sha256=",
        description="Prefix for signature value (e.g., 'sha256=')"
    )
    
    # Timestamp validation settings
    timestamp_tolerance_seconds: int = Field(
        default=300,  # 5 minutes
        ge=60,  # Minimum 1 minute
        le=3600,  # Maximum 1 hour
        description="Maximum age of webhook in seconds"
    )
    
    timestamp_header: str = Field(
        default="X-Green-Api-Timestamp",
        description="HTTP header containing the webhook timestamp"
    )
    
    require_timestamp: bool = Field(
        default=True,
        description="Whether timestamp validation is required"
    )
    
    # Replay attack prevention
    enable_replay_protection: bool = Field(
        default=True,
        description="Enable replay attack prevention"
    )
    
    replay_cache_ttl_seconds: int = Field(
        default=3600,  # 1 hour
        ge=300,  # Minimum 5 minutes
        le=86400,  # Maximum 24 hours
        description="TTL for replay protection cache"
    )
    
    # Rate limiting for webhooks
    webhook_rate_limit_per_minute: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Rate limit for webhook endpoints per minute"
    )
    
    # Content validation
    max_payload_size_bytes: int = Field(
        default=1024 * 1024,  # 1MB
        ge=1024,  # Minimum 1KB
        le=10 * 1024 * 1024,  # Maximum 10MB
        description="Maximum webhook payload size in bytes"
    )
    
    allowed_content_types: Set[str] = Field(
        default_factory=lambda: {
            "application/json",
            "application/x-www-form-urlencoded",
            "text/plain"
        },
        description="Allowed content types for webhook requests"
    )
    
    # Security headers
    required_headers: List[str] = Field(
        default_factory=lambda: [
            "User-Agent",
            "Content-Type"
        ],
        description="Required HTTP headers for webhook requests"
    )
    
    # Logging and monitoring
    log_invalid_signatures: bool = Field(
        default=True,
        description="Log invalid signature attempts"
    )
    
    log_replay_attempts: bool = Field(
        default=True,
        description="Log replay attack attempts"
    )
    
    alert_on_security_violations: bool = Field(
        default=True,
        description="Send alerts on security violations"
    )
    
    @validator('signature_algorithm')
    def validate_signature_algorithm(cls, v):
        """Validate signature algorithm"""
        allowed_algorithms = {'sha1', 'sha256', 'sha512'}
        if v not in allowed_algorithms:
            raise ValueError(f"Signature algorithm must be one of: {allowed_algorithms}")
        return v
    
    @validator('allowed_content_types')
    def validate_content_types(cls, v):
        """Validate content types"""
        if not v:
            raise ValueError("At least one content type must be allowed")
        return v


class GreenAPIWebhookConfig(WebhookSecurityConfig):
    """Specific configuration for Green API webhooks"""
    
    signature_header: str = "X-Green-Api-Signature"
    timestamp_header: str = "X-Green-Api-Timestamp"
    instance_header: str = "X-Green-Api-Instance"
    
    # Green API specific settings
    validate_instance_id: bool = Field(
        default=True,
        description="Validate instance ID in webhook"
    )
    
    require_instance_header: bool = Field(
        default=True,
        description="Require instance ID in header"
    )


class WebhookProviderConfig(BaseModel):
    """Configuration for different webhook providers"""
    
    green_api: GreenAPIWebhookConfig = Field(
        default_factory=GreenAPIWebhookConfig,
        description="Green API webhook configuration"
    )
    
    # Future webhook providers can be added here
    # telegram: TelegramWebhookConfig = Field(...)
    # slack: SlackWebhookConfig = Field(...)


class WebhookSecuritySettings(BaseModel):
    """Main webhook security settings"""
    
    # Global settings
    enabled: bool = Field(
        default=True,
        description="Enable webhook security validation"
    )
    
    strict_mode: bool = Field(
        default=False,
        description="Enable strict security mode (fail on any validation error)"
    )
    
    # Provider configurations
    providers: WebhookProviderConfig = Field(
        default_factory=WebhookProviderConfig,
        description="Provider-specific configurations"
    )
    
    # Security monitoring
    security_monitoring: Dict[str, bool] = Field(
        default_factory=lambda: {
            "log_all_requests": False,
            "log_security_events": True,
            "alert_on_violations": True,
            "track_metrics": True
        },
        description="Security monitoring settings"
    )


# Default configuration instance
default_webhook_security_config = WebhookSecuritySettings()

# Configuration for different environments
WEBHOOK_SECURITY_CONFIGS = {
    "development": WebhookSecuritySettings(
        strict_mode=False,
        providers=WebhookProviderConfig(
            green_api=GreenAPIWebhookConfig(
                timestamp_tolerance_seconds=600,  # 10 minutes for dev
                webhook_rate_limit_per_minute=200,
                alert_on_security_violations=False
            )
        )
    ),
    
    "staging": WebhookSecuritySettings(
        strict_mode=True,
        providers=WebhookProviderConfig(
            green_api=GreenAPIWebhookConfig(
                timestamp_tolerance_seconds=300,  # 5 minutes
                webhook_rate_limit_per_minute=150
            )
        )
    ),
    
    "production": WebhookSecuritySettings(
        strict_mode=True,
        providers=WebhookProviderConfig(
            green_api=GreenAPIWebhookConfig(
                timestamp_tolerance_seconds=300,  # 5 minutes
                webhook_rate_limit_per_minute=100,
                enable_replay_protection=True,
                alert_on_security_violations=True
            )
        )
    )
}


def get_webhook_security_config(environment: str = "production") -> WebhookSecuritySettings:
    """
    Get webhook security configuration for environment
    
    Args:
        environment: Environment name (development, staging, production)
        
    Returns:
        WebhookSecuritySettings: Configuration for the environment
    """
    config = WEBHOOK_SECURITY_CONFIGS.get(environment)
    if not config:
        logger.warning(
            "Unknown environment for webhook security config, using production",
            environment=environment
        )
        config = WEBHOOK_SECURITY_CONFIGS["production"]
    
    logger.info(
        "Loaded webhook security configuration",
        environment=environment,
        strict_mode=config.strict_mode
    )
    
    return config


# Export main classes and functions
__all__ = [
    'WebhookSecurityConfig',
    'GreenAPIWebhookConfig', 
    'WebhookProviderConfig',
    'WebhookSecuritySettings',
    'get_webhook_security_config',
    'default_webhook_security_config'
]
