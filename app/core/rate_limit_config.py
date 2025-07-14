"""
Rate limiting configuration for API endpoints

This module provides comprehensive rate limiting configuration including
per-user, per-hotel, per-endpoint limits with sliding window algorithms.
"""

from typing import Dict, List, Optional, Set, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithms"""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitScope(str, Enum):
    """Rate limiting scopes"""
    GLOBAL = "global"
    PER_IP = "per_ip"
    PER_USER = "per_user"
    PER_HOTEL = "per_hotel"
    PER_ENDPOINT = "per_endpoint"
    COMBINED = "combined"


class RateLimitRule(BaseModel):
    """Individual rate limit rule"""
    
    # Basic rule configuration
    name: str = Field(..., description="Rule name for identification")
    scope: RateLimitScope = Field(..., description="Rate limit scope")
    algorithm: RateLimitAlgorithm = Field(
        default=RateLimitAlgorithm.SLIDING_WINDOW,
        description="Rate limiting algorithm"
    )
    
    # Rate limits
    requests_per_second: Optional[int] = Field(
        None, ge=1, le=1000, description="Requests per second limit"
    )
    requests_per_minute: Optional[int] = Field(
        None, ge=1, le=10000, description="Requests per minute limit"
    )
    requests_per_hour: Optional[int] = Field(
        None, ge=1, le=100000, description="Requests per hour limit"
    )
    requests_per_day: Optional[int] = Field(
        None, ge=1, le=1000000, description="Requests per day limit"
    )
    
    # Burst handling
    burst_limit: Optional[int] = Field(
        None, ge=1, le=100, description="Burst request limit"
    )
    burst_window_seconds: int = Field(
        default=60, ge=1, le=3600, description="Burst window in seconds"
    )
    
    # Rule conditions
    paths: Optional[List[str]] = Field(
        None, description="Specific paths this rule applies to"
    )
    methods: Optional[List[str]] = Field(
        None, description="HTTP methods this rule applies to"
    )
    user_roles: Optional[List[str]] = Field(
        None, description="User roles this rule applies to"
    )
    
    # Exemptions
    exempt_ips: Set[str] = Field(
        default_factory=set, description="IP addresses exempt from this rule"
    )
    exempt_users: Set[str] = Field(
        default_factory=set, description="User IDs exempt from this rule"
    )
    
    # Response configuration
    block_request: bool = Field(
        default=True, description="Block request when limit exceeded"
    )
    custom_error_message: Optional[str] = Field(
        None, description="Custom error message for rate limit exceeded"
    )
    
    @validator('requests_per_second', 'requests_per_minute', 'requests_per_hour', 'requests_per_day')
    def at_least_one_limit(cls, v, values):
        """Ensure at least one rate limit is specified"""
        limits = [
            values.get('requests_per_second'),
            values.get('requests_per_minute'), 
            values.get('requests_per_hour'),
            values.get('requests_per_day'),
            v
        ]
        if not any(limit for limit in limits if limit is not None):
            raise ValueError("At least one rate limit must be specified")
        return v


class EndpointRateLimitConfig(BaseModel):
    """Rate limit configuration for specific endpoints"""
    
    # Webhook endpoints
    webhook_endpoints: Dict[str, RateLimitRule] = Field(
        default_factory=lambda: {
            "/api/v1/webhooks/green-api": RateLimitRule(
                name="green_api_webhook",
                scope=RateLimitScope.PER_IP,
                requests_per_minute=100,
                burst_limit=10,
                paths=["/api/v1/webhooks/green-api", "/webhooks/green-api"]
            )
        }
    )
    
    # Authentication endpoints
    auth_endpoints: Dict[str, RateLimitRule] = Field(
        default_factory=lambda: {
            "/api/v1/auth/login": RateLimitRule(
                name="auth_login",
                scope=RateLimitScope.PER_IP,
                requests_per_minute=10,
                requests_per_hour=50,
                burst_limit=3,
                paths=["/api/v1/auth/login"]
            ),
            "/api/v1/auth/register": RateLimitRule(
                name="auth_register",
                scope=RateLimitScope.PER_IP,
                requests_per_minute=5,
                requests_per_hour=20,
                burst_limit=2,
                paths=["/api/v1/auth/register"]
            )
        }
    )
    
    # API endpoints
    api_endpoints: Dict[str, RateLimitRule] = Field(
        default_factory=lambda: {
            "/api/v1/hotels": RateLimitRule(
                name="hotels_api",
                scope=RateLimitScope.PER_USER,
                requests_per_minute=60,
                requests_per_hour=1000,
                paths=["/api/v1/hotels"]
            ),
            "/api/v1/conversations": RateLimitRule(
                name="conversations_api",
                scope=RateLimitScope.PER_HOTEL,
                requests_per_minute=100,
                requests_per_hour=2000,
                paths=["/api/v1/conversations"]
            )
        }
    )


class UserRoleLimits(BaseModel):
    """Rate limits based on user roles"""
    
    # Admin users
    admin: RateLimitRule = Field(
        default_factory=lambda: RateLimitRule(
            name="admin_user",
            scope=RateLimitScope.PER_USER,
            requests_per_minute=200,
            requests_per_hour=5000,
            burst_limit=50
        )
    )
    
    # Staff users
    staff: RateLimitRule = Field(
        default_factory=lambda: RateLimitRule(
            name="staff_user",
            scope=RateLimitScope.PER_USER,
            requests_per_minute=100,
            requests_per_hour=2000,
            burst_limit=20
        )
    )
    
    # Regular users
    user: RateLimitRule = Field(
        default_factory=lambda: RateLimitRule(
            name="regular_user",
            scope=RateLimitScope.PER_USER,
            requests_per_minute=60,
            requests_per_hour=1000,
            burst_limit=10
        )
    )
    
    # Anonymous/unauthenticated users
    anonymous: RateLimitRule = Field(
        default_factory=lambda: RateLimitRule(
            name="anonymous_user",
            scope=RateLimitScope.PER_IP,
            requests_per_minute=30,
            requests_per_hour=200,
            burst_limit=5
        )
    )


class HotelTierLimits(BaseModel):
    """Rate limits based on hotel subscription tiers"""
    
    # Premium tier hotels
    premium: RateLimitRule = Field(
        default_factory=lambda: RateLimitRule(
            name="premium_hotel",
            scope=RateLimitScope.PER_HOTEL,
            requests_per_minute=500,
            requests_per_hour=10000,
            burst_limit=100
        )
    )
    
    # Standard tier hotels
    standard: RateLimitRule = Field(
        default_factory=lambda: RateLimitRule(
            name="standard_hotel",
            scope=RateLimitScope.PER_HOTEL,
            requests_per_minute=200,
            requests_per_hour=5000,
            burst_limit=50
        )
    )
    
    # Basic tier hotels
    basic: RateLimitRule = Field(
        default_factory=lambda: RateLimitRule(
            name="basic_hotel",
            scope=RateLimitScope.PER_HOTEL,
            requests_per_minute=100,
            requests_per_hour=2000,
            burst_limit=20
        )
    )


class RateLimitConfig(BaseModel):
    """Main rate limiting configuration"""
    
    # Global settings
    enabled: bool = Field(default=True, description="Enable rate limiting")
    strict_mode: bool = Field(
        default=False, description="Strict mode (no exemptions)"
    )
    
    # Storage configuration
    storage_backend: str = Field(
        default="redis", description="Storage backend (redis, memory)"
    )
    key_prefix: str = Field(
        default="rate_limit:", description="Redis key prefix"
    )
    
    # Default limits
    default_global_limit: RateLimitRule = Field(
        default_factory=lambda: RateLimitRule(
            name="global_default",
            scope=RateLimitScope.GLOBAL,
            requests_per_minute=1000,
            requests_per_hour=10000
        )
    )
    
    # Endpoint-specific limits
    endpoints: EndpointRateLimitConfig = Field(
        default_factory=EndpointRateLimitConfig
    )
    
    # User role limits
    user_roles: UserRoleLimits = Field(default_factory=UserRoleLimits)
    
    # Hotel tier limits
    hotel_tiers: HotelTierLimits = Field(default_factory=HotelTierLimits)
    
    # Response headers
    include_rate_limit_headers: bool = Field(
        default=True, description="Include rate limit headers in responses"
    )
    
    header_names: Dict[str, str] = Field(
        default_factory=lambda: {
            "limit": "X-RateLimit-Limit",
            "remaining": "X-RateLimit-Remaining", 
            "reset": "X-RateLimit-Reset",
            "retry_after": "Retry-After"
        }
    )
    
    # Monitoring and logging
    log_rate_limit_hits: bool = Field(
        default=True, description="Log rate limit violations"
    )
    
    alert_on_violations: bool = Field(
        default=True, description="Send alerts on rate limit violations"
    )
    
    track_metrics: bool = Field(
        default=True, description="Track rate limiting metrics"
    )


# Environment-specific configurations
RATE_LIMIT_CONFIGS = {
    "development": RateLimitConfig(
        strict_mode=False,
        default_global_limit=RateLimitRule(
            name="dev_global",
            scope=RateLimitScope.GLOBAL,
            requests_per_minute=2000,  # More lenient for development
            requests_per_hour=20000
        ),
        alert_on_violations=False
    ),
    
    "staging": RateLimitConfig(
        strict_mode=True,
        default_global_limit=RateLimitRule(
            name="staging_global",
            scope=RateLimitScope.GLOBAL,
            requests_per_minute=1500,
            requests_per_hour=15000
        )
    ),
    
    "production": RateLimitConfig(
        strict_mode=True,
        default_global_limit=RateLimitRule(
            name="prod_global",
            scope=RateLimitScope.GLOBAL,
            requests_per_minute=1000,
            requests_per_hour=10000
        ),
        alert_on_violations=True
    )
}


def get_rate_limit_config(environment: str = "production") -> RateLimitConfig:
    """
    Get rate limit configuration for environment
    
    Args:
        environment: Environment name
        
    Returns:
        RateLimitConfig: Configuration for the environment
    """
    config = RATE_LIMIT_CONFIGS.get(environment)
    if not config:
        logger.warning(
            "Unknown environment for rate limit config, using production",
            environment=environment
        )
        config = RATE_LIMIT_CONFIGS["production"]
    
    logger.info(
        "Loaded rate limit configuration",
        environment=environment,
        strict_mode=config.strict_mode,
        enabled=config.enabled
    )
    
    return config


# Export main classes and functions
__all__ = [
    'RateLimitAlgorithm',
    'RateLimitScope', 
    'RateLimitRule',
    'RateLimitConfig',
    'EndpointRateLimitConfig',
    'UserRoleLimits',
    'HotelTierLimits',
    'get_rate_limit_config'
]
