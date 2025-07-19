"""
Guest model for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import Column, String, DateTime, Index, UniqueConstraint, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import re

from app.models.base import TenantBaseModel

class Guest(TenantBaseModel):
    """
    Guest model for storing hotel guest information and preferences
    
    Each guest belongs to a specific hotel (tenant) and has their own
    preferences and interaction history.
    """
    __tablename__ = "guests"
    
    # Foreign key to hotel (inherited hotel_id from TenantBaseModel serves this purpose)
    # But we need to add the actual foreign key constraint
    hotel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hotels.id', ondelete='CASCADE'),
        nullable=False,
        comment="Hotel ID for multi-tenant data isolation"
    )
    
    # Guest contact information
    phone = Column(
        String(20),
        nullable=False,
        comment="Guest's phone number (WhatsApp number)"
    )
    
    name = Column(
        String(255),
        nullable=True,
        comment="Guest's name (optional, can be collected during conversation)"
    )
    
    # Guest preferences and data
    preferences = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default='{}',
        comment="Guest preferences and collected data in JSON format"
    )
    
    # Interaction tracking
    last_interaction = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the last interaction with the guest"
    )
    
    # Table constraints
    __table_args__ = (
        # Unique constraint on hotel_id + phone (one guest per phone per hotel)
        UniqueConstraint('hotel_id', 'phone', name='uq_guests_hotel_phone'),
        
        # Check constraint for phone number format
        CheckConstraint(
            "phone ~ '^\\+?[1-9]\\d{1,14}$'",
            name='ck_guests_phone_format'
        ),
        
        # Indexes for performance
        Index('idx_guests_hotel_id', 'hotel_id'),
        Index('idx_guests_phone', 'phone'),
        Index('idx_guests_hotel_phone', 'hotel_id', 'phone'),
        Index('idx_guests_last_interaction', 'last_interaction'),
        Index('idx_guests_name', 'name'),
        
        # Partial index for guests with names
        Index(
            'idx_guests_with_name',
            'hotel_id', 'name',
            postgresql_where="name IS NOT NULL"
        ),
        
        # Partial index for recent interactions
        Index(
            'idx_guests_recent_interaction',
            'hotel_id', 'last_interaction',
            postgresql_where="last_interaction > NOW() - INTERVAL '30 days'"
        ),
    )
    
    # Relationships
    # Temporarily commented out to resolve circular import issues
    # hotel = relationship("Hotel", back_populates="guests")
    conversations = relationship("Conversation", back_populates="guest", cascade="all, delete-orphan")
    staff_notifications = relationship("StaffNotification", back_populates="guest")
    message_queue = relationship("MessageQueue", back_populates="guest", cascade="all, delete-orphan")
    sentiment_analyses = relationship("SentimentAnalysis", back_populates="guest", cascade="all, delete-orphan")
    staff_alerts = relationship("StaffAlert", back_populates="guest", cascade="all, delete-orphan")
    
    @validates('phone')
    def validate_phone(self, key: str, value: str) -> str:
        """
        Validate phone number format
        
        Args:
            key: Field name
            value: Phone number to validate
            
        Returns:
            str: Validated phone number
            
        Raises:
            ValueError: If the phone number format is invalid
        """
        if not value:
            raise ValueError("Phone number is required")
        
        # Remove any spaces or special characters except +
        cleaned = re.sub(r'[^\d+]', '', value)
        
        # Validate format: optional +, followed by 1-15 digits
        if not re.match(r'^\+?[1-9]\d{1,14}$', cleaned):
            raise ValueError(
                "Invalid phone number format. Must be in international format "
                "(e.g., +1234567890) with 2-15 digits"
            )
        
        # Ensure it starts with + for consistency
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
            
        return cleaned
    
    @validates('name')
    def validate_name(self, key: str, value: Optional[str]) -> Optional[str]:
        """
        Validate guest name
        
        Args:
            key: Field name
            value: Guest name to validate
            
        Returns:
            Optional[str]: Validated guest name or None
            
        Raises:
            ValueError: If the guest name is invalid
        """
        if value is None:
            return None
        
        if not value.strip():
            return None
        
        if len(value.strip()) > 255:
            raise ValueError("Guest name must be less than 255 characters")
        
        return value.strip()
    
    @hybrid_property
    def has_name(self) -> bool:
        """
        Check if guest has a name set
        
        Returns:
            bool: True if guest has a name
        """
        return bool(self.name and self.name.strip())
    
    @hybrid_property
    def is_recent_guest(self) -> bool:
        """
        Check if guest has interacted recently (within 30 days)
        
        Returns:
            bool: True if guest has recent interactions
        """
        if not self.last_interaction:
            return False
        
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        return self.last_interaction > thirty_days_ago
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """
        Get a specific preference value
        
        Args:
            key: Preference key (supports dot notation for nested keys)
            default: Default value if key is not found
            
        Returns:
            Any: Preference value or default
        """
        if not self.preferences:
            return default
        
        # Support dot notation for nested keys
        keys = key.split('.')
        value = self.preferences
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_preference(self, key: str, value: Any) -> None:
        """
        Set a specific preference value
        
        Args:
            key: Preference key (supports dot notation for nested keys)
            value: Preference value
        """
        if not self.preferences:
            self.preferences = {}
        
        # Support dot notation for nested keys
        keys = key.split('.')
        current = self.preferences
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Set the final value
        current[keys[-1]] = value
    
    def update_last_interaction(self) -> None:
        """Update the last interaction timestamp to now"""
        self.last_interaction = datetime.utcnow()
    
    def get_default_preferences(self) -> Dict[str, Any]:
        """
        Get default preferences for a new guest
        
        Returns:
            Dict[str, Any]: Default preferences dictionary
        """
        return {
            "communication": {
                "language": "en",
                "preferred_time": None,
                "timezone": None
            },
            "stay": {
                "room_type_preference": None,
                "special_requests": [],
                "dietary_restrictions": []
            },
            "profile": {
                "vip_status": False,
                "loyalty_tier": "standard",
                "visit_count": 0
            },
            "notifications": {
                "marketing_consent": False,
                "service_updates": True
            }
        }
    
    def apply_default_preferences(self) -> None:
        """Apply default preferences to the guest"""
        if not self.preferences:
            self.preferences = self.get_default_preferences()
        else:
            # Merge with existing preferences, keeping existing values
            defaults = self.get_default_preferences()
            for key, value in defaults.items():
                if key not in self.preferences:
                    self.preferences[key] = value
    
    def increment_visit_count(self) -> int:
        """
        Increment the guest's visit count
        
        Returns:
            int: New visit count
        """
        current_count = self.get_preference('profile.visit_count', 0)
        new_count = current_count + 1
        self.set_preference('profile.visit_count', new_count)
        return new_count
    
    def add_special_request(self, request: str) -> None:
        """
        Add a special request to the guest's preferences
        
        Args:
            request: Special request text
        """
        requests = self.get_preference('stay.special_requests', [])
        if request not in requests:
            requests.append(request)
            self.set_preference('stay.special_requests', requests)
    
    def add_dietary_restriction(self, restriction: str) -> None:
        """
        Add a dietary restriction to the guest's preferences
        
        Args:
            restriction: Dietary restriction text
        """
        restrictions = self.get_preference('stay.dietary_restrictions', [])
        if restriction not in restrictions:
            restrictions.append(restriction)
            self.set_preference('stay.dietary_restrictions', restrictions)
    
    def get_display_name(self) -> str:
        """
        Get display name for the guest (name or phone)
        
        Returns:
            str: Display name
        """
        return self.name if self.has_name else self.phone
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Convert guest to dictionary with optional sensitive data inclusion
        
        Args:
            include_sensitive: Whether to include sensitive preference data
            
        Returns:
            Dict[str, Any]: Guest dictionary representation
        """
        result = super().to_dict()
        
        # Add computed properties
        result['has_name'] = self.has_name
        result['is_recent_guest'] = self.is_recent_guest
        result['display_name'] = self.get_display_name()
        result['visit_count'] = self.get_preference('profile.visit_count', 0)
        
        # Filter sensitive preferences if requested
        if not include_sensitive and self.preferences:
            filtered_prefs = self.preferences.copy()
            # Remove potentially sensitive data
            if 'profile' in filtered_prefs:
                filtered_prefs['profile'].pop('loyalty_tier', None)
            result['preferences'] = filtered_prefs
        
        return result
    
    def __repr__(self) -> str:
        """String representation of the guest"""
        display_name = self.get_display_name()
        return f"<Guest(id={self.id}, hotel_id={self.hotel_id}, name='{display_name}', phone='{self.phone}')>"
