"""
Hotel schemas for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator
import re

from app.validators.security_validators import (
    SecureBaseModel,
    SafeStr,
    SafePhone,
    validate_safe_text,
    validate_safe_phone
)


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields in schemas"""
    created_at: datetime = Field(..., description="Timestamp when the record was created")
    updated_at: datetime = Field(..., description="Timestamp when the record was last updated")


class HotelBase(SecureBaseModel):
    """Base hotel schema with common fields and security validation"""

    name: SafeStr = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Hotel name"
    )

    whatsapp_number: SafePhone = Field(
        ...,
        min_length=8,
        max_length=20,
        description="WhatsApp phone number for the hotel"
    )

    @field_validator('whatsapp_number')
    @classmethod
    def validate_whatsapp_number(cls, v):
        """Enhanced WhatsApp number validation with security"""
        # SafePhone already handles basic validation, add additional checks
        if not v.startswith('+'):
            raise ValueError('WhatsApp number must include country code with +')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Enhanced hotel name validation with security"""
        # SafeStr already handles sanitization, add business logic validation
        if len(v.strip()) < 2:
            raise ValueError('Hotel name must be at least 2 characters')
        return v


class HotelCreate(HotelBase):
    """Schema for creating a new hotel"""
    
    green_api_instance_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Green API instance ID for WhatsApp integration"
    )
    
    green_api_token: Optional[str] = Field(
        None,
        max_length=255,
        description="Green API token for WhatsApp integration"
    )
    
    green_api_webhook_token: Optional[str] = Field(
        None,
        max_length=255,
        description="Green API webhook token for secure webhook validation"
    )
    
    settings: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Hotel-specific settings and configuration"
    )

    deepseek_api_key: Optional[str] = Field(
        None,
        max_length=255,
        description="DeepSeek API key for this hotel (stored in settings)"
    )
    
    is_active: bool = Field(
        default=True,
        description="Whether the hotel is active and can receive messages"
    )
    
    @model_validator(mode='before')
    @classmethod
    def validate_green_api_credentials(cls, values):
        """Validate Green API credentials consistency"""
        instance_id = values.get('green_api_instance_id')
        token = values.get('green_api_token')

        # If one is provided, both should be provided
        if (instance_id and not token) or (token and not instance_id):
            raise ValueError('Both Green API instance ID and token must be provided together')

        return values


class HotelUpdate(BaseModel):
    """Schema for updating an existing hotel"""
    
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Hotel name"
    )
    
    whatsapp_number: Optional[str] = Field(
        None,
        min_length=8,
        max_length=20,
        description="WhatsApp phone number for the hotel"
    )
    
    green_api_instance_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Green API instance ID for WhatsApp integration"
    )
    
    green_api_token: Optional[str] = Field(
        None,
        max_length=255,
        description="Green API token for WhatsApp integration"
    )
    
    green_api_webhook_token: Optional[str] = Field(
        None,
        max_length=255,
        description="Green API webhook token for secure webhook validation"
    )
    
    settings: Optional[Dict[str, Any]] = Field(
        None,
        description="Hotel-specific settings and configuration"
    )
    
    is_active: Optional[bool] = Field(
        None,
        description="Whether the hotel is active and can receive messages"
    )
    
    @field_validator('whatsapp_number')
    @classmethod
    def validate_whatsapp_number(cls, v):
        """Validate WhatsApp number format"""
        if v is not None and not re.match(r'^\+?[1-9]\d{1,14}$', v):
            raise ValueError('Invalid WhatsApp number format')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate hotel name"""
        if v is not None and not v.strip():
            raise ValueError('Hotel name cannot be empty')
        return v.strip() if v else v


class HotelResponse(HotelBase, TimestampMixin):
    """Schema for hotel response"""
    
    id: uuid.UUID = Field(..., description="Hotel unique identifier")
    
    green_api_instance_id: Optional[str] = Field(
        None,
        description="Green API instance ID for WhatsApp integration"
    )
    
    # Note: We don't expose tokens in responses for security
    has_green_api_credentials: bool = Field(
        ...,
        description="Whether hotel has Green API credentials configured"
    )
    
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Hotel-specific settings and configuration"
    )
    
    is_active: bool = Field(
        ...,
        description="Whether the hotel is active and can receive messages"
    )
    
    is_operational: bool = Field(
        ...,
        description="Whether hotel can send/receive messages (active + has credentials)"
    )
    
    class Config:
        from_attributes = True


class HotelListResponse(BaseModel):
    """Schema for paginated hotel list response"""
    
    hotels: List[HotelResponse] = Field(..., description="List of hotels")
    total: int = Field(..., description="Total number of hotels")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")
    
    class Config:
        from_attributes = True


