"""
Green API Configuration for WhatsApp Hotel Bot
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from app.core.config import settings
import asyncio


class GreenAPIRetryConfig(BaseModel):
    """Configuration for retry mechanism"""
    max_retries: int = Field(default=3, ge=0, le=10)
    base_delay: float = Field(default=1.0, ge=0.1, le=10.0)
    max_delay: float = Field(default=60.0, ge=1.0, le=300.0)
    exponential_base: float = Field(default=2.0, ge=1.1, le=5.0)
    jitter: bool = Field(default=True)


class GreenAPIRateLimitConfig(BaseModel):
    """Configuration for rate limiting"""
    requests_per_minute: int = Field(default=60, ge=1, le=1000)
    requests_per_second: int = Field(default=2, ge=1, le=10)
    burst_limit: int = Field(default=5, ge=1, le=20)
    
    @validator('requests_per_second')
    def validate_rps_vs_rpm(cls, v, values):
        """Ensure requests per second doesn't exceed requests per minute"""
        if 'requests_per_minute' in values:
            max_rps = values['requests_per_minute'] // 60
            if v > max_rps:
                raise ValueError(f"requests_per_second ({v}) cannot exceed requests_per_minute/60 ({max_rps})")
        return v


class GreenAPITimeoutConfig(BaseModel):
    """Configuration for timeouts"""
    connect_timeout: float = Field(default=10.0, ge=1.0, le=60.0)
    read_timeout: float = Field(default=30.0, ge=5.0, le=120.0)
    write_timeout: float = Field(default=30.0, ge=5.0, le=120.0)
    pool_timeout: float = Field(default=10.0, ge=1.0, le=60.0)


class GreenAPIConfig(BaseModel):
    """Main Green API configuration"""
    
    # Base configuration
    base_url: str = Field(default="https://api.green-api.com")
    api_version: str = Field(default="v1")
    
    # Authentication (will be set per hotel)
    instance_id: Optional[str] = None
    token: Optional[str] = None
    
    # Retry configuration
    retry: GreenAPIRetryConfig = Field(default_factory=GreenAPIRetryConfig)
    
    # Rate limiting configuration
    rate_limit: GreenAPIRateLimitConfig = Field(default_factory=GreenAPIRateLimitConfig)
    
    # Timeout configuration
    timeouts: GreenAPITimeoutConfig = Field(default_factory=GreenAPITimeoutConfig)
    
    # Webhook configuration
    webhook_enabled: bool = Field(default=True)
    webhook_url: Optional[str] = None
    webhook_token: Optional[str] = None
    
    # Message configuration
    default_message_type: str = Field(default="textMessage")
    max_message_length: int = Field(default=4096, ge=1, le=65536)
    
    # File upload configuration
    max_file_size_mb: int = Field(default=100, ge=1, le=500)
    allowed_file_types: list = Field(default_factory=lambda: [
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "video/mp4", "video/avi", "video/mov",
        "audio/mp3", "audio/wav", "audio/ogg",
        "application/pdf", "text/plain"
    ])
    
    # Monitoring configuration
    enable_metrics: bool = Field(default=True)
    enable_detailed_logging: bool = Field(default=True)
    log_request_body: bool = Field(default=False)  # Security: don't log sensitive data by default
    log_response_body: bool = Field(default=False)
    
    @validator('base_url')
    def validate_base_url(cls, v):
        """Validate base URL format"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("base_url must start with http:// or https://")
        if v.endswith('/'):
            v = v.rstrip('/')
        return v
    
    @validator('webhook_url')
    def validate_webhook_url(cls, v):
        """Validate webhook URL format"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError("webhook_url must start with http:// or https://")
        return v
    
    def get_api_url(self, instance_id: Optional[str] = None) -> str:
        """Get full API URL for instance"""
        inst_id = instance_id or self.instance_id
        if not inst_id:
            raise ValueError("instance_id is required")
        return f"{self.base_url}/waInstance{inst_id}"
    
    def get_webhook_url(self, endpoint: str = "webhook") -> Optional[str]:
        """Get webhook URL for this instance"""
        if not self.webhook_url:
            return None
        return f"{self.webhook_url.rstrip('/')}/{endpoint}"
    
    def to_httpx_timeout(self) -> Dict[str, float]:
        """Convert to httpx timeout configuration"""
        return {
            "connect": self.timeouts.connect_timeout,
            "read": self.timeouts.read_timeout,
            "write": self.timeouts.write_timeout,
            "pool": self.timeouts.pool_timeout
        }


class GreenAPIHotelConfig(BaseModel):
    """Per-hotel Green API configuration"""
    hotel_id: str
    instance_id: str
    token: str
    webhook_token: Optional[str] = None
    custom_settings: Dict[str, Any] = Field(default_factory=dict)
    
    # Override global settings if needed
    rate_limit_override: Optional[GreenAPIRateLimitConfig] = None
    timeout_override: Optional[GreenAPITimeoutConfig] = None
    
    def get_effective_config(self, global_config: GreenAPIConfig) -> GreenAPIConfig:
        """Get effective configuration by merging global and hotel-specific settings"""
        config_dict = global_config.dict()
        
        # Set hotel-specific authentication
        config_dict['instance_id'] = self.instance_id
        config_dict['token'] = self.token
        
        # Apply overrides
        if self.rate_limit_override:
            config_dict['rate_limit'] = self.rate_limit_override.dict()
        
        if self.timeout_override:
            config_dict['timeouts'] = self.timeout_override.dict()
        
        # Apply custom settings
        config_dict.update(self.custom_settings)
        
        return GreenAPIConfig(**config_dict)


# Global configuration instance
green_api_config = GreenAPIConfig(
    base_url=settings.GREEN_API_URL,
    instance_id=settings.GREEN_API_INSTANCE_ID,
    token=settings.GREEN_API_TOKEN,
    webhook_url=f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}{settings.API_V1_STR}/webhooks/green-api" if settings.DEBUG else None
)


def get_green_api_config() -> GreenAPIConfig:
    """Get global Green API configuration"""
    return green_api_config


def create_hotel_config(
    hotel_id: str,
    instance_id: str,
    token: str,
    webhook_token: Optional[str] = None,
    **custom_settings
) -> GreenAPIHotelConfig:
    """Create hotel-specific Green API configuration"""
    return GreenAPIHotelConfig(
        hotel_id=hotel_id,
        instance_id=instance_id,
        token=token,
        webhook_token=webhook_token,
        custom_settings=custom_settings
    )


# Configuration validation
def validate_green_api_config(config: GreenAPIConfig) -> None:
    """Validate Green API configuration"""
    errors = []
    
    if not config.instance_id:
        errors.append("instance_id is required")
    
    if not config.token:
        errors.append("token is required")
    
    if config.webhook_enabled and not config.webhook_url:
        errors.append("webhook_url is required when webhook_enabled is True")
    
    if errors:
        raise ValueError(f"Green API configuration errors: {', '.join(errors)}")


# Export main components
__all__ = [
    'GreenAPIConfig',
    'GreenAPIHotelConfig', 
    'GreenAPIRetryConfig',
    'GreenAPIRateLimitConfig',
    'GreenAPITimeoutConfig',
    'green_api_config',
    'get_green_api_config',
    'create_hotel_config',
    'validate_green_api_config'
]
