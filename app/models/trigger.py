"""
Trigger model for WhatsApp Hotel Bot application
"""

import uuid
from datetime import datetime, time
from typing import Dict, Any, Optional, List, Union
from sqlalchemy import Column, String, Text, Integer, Boolean, Index, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy import JSON
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import enum

from app.models.base import TenantBaseModel

class TriggerType(enum.Enum):
    """Enumeration of trigger types"""
    TIME_BASED = "time_based"
    CONDITION_BASED = "condition_based"
    EVENT_BASED = "event_based"

# Create PostgreSQL ENUM type
trigger_type_enum = ENUM(
    TriggerType,
    name='trigger_type',
    create_type=True,
    checkfirst=True
)

class Trigger(TenantBaseModel):
    """
    Trigger model for automated message sending based on conditions
    
    Triggers define when and how automated messages should be sent to guests.
    They can be time-based, condition-based, or event-based.
    """
    __tablename__ = "triggers"
    
    # Foreign key to hotel
    hotel_id = Column(
        UUID(as_uuid=True),
        ForeignKey('hotels.id', ondelete='CASCADE'),
        nullable=False,
        comment="Hotel ID for multi-tenant data isolation"
    )
    
    # Trigger identification
    name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name for the trigger"
    )
    
    # Trigger type
    trigger_type = Column(
        trigger_type_enum,
        nullable=False,
        comment="Type of trigger (time_based, condition_based, event_based)"
    )
    
    # Trigger conditions and configuration
    conditions = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default='{}',
        comment="Trigger conditions and configuration in JSON format"
    )
    
    # Message content
    message_template = Column(
        Text,
        nullable=False,
        comment="Message template to send when trigger fires"
    )
    
    # Trigger control
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the trigger is active"
    )
    
    priority = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Trigger priority (1 = highest, higher numbers = lower priority)"
    )
    
    # Table constraints
    __table_args__ = (
        # Check constraint for priority range
        CheckConstraint(
            "priority >= 1 AND priority <= 10",
            name='ck_triggers_priority_range'
        ),
        
        # Indexes for performance
        Index('idx_triggers_hotel_id', 'hotel_id'),
        Index('idx_triggers_type', 'trigger_type'),
        Index('idx_triggers_active', 'is_active'),
        Index('idx_triggers_priority', 'priority'),
        Index('idx_triggers_hotel_active', 'hotel_id', 'is_active'),
        Index('idx_triggers_hotel_type', 'hotel_id', 'trigger_type'),
        
        # Partial index for active triggers
        Index(
            'idx_triggers_active_by_priority',
            'hotel_id', 'priority',
            postgresql_where="is_active = true"
        ),
    )
    
    # Relationships
    hotel = relationship("Hotel", back_populates="triggers")
    
    @validates('name')
    def validate_name(self, key: str, value: str) -> str:
        """
        Validate trigger name
        
        Args:
            key: Field name
            value: Trigger name to validate
            
        Returns:
            str: Validated trigger name
            
        Raises:
            ValueError: If the trigger name is invalid
        """
        if not value or not value.strip():
            raise ValueError("Trigger name is required")
        
        if len(value.strip()) < 2:
            raise ValueError("Trigger name must be at least 2 characters long")
        
        if len(value.strip()) > 255:
            raise ValueError("Trigger name must be less than 255 characters")
        
        return value.strip()
    
    @validates('message_template')
    def validate_message_template(self, key: str, value: str) -> str:
        """
        Validate message template
        
        Args:
            key: Field name
            value: Message template to validate
            
        Returns:
            str: Validated message template
            
        Raises:
            ValueError: If the message template is invalid
        """
        if not value or not value.strip():
            raise ValueError("Message template is required")
        
        if len(value.strip()) > 4000:
            raise ValueError("Message template must be less than 4000 characters")
        
        return value.strip()
    
    @validates('priority')
    def validate_priority(self, key: str, value: int) -> int:
        """
        Validate trigger priority
        
        Args:
            key: Field name
            value: Priority to validate
            
        Returns:
            int: Validated priority
            
        Raises:
            ValueError: If the priority is invalid
        """
        if not isinstance(value, int) or value < 1 or value > 10:
            raise ValueError("Priority must be an integer between 1 and 10")
        
        return value
    
    def get_condition(self, key: str, default: Any = None) -> Any:
        """
        Get a specific condition value
        
        Args:
            key: Condition key (supports dot notation for nested keys)
            default: Default value if key is not found
            
        Returns:
            Any: Condition value or default
        """
        if not self.conditions:
            return default
        
        # Support dot notation for nested keys
        keys = key.split('.')
        value = self.conditions
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_condition(self, key: str, value: Any) -> None:
        """
        Set a specific condition value
        
        Args:
            key: Condition key (supports dot notation for nested keys)
            value: Condition value
        """
        if not self.conditions:
            self.conditions = {}
        
        # Support dot notation for nested keys
        keys = key.split('.')
        current = self.conditions
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Set the final value
        current[keys[-1]] = value
    
    def validate_conditions(self) -> bool:
        """
        Validate trigger conditions based on trigger type
        
        Returns:
            bool: True if conditions are valid
            
        Raises:
            ValueError: If conditions are invalid for the trigger type
        """
        if self.trigger_type == TriggerType.TIME_BASED:
            return self._validate_time_based_conditions()
        elif self.trigger_type == TriggerType.CONDITION_BASED:
            return self._validate_condition_based_conditions()
        elif self.trigger_type == TriggerType.EVENT_BASED:
            return self._validate_event_based_conditions()
        else:
            raise ValueError(f"Unknown trigger type: {self.trigger_type}")
    
    def _validate_time_based_conditions(self) -> bool:
        """Validate time-based trigger conditions"""
        required_fields = ['schedule_type']
        
        for field in required_fields:
            if not self.get_condition(field):
                raise ValueError(f"Time-based trigger missing required field: {field}")
        
        schedule_type = self.get_condition('schedule_type')
        
        if schedule_type == 'hours_after_checkin':
            hours = self.get_condition('hours_after')
            if not isinstance(hours, (int, float)) or hours < 0:
                raise ValueError("hours_after must be a positive number")
        
        elif schedule_type == 'daily_at_time':
            time_str = self.get_condition('time')
            if not time_str:
                raise ValueError("daily_at_time trigger requires 'time' field")
            # Validate time format (HH:MM)
            try:
                time.fromisoformat(time_str)
            except ValueError:
                raise ValueError("Invalid time format. Use HH:MM format")
        
        elif schedule_type == 'days_before_checkout':
            days = self.get_condition('days_before')
            if not isinstance(days, int) or days < 0:
                raise ValueError("days_before must be a positive integer")
        
        return True
    
    def _validate_condition_based_conditions(self) -> bool:
        """Validate condition-based trigger conditions"""
        conditions = self.get_condition('conditions', [])
        
        if not conditions:
            raise ValueError("Condition-based trigger must have at least one condition")
        
        for condition in conditions:
            if not isinstance(condition, dict):
                raise ValueError("Each condition must be a dictionary")
            
            required_fields = ['field', 'operator', 'value']
            for field in required_fields:
                if field not in condition:
                    raise ValueError(f"Condition missing required field: {field}")
        
        return True
    
    def _validate_event_based_conditions(self) -> bool:
        """Validate event-based trigger conditions"""
        event_type = self.get_condition('event_type')
        
        if not event_type:
            raise ValueError("Event-based trigger requires 'event_type' field")
        
        valid_events = [
            'guest_checkin',
            'guest_checkout',
            'negative_sentiment',
            'service_request',
            'complaint_received'
        ]
        
        if event_type not in valid_events:
            raise ValueError(f"Invalid event_type. Must be one of: {valid_events}")
        
        return True
    
    def get_default_conditions_for_type(self, trigger_type: TriggerType) -> Dict[str, Any]:
        """
        Get default conditions for a specific trigger type
        
        Args:
            trigger_type: Type of trigger
            
        Returns:
            Dict[str, Any]: Default conditions
        """
        if trigger_type == TriggerType.TIME_BASED:
            return {
                "schedule_type": "hours_after_checkin",
                "hours_after": 2,
                "timezone": "UTC"
            }
        elif trigger_type == TriggerType.CONDITION_BASED:
            return {
                "conditions": [
                    {
                        "field": "guest.preferences.stay.room_type",
                        "operator": "equals",
                        "value": "suite"
                    }
                ],
                "logic": "AND"
            }
        elif trigger_type == TriggerType.EVENT_BASED:
            return {
                "event_type": "guest_checkin",
                "delay_minutes": 0
            }
        else:
            return {}
    
    def apply_default_conditions(self) -> None:
        """Apply default conditions based on trigger type"""
        if not self.conditions:
            self.conditions = self.get_default_conditions_for_type(self.trigger_type)
    
    @hybrid_property
    def is_time_based(self) -> bool:
        """Check if trigger is time-based"""
        return self.trigger_type == TriggerType.TIME_BASED
    
    @hybrid_property
    def is_condition_based(self) -> bool:
        """Check if trigger is condition-based"""
        return self.trigger_type == TriggerType.CONDITION_BASED
    
    @hybrid_property
    def is_event_based(self) -> bool:
        """Check if trigger is event-based"""
        return self.trigger_type == TriggerType.EVENT_BASED
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert trigger to dictionary
        
        Returns:
            Dict[str, Any]: Trigger dictionary representation
        """
        result = super().to_dict()
        
        # Add computed properties
        result['is_time_based'] = self.is_time_based
        result['is_condition_based'] = self.is_condition_based
        result['is_event_based'] = self.is_event_based
        
        # Convert enum to string
        result['trigger_type'] = self.trigger_type.value if self.trigger_type else None
        
        return result
    
    def __repr__(self) -> str:
        """String representation of the trigger"""
        return (f"<Trigger(id={self.id}, hotel_id={self.hotel_id}, "
                f"name='{self.name}', type={self.trigger_type.value if self.trigger_type else None}, "
                f"active={self.is_active}, priority={self.priority})>")