class HotelSearchParams(BaseModel):
    """Schema for hotel search parameters"""
    
    name: Optional[str] = Field(
        None,
        description="Search by hotel name (partial match)"
    )
    
    whatsapp_number: Optional[str] = Field(
        None,
        description="Search by WhatsApp number (exact match)"
    )
    
    is_active: Optional[bool] = Field(
        None,
        description="Filter by active status"
    )
    
    has_credentials: Optional[bool] = Field(
        None,
        description="Filter by Green API credentials presence"
    )
    
    page: int = Field(
        default=1,
        ge=1,
        description="Page number"
    )
    
    size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Page size"
    )
    
    sort_by: str = Field(
        default="name",
        description="Sort field (name, created_at, updated_at)"
    )
    
    sort_order: str = Field(
        default="asc",
        description="Sort order (asc, desc)"
    )
    
    @field_validator('sort_by')
    @classmethod
    def validate_sort_by(cls, v):
        """Validate sort field"""
        allowed_fields = ['name', 'created_at', 'updated_at', 'whatsapp_number']
        if v not in allowed_fields:
            raise ValueError(f'Sort field must be one of: {", ".join(allowed_fields)}')
        return v
    
    @field_validator('sort_order')
    @classmethod
    def validate_sort_order(cls, v):
        """Validate sort order"""
        if v.lower() not in ['asc', 'desc']:
            raise ValueError('Sort order must be "asc" or "desc"')
        return v.lower()


class HotelConfigUpdate(BaseModel):
    """Schema for updating hotel configuration"""
    
    settings: Dict[str, Any] = Field(
        ...,
        description="Hotel settings to update"
    )
    
    merge: bool = Field(
        default=True,
        description="Whether to merge with existing settings or replace completely"
    )


class HotelStatusUpdate(BaseModel):
    """Schema for updating hotel status"""
    
    is_active: bool = Field(
        ...,
        description="Whether the hotel should be active"
    )
    
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for status change"
    )


# Green API Configuration Schemas
class GreenAPISettings(BaseModel):
    """Green API settings schema"""
    webhook_enabled: bool = Field(default=True, description="Enable webhook for this hotel")
    incoming_webhook: bool = Field(default=True, description="Enable incoming message webhooks")
    outgoing_webhook: bool = Field(default=True, description="Enable outgoing message webhooks")
    rate_limit: Dict[str, Any] = Field(
        default_factory=lambda: {
            "requests_per_minute": 50,
            "requests_per_second": 2,
            "burst_limit": 10
        },
        description="Rate limiting settings"
    )
    timeouts: Dict[str, Any] = Field(
        default_factory=lambda: {
            "connect": 10,
            "read": 30,
            "write": 10,
            "pool": 60
        },
        description="Timeout settings"
    )


# DeepSeek Configuration Schemas
class DeepSeekSettings(BaseModel):
    """DeepSeek AI settings schema"""
    enabled: bool = Field(default=True, description="Enable DeepSeek AI for this hotel")
    api_key: Optional[str] = Field(None, description="DeepSeek API key")
    model: str = Field(default="deepseek-chat", description="DeepSeek model to use")
    max_tokens: int = Field(default=4096, ge=1, le=8192, description="Maximum tokens per request")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    timeout: int = Field(default=60, ge=1, le=300, description="Request timeout in seconds")
    max_requests_per_minute: int = Field(default=50, ge=1, description="Rate limit per minute")
    max_tokens_per_minute: int = Field(default=100000, ge=1000, description="Token limit per minute")
    cache_enabled: bool = Field(default=True, description="Enable response caching")
    cache_ttl: int = Field(default=3600, ge=60, description="Cache TTL in seconds")

    sentiment_analysis: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": True,
            "threshold": 0.3,
            "confidence_threshold": 0.7
        },
        description="Sentiment analysis settings"
    )

    response_generation: Dict[str, Any] = Field(
        default_factory=lambda: {
            "max_response_tokens": 500,
            "response_temperature": 0.8,
            "max_context_messages": 10,
            "include_guest_history": True,
            "use_hotel_branding": True
        },
        description="Response generation settings"
    )

    prompts: Dict[str, str] = Field(
        default_factory=lambda: {
            "system_prompt": "You are a helpful hotel assistant. Respond professionally and courteously to guest inquiries.",
            "greeting_prompt": "Greet the guest warmly and ask how you can assist them.",
            "escalation_prompt": "This conversation needs human attention. Please transfer to staff."
        },
        description="Custom prompts for this hotel"
    )


class HotelSettingsUpdate(BaseModel):
    """Schema for updating hotel settings"""
    green_api: Optional[GreenAPISettings] = Field(None, description="Green API settings")
    deepseek: Optional[DeepSeekSettings] = Field(None, description="DeepSeek AI settings")
    notifications: Optional[Dict[str, Any]] = Field(None, description="Notification settings")
    auto_responses: Optional[Dict[str, Any]] = Field(None, description="Auto response settings")
    sentiment_analysis: Optional[Dict[str, Any]] = Field(None, description="Sentiment analysis settings")
    language: Optional[Dict[str, Any]] = Field(None, description="Language settings")


class HotelConfigurationResponse(BaseModel):
    """Response schema for hotel configuration"""
    hotel_id: uuid.UUID = Field(..., description="Hotel ID")
    green_api_configured: bool = Field(..., description="Whether Green API is configured")
    deepseek_configured: bool = Field(..., description="Whether DeepSeek is configured")
    fully_configured: bool = Field(..., description="Whether hotel is fully configured")
    settings: Dict[str, Any] = Field(..., description="Current hotel settings")


# Export all schemas
__all__ = [
    'HotelBase',
    'HotelCreate',
    'HotelUpdate',
    'HotelResponse',
    'HotelListResponse',
    'HotelSearchParams',
    'HotelConfigUpdate',
    'HotelStatusUpdate',
    'GreenAPISettings',
    'DeepSeekSettings',
    'HotelSettingsUpdate',
    'HotelConfigurationResponse'
]
