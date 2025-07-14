"""
Hotel settings model for WhatsApp Hotel Bot application
"""

import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, Boolean, Integer, Float, Index, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, validates
from datetime import time
import re

from app.models.base import TenantBaseModel


class HotelSettings(TenantBaseModel):
    """
    Hotel settings model for storing structured configuration
    
    This model provides a structured way to store hotel settings
    with proper validation and type safety.
    """
    __tablename__ = "hotel_settings"
    
    # Foreign key to hotel
    hotel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hotels.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # One settings record per hotel
        comment="Hotel ID for settings association"
    )
    
    # Notification settings
    email_notifications_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether email notifications are enabled"
    )
    
    sms_notifications_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether SMS notifications are enabled"
    )
    
    webhook_notifications_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether webhook notifications are enabled"
    )
    
    # Auto-response settings
    auto_responses_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether auto-responses are enabled"
    )
    
    greeting_message = Column(
        String(1000),
        nullable=True,
        default="Welcome to our hotel! How can we help you today?",
        comment="Default greeting message for new conversations"
    )
    
    # Business hours settings
    business_hours_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether business hours restrictions are enabled"
    )
    
    business_hours_start = Column(
        String(5),  # Format: "HH:MM"
        nullable=True,
        default="09:00",
        comment="Business hours start time (24-hour format)"
    )
    
    business_hours_end = Column(
        String(5),  # Format: "HH:MM"
        nullable=True,
        default="18:00",
        comment="Business hours end time (24-hour format)"
    )
    
    business_hours_timezone = Column(
        String(50),
        nullable=False,
        default="UTC",
        comment="Timezone for business hours"
    )
    
    # Sentiment analysis settings
    sentiment_analysis_enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether sentiment analysis is enabled"
    )
    
    sentiment_threshold = Column(
        Float,
        nullable=False,
        default=0.3,
        comment="Sentiment threshold for triggering alerts (0.0 to 1.0)"
    )
    
    alert_on_negative_sentiment = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether to alert staff on negative sentiment"
    )
    
    # Language settings
    primary_language = Column(
        String(10),
        nullable=False,
        default="en",
        comment="Primary language code (ISO 639-1)"
    )
    
    supported_languages = Column(
        JSONB,
        nullable=False,
        default=["en", "es", "fr"],
        server_default='["en", "es", "fr"]',
        comment="List of supported language codes"
    )
    
    # Advanced settings (stored as JSONB for flexibility)
    advanced_settings = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default='{}',
        comment="Advanced settings in JSON format"
    )
    
    # Table constraints and indexes
    __table_args__ = (
        # Index for hotel lookup
        Index('idx_hotel_settings_hotel_id', 'hotel_id'),
        
        # Index for settings queries
        Index('idx_hotel_settings_auto_responses', 'auto_responses_enabled'),
        Index('idx_hotel_settings_sentiment', 'sentiment_analysis_enabled'),
        Index('idx_hotel_settings_language', 'primary_language'),
    )
    
    # Relationships
    # Temporarily commented out to resolve circular import issues
    # hotel = relationship("Hotel", back_populates="settings_record")
    
    @validates('business_hours_start', 'business_hours_end')
    def validate_time_format(self, key, value):
        """Validate time format (HH:MM)"""
        if value is not None:
            if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', value):
                raise ValueError(f"{key} must be in HH:MM format")
        return value
    
    @validates('sentiment_threshold')
    def validate_sentiment_threshold(self, key, value):
        """Validate sentiment threshold is between 0 and 1"""
        if value is not None:
            if not 0.0 <= value <= 1.0:
                raise ValueError("sentiment_threshold must be between 0.0 and 1.0")
        return value
    
    @validates('primary_language')
    def validate_primary_language(self, key, value):
        """Validate primary language code"""
        if value is not None:
            if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', value):
                raise ValueError("primary_language must be a valid language code (e.g., 'en', 'en-US')")
        return value
    
    @validates('supported_languages')
    def validate_supported_languages(self, key, value):
        """Validate supported languages list"""
        if value is not None:
            if not isinstance(value, list):
                raise ValueError("supported_languages must be a list")
            for lang in value:
                if not isinstance(lang, str) or not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', lang):
                    raise ValueError(f"Invalid language code: {lang}")
        return value
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert settings to dictionary format
        
        Returns:
            Dict[str, Any]: Settings as dictionary
        """
        return {
            "notifications": {
                "email_enabled": self.email_notifications_enabled,
                "sms_enabled": self.sms_notifications_enabled,
                "webhook_enabled": self.webhook_notifications_enabled
            },
            "auto_responses": {
                "enabled": self.auto_responses_enabled,
                "greeting_message": self.greeting_message,
                "business_hours": {
                    "enabled": self.business_hours_enabled,
                    "start": self.business_hours_start,
                    "end": self.business_hours_end,
                    "timezone": self.business_hours_timezone
                }
            },
            "sentiment_analysis": {
                "enabled": self.sentiment_analysis_enabled,
                "threshold": self.sentiment_threshold,
                "alert_negative": self.alert_on_negative_sentiment
            },
            "language": {
                "primary": self.primary_language,
                "supported": self.supported_languages
            },
            "advanced": self.advanced_settings
        }
    
    @classmethod
    def from_dict(cls, hotel_id: uuid.UUID, settings_dict: Dict[str, Any]) -> 'HotelSettings':
        """
        Create HotelSettings instance from dictionary
        
        Args:
            hotel_id: Hotel UUID
            settings_dict: Settings dictionary
            
        Returns:
            HotelSettings: New settings instance
        """
        # Extract nested settings with defaults
        notifications = settings_dict.get("notifications", {})
        auto_responses = settings_dict.get("auto_responses", {})
        business_hours = auto_responses.get("business_hours", {})
        sentiment = settings_dict.get("sentiment_analysis", {})
        language = settings_dict.get("language", {})
        advanced = settings_dict.get("advanced", {})
        
        return cls(
            hotel_id=hotel_id,
            email_notifications_enabled=notifications.get("email_enabled", True),
            sms_notifications_enabled=notifications.get("sms_enabled", False),
            webhook_notifications_enabled=notifications.get("webhook_enabled", False),
            auto_responses_enabled=auto_responses.get("enabled", True),
            greeting_message=auto_responses.get("greeting_message", "Welcome to our hotel! How can we help you today?"),
            business_hours_enabled=business_hours.get("enabled", True),
            business_hours_start=business_hours.get("start", "09:00"),
            business_hours_end=business_hours.get("end", "18:00"),
            business_hours_timezone=business_hours.get("timezone", "UTC"),
            sentiment_analysis_enabled=sentiment.get("enabled", True),
            sentiment_threshold=sentiment.get("threshold", 0.3),
            alert_on_negative_sentiment=sentiment.get("alert_negative", True),
            primary_language=language.get("primary", "en"),
            supported_languages=language.get("supported", ["en", "es", "fr"]),
            advanced_settings=advanced
        )
    
    def update_from_dict(self, settings_dict: Dict[str, Any]) -> None:
        """
        Update settings from dictionary
        
        Args:
            settings_dict: Settings dictionary with updates
        """
        # Update notifications
        if "notifications" in settings_dict:
            notifications = settings_dict["notifications"]
            if "email_enabled" in notifications:
                self.email_notifications_enabled = notifications["email_enabled"]
            if "sms_enabled" in notifications:
                self.sms_notifications_enabled = notifications["sms_enabled"]
            if "webhook_enabled" in notifications:
                self.webhook_notifications_enabled = notifications["webhook_enabled"]
        
        # Update auto responses
        if "auto_responses" in settings_dict:
            auto_responses = settings_dict["auto_responses"]
            if "enabled" in auto_responses:
                self.auto_responses_enabled = auto_responses["enabled"]
            if "greeting_message" in auto_responses:
                self.greeting_message = auto_responses["greeting_message"]
            
            # Update business hours
            if "business_hours" in auto_responses:
                business_hours = auto_responses["business_hours"]
                if "enabled" in business_hours:
                    self.business_hours_enabled = business_hours["enabled"]
                if "start" in business_hours:
                    self.business_hours_start = business_hours["start"]
                if "end" in business_hours:
                    self.business_hours_end = business_hours["end"]
                if "timezone" in business_hours:
                    self.business_hours_timezone = business_hours["timezone"]
        
        # Update sentiment analysis
        if "sentiment_analysis" in settings_dict:
            sentiment = settings_dict["sentiment_analysis"]
            if "enabled" in sentiment:
                self.sentiment_analysis_enabled = sentiment["enabled"]
            if "threshold" in sentiment:
                self.sentiment_threshold = sentiment["threshold"]
            if "alert_negative" in sentiment:
                self.alert_on_negative_sentiment = sentiment["alert_negative"]
        
        # Update language settings
        if "language" in settings_dict:
            language = settings_dict["language"]
            if "primary" in language:
                self.primary_language = language["primary"]
            if "supported" in language:
                self.supported_languages = language["supported"]
        
        # Update advanced settings
        if "advanced" in settings_dict:
            self.advanced_settings = settings_dict["advanced"]
