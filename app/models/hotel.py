"""
Hotel model for WhatsApp Hotel Bot application
"""

import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, Boolean, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import re

from app.models.base import BaseModel

class Hotel(BaseModel):
    """
    Hotel model for multi-tenant WhatsApp bot system
    
    Each hotel represents a tenant in the multi-tenant architecture.
    Hotels have their own WhatsApp integration and settings.
    """
    __tablename__ = "hotels"
    
    # Basic hotel information
    name = Column(
        String(255),
        nullable=False,
        comment="Hotel name"
    )
    
    # WhatsApp integration fields
    whatsapp_number = Column(
        String(20),
        nullable=False,
        unique=True,
        comment="WhatsApp phone number for the hotel"
    )
    
    # Green API credentials
    green_api_instance_id = Column(
        String(50),
        nullable=True,
        comment="Green API instance ID for WhatsApp integration"
    )
    
    green_api_token = Column(
        String(255),
        nullable=True,
        comment="Green API token for WhatsApp integration"
    )

    green_api_webhook_token = Column(
        String(255),
        nullable=True,
        comment="Green API webhook token for secure webhook validation"
    )
    
    # Hotel settings and configuration
    settings = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default='{}',
        comment="Hotel-specific settings and configuration in JSON format"
    )
    
    # Status and control fields
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the hotel is active and can receive messages"
    )
    
    # Table constraints
    __table_args__ = (
        # Unique constraint on WhatsApp number
        UniqueConstraint('whatsapp_number', name='uq_hotels_whatsapp_number'),
        
        # Check constraint for WhatsApp number format
        CheckConstraint(
            "whatsapp_number ~ '^\\+?[1-9]\\d{1,14}$'",
            name='ck_hotels_whatsapp_number_format'
        ),
        
        # Index for active hotels
        Index('idx_hotels_active', 'is_active'),
        
        # Index for WhatsApp number lookups
        Index('idx_hotels_whatsapp_number', 'whatsapp_number'),
        
        # Partial index for active hotels with Green API credentials
        Index(
            'idx_hotels_active_with_api',
            'is_active', 'green_api_instance_id',
            postgresql_where="is_active = true AND green_api_instance_id IS NOT NULL"
        ),
    )
    
    # Relationships (using lazy loading to avoid circular imports)
    # Temporarily commented out to resolve circular import issues
    # settings_record = relationship("HotelSettings", back_populates="hotel", uselist=False, cascade="all, delete-orphan", lazy="select")
    # guests = relationship("Guest", back_populates="hotel", cascade="all, delete-orphan", lazy="select")
    
    @validates('whatsapp_number')
    def validate_whatsapp_number(self, key: str, value: str) -> str:
        """
        Validate WhatsApp number format
        
        Args:
            key: Field name
            value: WhatsApp number to validate
            
        Returns:
            str: Validated WhatsApp number
            
        Raises:
            ValueError: If the WhatsApp number format is invalid
        """
        if not value:
            raise ValueError("WhatsApp number is required")
        
        # Remove any spaces or special characters except +
        cleaned = re.sub(r'[^\d+]', '', value)
        
        # Validate format: optional +, followed by 1-15 digits
        if not re.match(r'^\+?[1-9]\d{1,14}$', cleaned):
            raise ValueError(
                "Invalid WhatsApp number format. Must be in international format "
                "(e.g., +1234567890) with 2-15 digits"
            )
        
        # Ensure it starts with + for consistency
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
            
        return cleaned
    
    @validates('name')
    def validate_name(self, key: str, value: str) -> str:
        """
        Validate hotel name
        
        Args:
            key: Field name
            value: Hotel name to validate
            
        Returns:
            str: Validated hotel name
            
        Raises:
            ValueError: If the hotel name is invalid
        """
        if not value or not value.strip():
            raise ValueError("Hotel name is required")
        
        if len(value.strip()) < 2:
            raise ValueError("Hotel name must be at least 2 characters long")
        
        if len(value.strip()) > 255:
            raise ValueError("Hotel name must be less than 255 characters")
        
        return value.strip()
    
    @hybrid_property
    def has_green_api_credentials(self) -> bool:
        """
        Check if hotel has Green API credentials configured
        
        Returns:
            bool: True if both instance ID and token are set
        """
        return bool(self.green_api_instance_id and self.green_api_token)
    
    @hybrid_property
    def is_operational(self) -> bool:
        """
        Check if hotel is operational (active and has API credentials)
        
        Returns:
            bool: True if hotel can send/receive messages
        """
        return self.is_active and self.has_green_api_credentials
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a specific setting value
        
        Args:
            key: Setting key (supports dot notation for nested keys)
            default: Default value if key is not found
            
        Returns:
            Any: Setting value or default
        """
        if not self.settings:
            return default
        
        # Support dot notation for nested keys
        keys = key.split('.')
        value = self.settings
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_setting(self, key: str, value: Any) -> None:
        """
        Set a specific setting value
        
        Args:
            key: Setting key (supports dot notation for nested keys)
            value: Setting value
        """
        if not self.settings:
            self.settings = {}
        
        # Support dot notation for nested keys
        keys = key.split('.')
        current = self.settings
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Set the final value
        current[keys[-1]] = value
    
    def get_default_settings(self) -> Dict[str, Any]:
        """
        Get default settings for a new hotel

        Returns:
            Dict[str, Any]: Default settings dictionary
        """
        return {
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
                    "timezone": "UTC"
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
            "green_api": {
                "webhook_enabled": True,
                "incoming_webhook": True,
                "outgoing_webhook": True,
                "rate_limit": {
                    "requests_per_minute": 50,
                    "requests_per_second": 2,
                    "burst_limit": 10
                },
                "timeouts": {
                    "connect": 10,
                    "read": 30,
                    "write": 10,
                    "pool": 60
                },
                "retry": {
                    "max_attempts": 3,
                    "base_delay": 1.0,
                    "max_delay": 60.0,
                    "exponential_base": 2.0
                }
            },
            "deepseek": {
                "enabled": True,
                "model": "deepseek-chat",
                "max_tokens": 4096,
                "temperature": 0.7,
                "timeout": 60,
                "max_requests_per_minute": 50,
                "max_tokens_per_minute": 100000,
                "cache_enabled": True,
                "cache_ttl": 3600,
                "sentiment_analysis": {
                    "enabled": True,
                    "threshold": 0.3,
                    "confidence_threshold": 0.7
                },
                "response_generation": {
                    "max_response_tokens": 500,
                    "response_temperature": 0.8,
                    "max_context_messages": 10,
                    "include_guest_history": True,
                    "use_hotel_branding": True
                },
                "prompts": {
                    "system_prompt": "You are a helpful hotel assistant. Respond professionally and courteously to guest inquiries.",
                    "greeting_prompt": "Greet the guest warmly and ask how you can assist them.",
                    "escalation_prompt": "This conversation needs human attention. Please transfer to staff."
                }
            }
        }
    
    def apply_default_settings(self) -> None:
        """Apply default settings to the hotel"""
        if not self.settings:
            self.settings = self.get_default_settings()
        else:
            # Merge with existing settings, keeping existing values
            defaults = self.get_default_settings()
            for key, value in defaults.items():
                if key not in self.settings:
                    self.settings[key] = value
    
    def to_dict(self, include_credentials: bool = False) -> Dict[str, Any]:
        """
        Convert hotel to dictionary with optional credential inclusion
        
        Args:
            include_credentials: Whether to include API credentials
            
        Returns:
            Dict[str, Any]: Hotel dictionary representation
        """
        exclude_fields = set()
        if not include_credentials:
            exclude_fields.update(['green_api_token'])
        
        result = super().to_dict(exclude_fields=exclude_fields)
        
        # Add computed properties
        result['has_green_api_credentials'] = self.has_green_api_credentials
        result['is_operational'] = self.is_operational
        
        return result

    def get_green_api_settings(self) -> Dict[str, Any]:
        """
        Get Green API specific settings for this hotel

        Returns:
            Dict[str, Any]: Green API settings
        """
        return self.settings.get("green_api", self.get_default_settings()["green_api"])

    def update_green_api_settings(self, green_api_settings: Dict[str, Any]) -> None:
        """
        Update Green API settings for this hotel

        Args:
            green_api_settings: New Green API settings
        """
        if not self.settings:
            self.settings = self.get_default_settings()

        self.settings["green_api"] = {
            **self.settings.get("green_api", {}),
            **green_api_settings
        }

    def get_deepseek_settings(self) -> Dict[str, Any]:
        """
        Get DeepSeek AI specific settings for this hotel

        Returns:
            Dict[str, Any]: DeepSeek settings
        """
        return self.settings.get("deepseek", self.get_default_settings()["deepseek"])

    def update_deepseek_settings(self, deepseek_settings: Dict[str, Any]) -> None:
        """
        Update DeepSeek AI settings for this hotel

        Args:
            deepseek_settings: New DeepSeek settings
        """
        if not self.settings:
            self.settings = self.get_default_settings()

        self.settings["deepseek"] = {
            **self.settings.get("deepseek", {}),
            **deepseek_settings
        }

    def get_deepseek_api_key(self) -> Optional[str]:
        """
        Get DeepSeek API key for this hotel

        Returns:
            Optional[str]: DeepSeek API key if configured
        """
        deepseek_settings = self.get_deepseek_settings()
        return deepseek_settings.get("api_key")

    def set_deepseek_api_key(self, api_key: str) -> None:
        """
        Set DeepSeek API key for this hotel

        Args:
            api_key: DeepSeek API key
        """
        deepseek_settings = self.get_deepseek_settings()
        deepseek_settings["api_key"] = api_key
        self.update_deepseek_settings(deepseek_settings)

    def has_deepseek_credentials(self) -> bool:
        """
        Check if hotel has DeepSeek API credentials configured

        Returns:
            bool: True if API key is set
        """
        return bool(self.get_deepseek_api_key())

    def is_green_api_configured(self) -> bool:
        """
        Check if Green API is properly configured for this hotel

        Returns:
            bool: True if all required Green API settings are present
        """
        return self.has_green_api_credentials

    def is_deepseek_configured(self) -> bool:
        """
        Check if DeepSeek AI is properly configured for this hotel

        Returns:
            bool: True if DeepSeek is enabled and has API key
        """
        deepseek_settings = self.get_deepseek_settings()
        return (
            deepseek_settings.get("enabled", False) and
            bool(deepseek_settings.get("api_key"))
        )

    def is_fully_configured(self) -> bool:
        """
        Check if hotel is fully configured for operation

        Returns:
            bool: True if both Green API and DeepSeek are configured
        """
        return (
            self.is_active and
            self.is_green_api_configured() and
            self.is_deepseek_configured()
        )

    def __repr__(self) -> str:
        """String representation of the hotel"""
        return f"<Hotel(id={self.id}, name='{self.name}', whatsapp='{self.whatsapp_number}', active={self.is_active})>"
