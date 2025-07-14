"""
Hotel configuration schemas for WhatsApp Hotel Bot application
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, validator
import re


class NotificationSettings(BaseModel):
    """Schema for notification settings"""
    
    email_enabled: bool = Field(
        default=True,
        description="Whether email notifications are enabled"
    )
    
    sms_enabled: bool = Field(
        default=False,
        description="Whether SMS notifications are enabled"
    )
    
    webhook_enabled: bool = Field(
        default=False,
        description="Whether webhook notifications are enabled"
    )


class BusinessHoursSettings(BaseModel):
    """Schema for business hours settings"""
    
    enabled: bool = Field(
        default=True,
        description="Whether business hours restrictions are enabled"
    )
    
    start: str = Field(
        default="09:00",
        description="Business hours start time (HH:MM format)"
    )
    
    end: str = Field(
        default="18:00",
        description="Business hours end time (HH:MM format)"
    )
    
    timezone: str = Field(
        default="Asia/Bangkok",
        description="Timezone for business hours"
    )
    
    @validator('start', 'end')
    def validate_time_format(cls, v):
        """Validate time format (HH:MM)"""
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError('Time must be in HH:MM format')
        return v


class AutoResponseSettings(BaseModel):
    """Schema for auto-response settings"""
    
    enabled: bool = Field(
        default=True,
        description="Whether auto-responses are enabled"
    )
    
    greeting_message: str = Field(
        default="Welcome to our hotel! How can we help you today?",
        max_length=1000,
        description="Default greeting message for new conversations"
    )
    
    business_hours: BusinessHoursSettings = Field(
        default_factory=BusinessHoursSettings,
        description="Business hours configuration"
    )


class SentimentAnalysisSettings(BaseModel):
    """Schema for sentiment analysis settings"""
    
    enabled: bool = Field(
        default=True,
        description="Whether sentiment analysis is enabled"
    )
    
    threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Sentiment threshold for triggering alerts (0.0 to 1.0)"
    )
    
    alert_negative: bool = Field(
        default=True,
        description="Whether to alert staff on negative sentiment"
    )


class LanguageSettings(BaseModel):
    """Schema for language settings"""
    
    primary: str = Field(
        default="en",
        description="Primary language code (ISO 639-1)"
    )
    
    supported: List[str] = Field(
        default=["en", "es", "fr"],
        description="List of supported language codes"
    )
    
    @validator('primary')
    def validate_primary_language(cls, v):
        """Validate primary language code"""
        if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', v):
            raise ValueError('Primary language must be a valid language code (e.g., "en", "en-US")')
        return v
    
    @validator('supported')
    def validate_supported_languages(cls, v):
        """Validate supported languages list"""
        for lang in v:
            if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', lang):
                raise ValueError(f'Invalid language code: {lang}')
        return v


class HotelConfigurationSchema(BaseModel):
    """Complete hotel configuration schema"""
    
    notifications: NotificationSettings = Field(
        default_factory=NotificationSettings,
        description="Notification settings"
    )
    
    auto_responses: AutoResponseSettings = Field(
        default_factory=AutoResponseSettings,
        description="Auto-response settings"
    )
    
    sentiment_analysis: SentimentAnalysisSettings = Field(
        default_factory=SentimentAnalysisSettings,
        description="Sentiment analysis settings"
    )
    
    language: LanguageSettings = Field(
        default_factory=LanguageSettings,
        description="Language settings"
    )
    
    advanced: Dict[str, Any] = Field(
        default_factory=dict,
        description="Advanced settings for custom configurations"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "notifications": {
                    "email_enabled": True,
                    "sms_enabled": False,
                    "webhook_enabled": False
                },
                "auto_responses": {
                    "enabled": True,
                    "greeting_message": "Welcome to our hotel! How can we help you today?",
                    "business_hours": {
                        "enabled": True,
                        "start": "09:00",
                        "end": "18:00",
                        "timezone": "Asia/Bangkok"
                    }
                },
                "sentiment_analysis": {
                    "enabled": True,
                    "threshold": 0.3,
                    "alert_negative": True
                },
                "language": {
                    "primary": "en",
                    "supported": ["en", "es", "fr"]
                },
                "advanced": {}
            }
        }
    }


class HotelConfigurationUpdate(BaseModel):
    """Schema for updating hotel configuration"""
    
    notifications: Optional[NotificationSettings] = Field(
        None,
        description="Notification settings to update"
    )
    
    auto_responses: Optional[AutoResponseSettings] = Field(
        None,
        description="Auto-response settings to update"
    )
    
    sentiment_analysis: Optional[SentimentAnalysisSettings] = Field(
        None,
        description="Sentiment analysis settings to update"
    )
    
    language: Optional[LanguageSettings] = Field(
        None,
        description="Language settings to update"
    )
    
    advanced: Optional[Dict[str, Any]] = Field(
        None,
        description="Advanced settings to update"
    )
    
    merge: bool = Field(
        default=True,
        description="Whether to merge with existing settings or replace completely"
    )


class ConfigurationValidationResult(BaseModel):
    """Schema for configuration validation results"""
    
    is_valid: bool = Field(
        ...,
        description="Whether the configuration is valid"
    )
    
    errors: List[str] = Field(
        default_factory=list,
        description="List of validation errors"
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="List of validation warnings"
    )


class ConfigurationTemplate(BaseModel):
    """Schema for configuration templates"""
    
    name: str = Field(
        ...,
        description="Template name"
    )
    
    description: str = Field(
        ...,
        description="Template description"
    )
    
    configuration: HotelConfigurationSchema = Field(
        ...,
        description="Template configuration"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Template tags for categorization"
    )


# Predefined configuration templates
DEFAULT_TEMPLATES = {
    "basic": ConfigurationTemplate(
        name="Basic Configuration",
        description="Basic hotel configuration with essential settings",
        configuration=HotelConfigurationSchema(),
        tags=["basic", "default"]
    ),
    
    "luxury": ConfigurationTemplate(
        name="Luxury Hotel Configuration",
        description="Configuration optimized for luxury hotels with premium service",
        configuration=HotelConfigurationSchema(
            auto_responses=AutoResponseSettings(
                greeting_message="Welcome to our luxury hotel! Our concierge team is here to assist you with any requests.",
                business_hours=BusinessHoursSettings(
                    start="06:00",
                    end="23:00"
                )
            ),
            sentiment_analysis=SentimentAnalysisSettings(
                threshold=0.2,  # More sensitive for luxury service
                alert_negative=True
            )
        ),
        tags=["luxury", "premium", "concierge"]
    ),
    
    "budget": ConfigurationTemplate(
        name="Budget Hotel Configuration",
        description="Configuration optimized for budget hotels with automated responses",
        configuration=HotelConfigurationSchema(
            notifications=NotificationSettings(
                email_enabled=True,
                sms_enabled=False,
                webhook_enabled=False
            ),
            auto_responses=AutoResponseSettings(
                greeting_message="Welcome! For quick assistance, please let us know how we can help you.",
                business_hours=BusinessHoursSettings(
                    start="08:00",
                    end="20:00"
                )
            ),
            sentiment_analysis=SentimentAnalysisSettings(
                threshold=0.4,  # Less sensitive for budget operations
                alert_negative=True
            )
        ),
        tags=["budget", "automated", "efficient"]
    )
}


# Export all schemas
__all__ = [
    'NotificationSettings',
    'BusinessHoursSettings',
    'AutoResponseSettings',
    'SentimentAnalysisSettings',
    'LanguageSettings',
    'HotelConfigurationSchema',
    'HotelConfigurationUpdate',
    'ConfigurationValidationResult',
    'ConfigurationTemplate',
    'DEFAULT_TEMPLATES'
]
